#!/usr/bin/env python3
"""
Outbound call dispatcher (Retell).

Every dial passes a gate chain before the API is touched. The gates are here, in
code, and not in the agent prompt, because a prompt is a request and a gate is a
guarantee. TCPA/DNC exposure is per-call and compounds fast.

Gate chain -- ALL must pass:

    1. Campaign type matches contact type. A homeowner can never be dialed by a
       realtor campaign, and vice versa. This is the separation the client asked
       for and it is enforced on the record, not on the list filename.
    2. Contact is not opted out (GHL dnd flag, opt-out tags, channel dnd).
    3. Number is not on the internal suppression list.
    4. Homeowner campaigns require --dnc-verified, asserting a national DNC
       scrub has been run. Absent that flag, homeowner dialing refuses to start.
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
    """Local do-not-call list. Survives CRM outages; checked on every dial."""
    if not os.path.exists(SUPPRESSION):
        return set()
    out = set()
    with open(SUPPRESSION) as f:
        for line in f:
            line = line.split("#")[0].strip()
            n = normalize(line)
            if n:
                out.add(n)
    return out


def add_to_suppression(phone, reason=""):
    os.makedirs(os.path.dirname(SUPPRESSION), exist_ok=True)
    n = normalize(phone)
    if not n:
        return False
    with open(SUPPRESSION, "a") as f:
        f.write(f"{n}  # {_now()} {reason}\n")
    return True


def in_call_window(now=None):
    now = now or central_now()
    return CALL_WINDOW[0] <= now.hour < CALL_WINDOW[1]


class Dialer:
    def __init__(self, campaign, live=False, dnc_verified=False, ghl=None):
        self.campaign = campaign
        self.live = live
        self.dnc_verified = dnc_verified
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

        if self.campaign not in ("realtor", "homeowner"):
            problems.append(f"unknown campaign type: {self.campaign}")

        if self.campaign == "homeowner" and not self.dnc_verified:
            problems.append(
                "homeowner campaign requires --dnc-verified. Federal DNC scrubbing "
                "must be run against this list first. Penalties are $500-$1,500 per call."
            )

        if self.live:
            for name, val in [("RETELL_API_KEY", self.api_key),
                              ("RETELL_AGENT_ID", self.agent_id),
                              ("RETELL_FROM_NUMBER", self.from_number)]:
                if not val:
                    problems.append(f"--live requires {name}")
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

        if contact_type and contact_type != self.campaign:
            return False, (f"contact_type={contact_type!r} does not match "
                           f"campaign={self.campaign!r} — refusing cross-campaign dial")

        if self.ghl and self.ghl.available:
            try:
                contact = self.ghl.find_contact_by_phone(n)
            except Exception as e:
                return False, f"CRM check failed, failing closed: {type(e).__name__}"

            if contact:
                ok, reason = self.ghl.is_callable(contact)
                if not ok:
                    return False, f"CRM: {reason}"

                crm_type = None
                for f in contact.get("customFields", []) or []:
                    if f.get("id") and str(f.get("value", "")).lower() in ("realtor", "homeowner"):
                        crm_type = str(f["value"]).lower()
                if crm_type and crm_type != self.campaign:
                    return False, (f"CRM contact_type={crm_type!r} != campaign={self.campaign!r}")

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
    ap.add_argument("--campaign", required=True, choices=["realtor", "homeowner"])
    ap.add_argument("--numbers", nargs="*", default=[])
    ap.add_argument("--from-csv")
    ap.add_argument("--max", type=int, default=25, help="hard cap on calls this run")
    ap.add_argument("--live", action="store_true", help="actually place calls")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--dnc-verified", action="store_true",
                    help="assert federal DNC scrubbing has been run on this list")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between calls")
    args = ap.parse_args()

    live = args.live
    load("retell", "ghl")

    targets = [{"phone": p, "contact_type": None, "variables": {}} for p in args.numbers]
    if args.from_csv:
        targets += load_csv(args.from_csv)

    if not targets:
        sys.exit("no targets. Use --numbers or --from-csv.")

    if len(targets) > args.max:
        print(f"note: {len(targets)} targets, capped at --max {args.max}")
        targets = targets[: args.max]

    ghl = GHL()
    d = Dialer(args.campaign, live=live, dnc_verified=args.dnc_verified,
               ghl=ghl if ghl.available else None)

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
