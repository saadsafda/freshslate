#!/usr/bin/env python3
"""Retell webhook receiver -> GoHighLevel CRM push.

Scope: this only ever handles calls placed by the buyer-outreach agent
(realtors/cash buyers, never sellers/homeowners - see
skills/buyer-outreach/SKILL.md and src/buyer_outreach.py, which is the same
trust boundary this file must not cross). Currently that's the "Marigny"
conversation-flow agent - see deals/_config/call-script.md for the current
agent_id and approved script text.

Two request shapes hit this server, both signed the same way
(X-Retell-Signature, verified before any other processing):
  - POST /webhooks/retell            - agent-level post-call webhook_url,
    fires automatically after every call (event=call_analyzed).
  - POST /webhooks/retell/log-call-outcome - the log_call_outcome custom
    tool, called by the flow itself once right before the call ends, with
    the structured qualifying fields it collected (deals/_config's "Collected
    variables"). This is the more reliable source for those specific fields -
    the call_analyzed event's custom_analysis_data depends on a separate
    post-call analysis LLM inferring them from the transcript, which isn't
    configured to extract this field set.

Every request is authenticated before any other work happens: an invalid or
missing Retell signature gets 401 and nothing else runs. This exists because
an unauthenticated POST here would otherwise let anyone inject arbitrary
contact records into the client's live CRM.

Run:
    python3 src/webhook_server.py [port]   # default port 8090
"""
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
import ghl_client  # noqa: E402
import dnc  # noqa: E402  - suppression requests are recorded, not just tagged

RETELL_ENV_FILE = REPO_ROOT.parent / "secrets" / "retell.env"
EVENT_LOG_DIR = REPO_ROOT.parent / "deals" / "_inbox"
SIGNATURE_MAX_AGE_SECONDS = 5 * 60

# Outcomes buyer_outreach.py / the Morgan agent's post-call schema can log -
# see call-script.md "Global behaviors". Anything else is passed through as
# a generic tag rather than dropped, so an unrecognized-but-legitimate value
# doesn't get silently lost.
OUTCOME_TAGS = {
    "callback_booked": "freshslate-callback-booked",
    "no_fit": "freshslate-no-fit",
    "dnc_requested": "freshslate-dnc",
    "hostile_ended": "freshslate-hostile",
    "reschedule_requested": "freshslate-reschedule",
}


def load_retell_env():
    if not RETELL_ENV_FILE.exists():
        print(f"FATAL: {RETELL_ENV_FILE} not found.", file=sys.stderr)
        sys.exit(1)
    env = {}
    for line in RETELL_ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    for required in ("RETELL_WEBHOOK_SECRET", "RETELL_AGENT_ID"):
        if not env.get(required):
            print(f"FATAL: {required} not set in secrets/retell.env.", file=sys.stderr)
            sys.exit(1)
    return env


def verify_signature(raw_body: bytes, header_value: str, webhook_secret: str) -> bool:
    """https://docs.retellai.com/features/secure-webhook

    Header format: v={timestamp},d={hex_digest}
    digest = HMAC-SHA256(raw_body + timestamp, webhook_secret), hex-encoded.

    "webhook_secret" here must be a real Retell API key that has the
    "webhook" badge in the dashboard (Settings > API Keys) - Retell has no
    separate webhook-signing secret, despite the name of this field in
    retell.env. Wrong key in that slot = every genuine Retell call 401s
    here, silently, since self-signed synthetic tests can't catch it (see
    retell.env.example).
    """
    if not header_value:
        return False
    parts = dict(p.split("=", 1) for p in header_value.split(",") if "=" in p)
    timestamp, digest = parts.get("v"), parts.get("d")
    if not timestamp or not digest:
        return False
    try:
        if abs(time.time() - int(timestamp) / 1000) > SIGNATURE_MAX_AGE_SECONDS:
            return False
    except ValueError:
        return False
    expected = hmac.new(
        webhook_secret.encode(), raw_body + timestamp.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, digest)


def log_event(event_type: str, call_id: str, note: str):
    EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = EVENT_LOG_DIR / f"{datetime.now(timezone.utc).date()}-webhook-events.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "call_id": call_id,
        "note": note,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def record_dnc_request(call: dict, requested: bool, origin: str) -> str:
    """A "take me off your list" on a call is a legally binding suppression
    request. Tagging it in the CRM is not enough - it has to reach the
    internal DNC list, or the next sweep of this number dials it again.
    Returns a note fragment for the event log."""
    if not requested:
        return ""
    number = call.get("to_number") or ""
    try:
        entry = dnc.add_internal(
            number,
            reason=f"DNC requested during Retell call {call.get('call_id', '?')}",
            source=f"retell-webhook:{origin}",
        )
        return f" | INTERNAL DNC: recorded {entry['number']}"
    except ValueError as e:
        # Never swallow this: a suppression request we failed to record is
        # the one failure here with real legal consequence.
        return f" | ⛔ INTERNAL DNC RECORDING FAILED ({e}) - RECORD MANUALLY"


def handle_call_analyzed(call: dict, ghl_env: dict) -> str:
    to_number = call.get("to_number", "")
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    summary = analysis.get("call_summary", "")
    variables = call.get("retell_llm_dynamic_variables") or {}
    contact_name = variables.get("contact_name", "")
    deal_context = variables.get("deal_context", "")

    tags = ["freshslate-buyer-outreach"]
    for field, tag in OUTCOME_TAGS.items():
        if custom.get(field):
            tags.append(tag)

    # Record the suppression request BEFORE the CRM write: if GHL is down,
    # the DNC entry must still have been made.
    dnc_note = record_dnc_request(call, bool(custom.get("dnc_requested")), "call_analyzed")

    # Tags are added separately, never passed to upsert - see ghl_client.add_tags
    # for why (upsert replaces the tag set; the two events per call clobber
    # each other).
    result = ghl_client.upsert_contact(ghl_env, to_number, contact_name)
    if not result["ok"]:
        return f"GHL upsert_contact failed: {result['error']}{dnc_note}"

    contact_id = (result.get("response") or {}).get("contact", {}).get("id")
    if not contact_id:
        return f"GHL upsert_contact returned no contact id: {result['response']}{dnc_note}"

    tag_result = ghl_client.add_tags(ghl_env, contact_id, tags)
    tag_note = "" if tag_result["ok"] else f" | tag add failed: {tag_result['error']}"

    note_lines = [f"Retell call {call.get('call_id', '')} (Marigny / buyer-outreach)"]
    if deal_context:
        note_lines.append(f"Deal context: {deal_context}")
    if summary:
        note_lines.append(f"Summary: {summary}")
    if custom:
        note_lines.append(f"Outcome data: {json.dumps(custom)}")
    note_result = ghl_client.add_note(ghl_env, contact_id, "\n".join(note_lines))
    if not note_result["ok"]:
        return f"GHL add_note failed: {note_result['error']}{dnc_note}{tag_note}"
    return f"OK - contact {contact_id} updated, tags={tags}{dnc_note}{tag_note}"


# Field names match the log_call_outcome tool's parameter schema in the
# "Marigny" conversation flow (see deals/_config/call-script.md "Collected
# variables"). If the flow's tool schema changes, this must be updated to
# match - unrecognized fields still get logged in the note, just untagged.
def handle_log_call_outcome(call: dict, args: dict, ghl_env: dict) -> str:
    to_number = call.get("to_number", "")

    tags = ["freshslate-buyer-outreach"]
    if args.get("do_not_call_requested"):
        tags.append("freshslate-dnc")
    if args.get("callback_booked"):
        tags.append("freshslate-callback-booked")
    elif args.get("fits_buy_box") is False:
        tags.append("freshslate-no-fit")
    if args.get("reschedule_requested_time"):
        tags.append("freshslate-reschedule")

    # Same ordering rationale as handle_call_analyzed: suppression first.
    dnc_note = record_dnc_request(call, bool(args.get("do_not_call_requested")),
                                  "log_call_outcome")

    # Tags added separately, never via upsert - see ghl_client.add_tags.
    result = ghl_client.upsert_contact(ghl_env, to_number, "")
    if not result["ok"]:
        return f"GHL upsert_contact failed: {result['error']}{dnc_note}"

    contact_id = (result.get("response") or {}).get("contact", {}).get("id")
    if not contact_id:
        return f"GHL upsert_contact returned no contact id: {result['response']}{dnc_note}"

    tag_result = ghl_client.add_tags(ghl_env, contact_id, tags)
    tag_note = "" if tag_result["ok"] else f" | tag add failed: {tag_result['error']}"

    note_lines = [f"Retell call {call.get('call_id', '')} (Marigny / buyer-outreach)"]
    for field, value in args.items():
        if value not in (None, ""):
            note_lines.append(f"{field}: {value}")
    note_result = ghl_client.add_note(ghl_env, contact_id, "\n".join(note_lines))
    if not note_result["ok"]:
        return f"GHL add_note failed: {note_result['error']}{dnc_note}{tag_note}"
    return f"OK - contact {contact_id} updated, tags={tags}{dnc_note}{tag_note}"


class Handler(BaseHTTPRequestHandler):
    retell_env = None
    ghl_env = None

    def log_message(self, fmt, *args):
        pass  # log_event() is the audit trail; suppress default stderr noise

    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path not in ("/webhooks/retell", "/webhooks/retell/log-call-outcome"):
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""
        signature = self.headers.get("X-Retell-Signature", "")

        if not verify_signature(raw_body, signature, self.retell_env["RETELL_WEBHOOK_SECRET"]):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"invalid signature")
            return

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            # Ack before logging so Retell doesn't retry an unparseable body.
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            log_event("malformed", None, "malformed JSON body, signature was valid")
            return

        call = body.get("call") or {}
        if call.get("agent_id") and call["agent_id"] != self.retell_env["RETELL_AGENT_ID"]:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            log_event(
                body.get("event", "tool_call"), call.get("call_id"),
                f"IGNORED - agent_id {call.get('agent_id')} is not the buyer-outreach agent",
            )
            return

        if self.path == "/webhooks/retell/log-call-outcome":
            # Synchronous: this fires while the call is still live, right
            # before it ends, so we finish the GHL write before acking -
            # Retell retries up to 2x on failure/timeout, and a fast ack
            # here would just risk a retry racing a still-in-flight write.
            note = handle_log_call_outcome(call, body.get("args") or {}, self.ghl_env)
            log_event("log_call_outcome", call.get("call_id"), note)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        # /webhooks/retell (agent-level post-call webhook_url) - ack
        # immediately, GHL/network errors below get logged, not retried via
        # Retell (which would risk duplicate CRM writes on retry).
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

        if body.get("event") != "call_analyzed":
            log_event(body.get("event"), call.get("call_id"), f"received, no action ({body.get('event')})")
            return

        note = handle_call_analyzed(call, self.ghl_env)
        log_event("call_analyzed", call.get("call_id"), note)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    Handler.retell_env = load_retell_env()
    Handler.ghl_env = ghl_client.load_env()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Listening on :{port} (POST /webhooks/retell{{,/log-call-outcome}}, GET /healthz)")
    server.serve_forever()


if __name__ == "__main__":
    main()
