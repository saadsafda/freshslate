#!/usr/bin/env python3
"""
Outbound call dispatcher (Retell).

Every dial passes a gate chain before the API is touched. The gates are here, in
code, and not in the agent prompt, because a prompt is a request and a gate is a
guarantee. TCPA/DNC exposure is per-call and compounds fast.

Authorized scope: licensed real estate agents only. Homeowner, seller, heir,
buyer, and unknown contacts are never dialed by this program.

Gate chain -- ALL must pass:

    1. Campaign and contact type both equal ``realtor``. Blank is a failure.
    2. Contact is not opted out (GHL dnd flag, opt-out tags, channel dnd).
    3. Number is not on the internal suppression list.
    4. A live target exists in GHL and its fs_contact_type is ``realtor``.
    5. Calling window: 8am-9pm in the contact's local time (America/Chicago),
       per TCPA. Checked per call, not per batch.
    6. Per-run call cap, so a bad list cannot become a thousand violations.

Default mode is --dry-run. Placing real calls requires --live, explicitly.

Usage:
    python3 src/dialer.py --campaign realtor --numbers +15045551234 --dry-run
    python3 src/dialer.py --campaign realtor --from-csv leads.csv --live --max 25
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ghl import GHL  # noqa: E402
from secrets_loader import load  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPRESSION = os.path.join(ROOT, "deals", "_config", "suppression-list.txt")
CALL_LOG = os.path.join(ROOT, "deals", "_index", "calls")

RETELL_BASE = "https://api.retellai.com"

# TCPA: no calls before 8am or after 9pm in the CALLED PARTY's local time.
# Louisiana is America/Chicago (UTC-5 CDT / UTC-6 CST).
CALL_WINDOW = (8, 21)
CENTRAL_OFFSET_HOURS = -5


class GateFailure(Exception):
    """A dial was refused. Carries the reason for the audit log."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def central_now():
    return datetime.now(timezone.utc) + timedelta(hours=CENTRAL_OFFSET_HOURS)


def normalize(phone):
    """To E.164 for US numbers. Returns None if it cannot be made valid."""
    if not phone:
        return None
    d = "".join(c for c in str(phone) if c.isdigit())
    if len(d) == 10:
        return f"+1{d}"
    if len(d) == 11 and d[0] == "1":
        return f"+{d}"
    if str(phone).startswith("+") and 11 <= len(d) <= 15:
        return f"+{d}"
    return None


def load_suppression():
    """Local do-not-call list. Survives CRM outages; checked on every dial.

    Reads BOTH local stores and returns their union. This module grew a plain
    suppression-list.txt while dnc.py grew an append-only internal-dnc.jsonl,
    and for a while neither knew about the other - a number opted out through
    one path was still dialable through the other. Two do-not-call lists is the
    same as none: the caller only has to miss one of them to place the call a
    consumer explicitly refused. Read both, always, and let the union win.
    """
    out = set()

    if os.path.exists(SUPPRESSION):
        with open(SUPPRESSION) as f:
            for line in f:
                line = line.split("#")[0].strip()
                n = normalize(line)
                if n:
                    out.add(n)

    # dnc.py is the legally-framed store: append-only, one JSON object per
    # entry recording who/when/why. Failing to read it must never be silent -
    # a suppression list that quietly comes back short is worse than an error.
    #
    # Re-normalize every key on the way in. dnc.py stores bare 10-digit NANP
    # ("5045550142") while this module works in E.164 ("+15045550142"), so the
    # raw keys would never compare equal to a dial target - the numbers would
    # sit in the set looking suppressed while every one of them stayed dialable.
    try:
        import dnc
        for key in dnc.load_internal():
            n = normalize(key)
            if n:
                out.add(n)
    except Exception as e:
        raise GateFailure(
            f"cannot read the internal DNC list ({type(e).__name__}: {e}). "
            "Refusing to dial with an incomplete suppression list."
        ) from e

    return out


def add_to_suppression(phone, reason="", source="dialer"):
    """Record an opt-out in both local stores.

    Writes dnc.py's internal-dnc.jsonl first, because that is the one with the
    audit trail; the text file is kept in sync so a human can read and hand-edit
    it. Both are append-only - a suppression request is permanent.
    """
    n = normalize(phone)
    if not n:
        return False

    try:
        import dnc
        dnc.add_internal(n, reason=reason or "opt-out", source=source)
    except Exception as e:
        raise GateFailure(
            f"could not record opt-out for {n} in the internal DNC list "
            f"({type(e).__name__}: {e}). This must not be swallowed - an "
            "unrecorded opt-out becomes a repeat call."
        ) from e

    os.makedirs(os.path.dirname(SUPPRESSION), exist_ok=True)
    with open(SUPPRESSION, "a") as f:
        f.write(f"{n}  # {_now()} {reason}\n")
    return True


def in_call_window(now=None):
    now = now or central_now()
    return CALL_WINDOW[0] <= now.hour < CALL_WINDOW[1]


class Dialer:
    def __init__(self, campaign, live=False, ghl=None):
        self.campaign = campaign
        self.live = live
        self.ghl = ghl
        self.suppression = load_suppression()
        self.api_key = os.environ.get("RETELL_API_KEY")
        self.agent_id = os.environ.get("RETELL_AGENT_ID")
        self.from_number = os.environ.get("RETELL_FROM_NUMBER")
        self.results = []

    # ---------- gates ----------

    def preflight(self):
        """Run-level checks. Raises before any number is considered."""
        problems = []

        if self.campaign != "realtor":
            problems.append(
                f"campaign {self.campaign!r} is not authorized. Client scope permits "
                "licensed-realtor calls only."
            )

        if self.live:
            for name, val in [("RETELL_API_KEY", self.api_key),
                              ("RETELL_AGENT_ID", self.agent_id),
                              ("RETELL_FROM_NUMBER", self.from_number)]:
                if not val:
                    problems.append(f"--live requires {name}")
            if not self.ghl or not self.ghl.available:
                problems.append(
                    "--live requires GHL. Every live target must resolve to a callable "
                    "contact with fs_contact_type=realtor."
                )
            if not in_call_window():
                problems.append(
                    f"outside TCPA calling window. Central time is "
                    f"{central_now().strftime('%H:%M')}; allowed {CALL_WINDOW[0]}:00-{CALL_WINDOW[1]}:00."
                )

        if problems:
            raise GateFailure(" | ".join(problems))

    def check_contact(self, phone, contact_type=None):
        """Per-number gates. Returns (allowed, reason)."""
        n = normalize(phone)
        if not n:
            return False, f"unparseable phone: {phone!r}"

        if n in self.suppression:
            return False, "on local suppression list"

        if not in_call_window():
            return False, f"outside calling window ({central_now().strftime('%H:%M')} Central)"

        if str(contact_type or "").strip().lower() != "realtor":
            return False, (
                f"contact_type={contact_type!r}; licensed-realtor type is required — "
                "blank, homeowner, seller, heir, and buyer records are blocked"
            )

        if self.ghl and self.ghl.available:
            try:
                contact = self.ghl.find_contact_by_phone(n)
            except Exception as e:
                return False, f"CRM check failed, failing closed: {type(e).__name__}"

            if not contact:
                return False, "CRM: target not found — live calls require a verified realtor record"

            ok, reason = self.ghl.is_callable(contact)
            if not ok:
                return False, f"CRM: {reason}"

            try:
                fmap = self.ghl.field_map()
            except Exception as e:
                return False, f"CRM field lookup failed, failing closed: {type(e).__name__}"
            type_id = fmap.get("contact.fs_contact_type") or fmap.get("fs_contact_type")
            if not type_id:
                return False, "CRM: fs_contact_type field is unavailable"

            crm_type = None
            for f in contact.get("customFields", []) or []:
                if f.get("id") == type_id:
                    crm_type = str(f.get("value", "")).strip().lower()
                    break
            if crm_type != "realtor":
                return False, f"CRM contact_type={crm_type!r}; licensed realtor required"

        return True, "ok"

    # ---------- dial ----------

    def _place(self, to_number, variables):
        body = {
            "from_number": self.from_number,
            "to_number": to_number,
            "override_agent_id": self.agent_id,
            "retell_llm_dynamic_variables": variables,
        }
        req = urllib.request.Request(
            f"{RETELL_BASE}/v2/create-phone-call",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Retell {e.code}: {e.read().decode()[:300]}")

    def dial(self, phone, variables=None, contact_type=None):
        n = normalize(phone)
        allowed, reason = self.check_contact(phone, contact_type)

        rec = {
            "phone": n or phone,
            "campaign": self.campaign,
            "allowed": allowed,
            "reason": reason,
            "at": _now(),
            "live": self.live,
        }

        if not allowed:
            rec["status"] = "BLOCKED"
            self.results.append(rec)
            return rec

        if not self.live:
            rec["status"] = "DRY_RUN"
            self.results.append(rec)
            return rec

        try:
            resp = self._place(n, variables or {})
            rec["status"] = "PLACED"
            rec["call_id"] = resp.get("call_id")
        except Exception as e:
            rec["status"] = "ERROR"
            rec["error"] = str(e)[:300]

        self.results.append(rec)
        return rec

    def write_log(self):
        os.makedirs(CALL_LOG, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = os.path.join(CALL_LOG, f"{day}-dialer.jsonl")
        with open(path, "a") as f:
            for r in self.results:
                f.write(json.dumps(r) + "\n")
        return path


def load_csv(path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            low = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            phone = low.get("phone") or low.get("phone_number") or low.get("number")
            if phone:
                rows.append({
                    "phone": phone,
                    "contact_type": low.get("contact_type") or low.get("fs_contact_type"),
                    "variables": {k: v for k, v in low.items()
                                  if k not in ("phone", "phone_number", "number", "contact_type")},
                })
    return rows


def main():
    ap = argparse.ArgumentParser(description="Fresh Slate outbound dialer")
    ap.add_argument("--campaign", required=True, choices=["realtor"])
    ap.add_argument("--numbers", nargs="*", default=[])
    ap.add_argument("--from-csv")
    ap.add_argument("--max", type=int, default=25, help="hard cap on calls this run")
    ap.add_argument("--live", action="store_true", help="actually place calls")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between calls")
    args = ap.parse_args()

    live = args.live
    load("retell", "ghl")

    if live and args.numbers:
        sys.exit(
            "--numbers is dry-run only. Live targets must come from a CSV carrying "
            "contact_type=realtor and must also exist as realtor records in GHL."
        )

    targets = [{"phone": p, "contact_type": "realtor", "variables": {}}
               for p in args.numbers]
    if args.from_csv:
        targets += load_csv(args.from_csv)

    if not targets:
        sys.exit("no targets. Use --numbers or --from-csv.")

    if len(targets) > args.max:
        print(f"note: {len(targets)} targets, capped at --max {args.max}")
        targets = targets[: args.max]

    ghl = GHL()
    d = Dialer(args.campaign, live=live, ghl=ghl if ghl.available else None)

    print(f"Campaign : {args.campaign}")
    print(f"Mode     : {'LIVE — REAL CALLS' if live else 'DRY RUN'}")
    print(f"Targets  : {len(targets)}")
    print(f"Central  : {central_now().strftime('%Y-%m-%d %H:%M')} "
          f"(window {CALL_WINDOW[0]}:00-{CALL_WINDOW[1]}:00)")
    print(f"CRM      : {'connected' if ghl.available else 'unavailable'}")
    print(f"Suppress : {len(d.suppression)} numbers\n")

    try:
        d.preflight()
    except GateFailure as e:
        sys.exit(f"PREFLIGHT FAILED\n  {e}")

    if live:
        print("!!! LIVE MODE — real calls will be placed !!!")
        if input("Type CONFIRM to proceed: ").strip() != "CONFIRM":
            sys.exit("aborted.")
        print()

    for i, t in enumerate(targets, 1):
        r = d.dial(t["phone"], t.get("variables"), t.get("contact_type"))
        mark = {"PLACED": "OK", "DRY_RUN": "--", "BLOCKED": "XX", "ERROR": "!!"}[r["status"]]
        print(f"  [{mark}] {r['phone']:16} {r['status']:8} {r['reason']}")
        if live and i < len(targets):
            time.sleep(args.delay)

    path = d.write_log()
    blocked = sum(1 for r in d.results if r["status"] == "BLOCKED")
    placed = sum(1 for r in d.results if r["status"] == "PLACED")
    print(f"\nplaced={placed} blocked={blocked} total={len(d.results)}")
    print(f"log: {path}")


if __name__ == "__main__":
    main()
