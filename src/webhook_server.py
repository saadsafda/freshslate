#!/usr/bin/env python3
"""
Retell -> GHL webhook receiver.

Retell posts call lifecycle events here; this writes the outcome back to the CRM
and enforces opt-out. Runs on stdlib http.server -- no framework, because this
does one thing and a dependency tree is attack surface on a box holding seller PII.

Endpoints:
    GET  /health            liveness
    POST /webhooks/retell   Retell call events

Signature verification is mandatory and fails closed. Retell signs each request
with HMAC-SHA256 over the raw body using the API key; RETELL_WEBHOOK_SECRET is
accepted as an alternate signing key. An unsigned or badly signed request is
rejected with 401 before the body is parsed -- this endpoint is public, and a
forged 'opt-out' or a forged 'interested' both cause real damage.

Opt-out handling is the reason this file exists. When a call ends, the transcript
is scanned for opt-out language regardless of what the agent's own analysis said,
because the agent's structured output is a model judgement and the DNC obligation
is not conditional on the model getting it right.

Usage:
    python3 src/webhook_server.py --port 8080
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ghl import GHL, OPT_OUT_TAG  # noqa: E402
from secrets_loader import load  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "deals", "_index", "calls")

# Phrases that constitute an opt-out. Deliberately broad: a false positive costs
# one lost lead, a false negative costs $500-$1,500 per subsequent call.
# The bare forms "don't call" / "don't contact" are anchored to a target word
# (me/us/this/here/again/back...). Without the anchor, "I don't call people back
# usually, but sure" reads as an opt-out and suppresses a willing contact.
# Over-matching here is not free: it silently deletes leads.
OPT_OUT_PATTERNS = [
    r"\bdo not call\b", r"\bstop calling\b", r"\bnever call\b",
    r"\btake me off\b", r"\bremove me\b", r"\bunsubscribe\b", r"\bopt me out\b",
    r"\bdo not contact\b", r"\bquit calling\b",
    r"\bstop contacting\b", r"\bno more calls\b", r"\blose my number\b",
    r"\btake (me|us) off\b", r"\bdelete my number\b",
    r"\bdon'?t (ever )?(call|contact) (me|us|this|here|again|back|my)\b",
    r"\bdon'?t (call|contact) (me|us)\b",
]

# Signals a human must take over. Module 13 requires escalation on legal matters.
ESCALATE_PATTERNS = {
    "attorney": [r"\battorney\b", r"\blawyer\b", r"\blegal counsel\b", r"\bmy lawyer\b"],
    "succession_dispute": [r"\bsuccession\b", r"\bprobate\b", r"\bestate\b", r"\bheir\b"],
    "legal_question": [r"\bsue\b", r"\blawsuit\b", r"\blitigation\b", r"\bcourt\b"],
    "distress": [r"\bpassed away\b", r"\bdied\b", r"\bfuneral\b", r"\bhospice\b"],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def scan(text, patterns):
    if not text:
        return []
    low = text.lower()
    return [p for p in patterns if re.search(p, low)]


def detect_opt_out(transcript):
    return bool(scan(transcript, OPT_OUT_PATTERNS))


def detect_escalation(transcript):
    if not transcript:
        return None
    for reason, pats in ESCALATE_PATTERNS.items():
        if scan(transcript, pats):
            return reason
    return None


def verify_signature(raw_body, header_sig, keys):
    """
    Constant-time HMAC-SHA256 check against each candidate key.

    Header forms seen in the wild, all accepted:
        <hex>
        sha256=<hex>
        v=1,<hex>            (comma-delimited, version prefix)
        t=...,v1=<hex>       (Stripe-style, multiple parts)

    Every hex-looking token in the header is tried against every candidate key,
    so a format change upstream degrades to "still works" rather than "rejects
    all traffic". Comparison stays constant-time.
    """
    if not header_sig:
        return False

    # Pull every plausible digest out of the header regardless of delimiter.
    tokens = set()
    raw = header_sig.strip()
    tokens.add(raw)
    for part in re.split(r"[,;\s]+", raw):
        part = part.strip()
        if not part:
            continue
        tokens.add(part)
        if "=" in part:
            tokens.add(part.split("=", 1)[1].strip())

    candidates = {t for t in tokens if len(t) == 64 and all(c in "0123456789abcdefABCDEF" for c in t)}
    if not candidates:
        return False

    for key in keys:
        if not key:
            continue
        expected = hmac.new(key.encode(), raw_body, hashlib.sha256).hexdigest()
        for cand in candidates:
            if hmac.compare_digest(expected, cand.lower()):
                return True
    return False


def archive(event_name, payload):
    """Append-only call log. Evidence trail for the audit file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(LOG_DIR, f"{day}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps({"received_at": _now(), "event": event_name,
                            "payload": payload}, default=str) + "\n")
    return path


def process_call_event(payload, ghl=None):
    """
    Handle a Retell call event. Returns a dict describing what was done.

    Pure enough to unit-test: pass ghl=None and it computes decisions without
    writing to the CRM.
    """
    call = payload.get("call", payload)
    event = payload.get("event", "unknown")

    to_number = call.get("to_number") or call.get("to")
    transcript = call.get("transcript") or ""
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    dynamic = call.get("retell_llm_dynamic_variables") or {}

    result = {
        "event": event,
        "call_id": call.get("call_id"),
        "to_number": to_number,
        "opt_out": False,
        "escalate": None,
        "outcome": None,
        "ghl_contact_id": None,
        "actions": [],
    }

    # Opt-out: transcript scan OR agent-reported. Either one triggers it.
    agent_said_optout = str(custom.get("call_outcome", "")).lower() in ("opt_out", "do_not_call")
    result["opt_out"] = detect_opt_out(transcript) or agent_said_optout

    result["escalate"] = detect_escalation(transcript)

    if result["opt_out"]:
        result["outcome"] = "opt_out"
    elif result["escalate"]:
        result["outcome"] = "escalate_human"
    else:
        result["outcome"] = custom.get("call_outcome") or (
            "no_answer" if call.get("disconnection_reason") in
            ("dial_no_answer", "dial_busy", "voicemail_reached") else "completed"
        )

    # Record the opt-out LOCALLY FIRST, before anything that can bail out.
    #
    # Everything below this point is conditional: no GHL client, no phone
    # number, a non-realtor contact_type, a missing contact id - each returns
    # early. Marking dnd=true in the CRM was the only suppression this handler
    # did, so a GoHighLevel outage during the one call where someone said "take
    # me off your list" meant the request was heard, acknowledged on the phone,
    # and then dropped. The next run would dial them again.
    #
    # The local list is what dialer.py actually scrubs against, it needs no
    # network, and the write is append-only. It goes first, unconditionally.
    if result["opt_out"] and to_number:
        try:
            import dialer
            dialer.add_to_suppression(
                to_number,
                reason=f"opt-out on call {call.get('call_id') or 'unknown'}",
                source="retell_webhook",
            )
            result["actions"].append("suppressed_local")
        except Exception as e:
            # Loud, and recorded in the append-only event log. An opt-out we
            # failed to persist is a compliance incident, not a log line.
            result["actions"].append(f"SUPPRESSION_WRITE_FAILED:{type(e).__name__}")
            log_line = (f"!!! FAILED TO RECORD OPT-OUT for {to_number} "
                        f"(call {call.get('call_id')}): {e}")
            print(log_line, file=sys.stderr)
            archive("suppression_write_failed", {
                "to_number": to_number,
                "call_id": call.get("call_id"),
                "error": f"{type(e).__name__}: {e}",
            })

    if ghl is None or not to_number:
        return result

    # The client authorized realtor calls only. A webhook claiming any other
    # contact type is quarantined: do not create a homeowner/seller contact and
    # do not write call-derived fields into the CRM. The signed raw event remains
    # in the append-only webhook log for incident review.
    if str(dynamic.get("contact_type") or "").strip().lower() != "realtor":
        result["actions"].append("quarantined:non_realtor_contact_type")
        return result

    contact = ghl.find_contact_by_phone(to_number)
    if not contact:
        contact = ghl.upsert_contact(
            phone=to_number,
            first_name=dynamic.get("agent_first_name") or dynamic.get("first_name"),
            tags=["freshslate-realtor"],
            custom={"fs_contact_type": "realtor"},
        )
        result["actions"].append("contact_created")

    cid = (contact or {}).get("id")
    result["ghl_contact_id"] = cid
    if not cid:
        result["actions"].append("no_contact_id")
        return result

    if result["opt_out"]:
        ghl.mark_opted_out(cid, reason=f"call {call.get('call_id')}")
        result["actions"].append("dnd_set")

    fields = {
        "fs_last_call_at": _now(),
        "fs_call_outcome": result["outcome"],
        "fs_call_summary": (analysis.get("call_summary") or "")[:4000],
        "fs_call_recording_url": call.get("recording_url"),
    }
    if result["opt_out"]:
        fields["fs_dnc_status"] = "suppressed"
        fields["fs_optout_date"] = _now()
    if result["escalate"]:
        fields["fs_escalation_reason"] = result["escalate"]
    if custom.get("callback_time"):
        fields["fs_callback_at"] = custom["callback_time"]

    ghl.upsert_contact(phone=to_number, custom=fields)
    result["actions"].append("fields_written")

    tags = []
    if result["escalate"]:
        tags.append("freshslate-escalate-human")
    if result["outcome"] == "callback_booked":
        tags.append("freshslate-callback-booked")
    if tags:
        ghl.add_tags(cid, tags)
        result["actions"].append(f"tagged:{','.join(tags)}")

    note = [
        f"[{_now()}] Retell call {call.get('call_id')}",
        f"Outcome: {result['outcome']}",
    ]
    if result["opt_out"]:
        note.append("*** DO NOT CALL recorded — contact suppressed (dnd=true) ***")
    if result["escalate"]:
        note.append(f"*** ESCALATE TO HUMAN: {result['escalate']} ***")
    if analysis.get("call_summary"):
        note.append(f"\nSummary: {analysis['call_summary']}")
    ghl.add_note(cid, "\n".join(note))
    result["actions"].append("note_added")

    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "FreshSlate/1.0"
    ghl_client = None
    signing_keys = ()

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}\n")

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", "/healthz"):
            self._send(200, {"status": "ok", "time": _now(),
                             "ghl": bool(self.ghl_client and self.ghl_client.available)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/webhooks/retell":
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
            self._send(413, {"error": "payload too large"})
            return
        raw = self.rfile.read(length)

        sig = (self.headers.get("x-retell-signature")
               or self.headers.get("X-Retell-Signature")
               or self.headers.get("x-hub-signature-256"))

        if not verify_signature(raw, sig, self.signing_keys):
            self.log_message("REJECTED unsigned/invalid webhook from %s", self.client_address[0])
            self._send(401, {"error": "invalid signature"})
            return

        try:
            payload = json.loads(raw.decode())
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid json"})
            return

        event = payload.get("event", "unknown")
        archive(event, payload)

        # Only terminal events carry a transcript worth acting on.
        if event not in ("call_ended", "call_analyzed"):
            self._send(200, {"status": "ignored", "event": event})
            return

        try:
            result = process_call_event(payload, ghl=self.ghl_client)
            self.log_message("call %s -> %s%s", result.get("call_id"), result.get("outcome"),
                             " [OPT-OUT]" if result.get("opt_out") else "")
            self._send(200, {"status": "ok", "result": result})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": type(e).__name__, "detail": str(e)[:300]})


def main():
    ap = argparse.ArgumentParser(description="Retell -> GHL webhook receiver")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address; keep localhost behind a reverse proxy")
    ap.add_argument("--allow-unsigned", action="store_true",
                    help="DEV ONLY: skip signature verification")
    args = ap.parse_args()

    st = load("retell", "ghl")
    keys = [os.environ.get("RETELL_WEBHOOK_SECRET"), os.environ.get("RETELL_API_KEY")]

    Handler.ghl_client = GHL() if st.get("ghl") else None
    Handler.signing_keys = tuple(k for k in keys if k)

    if args.allow_unsigned:
        print("!!! SIGNATURE VERIFICATION DISABLED — development only !!!")
        Handler.signing_keys = ()
        original = verify_signature
        globals()["verify_signature"] = lambda *a, **k: True
        del original

    print(f"Fresh Slate webhook receiver on http://{args.host}:{args.port}")
    print(f"  POST /webhooks/retell   signing keys loaded: {len(Handler.signing_keys)}")
    print(f"  GET  /health")
    print(f"  GHL: {'connected' if Handler.ghl_client else 'UNAVAILABLE'}")
    print(f"  Call log: {LOG_DIR}\n")

    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
