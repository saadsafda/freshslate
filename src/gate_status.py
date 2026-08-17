#!/usr/bin/env python3
"""Snapshot every compliance gate to a file the briefing agent can read.

Why this exists
---------------
The OpenClaw agent that writes the morning brief runs with `exec` denied
(`tools.deny: ["exec", ...]` in openclaw.json) and `fs.workspaceOnly: true`.
That is deliberate - a briefing agent has no business shelling out on a box
that holds Retell and GHL credentials. But it means the agent can never run
`dnc.py --status` or `act807.py --check` itself, and the 2026-08-13 brief
consequently reported the DNC gate as "unverified this run" and left the
deadline sections blank. A brief that cannot see the gates is worse than no
brief: "unverified" and "clear" look the same at 7am on a phone.

So the host - which does have exec - computes the gates on a schedule and
writes the result into `deals/_inbox/`, which IS bind-mounted into the agent's
workspace. The agent reads a file instead of running a script.

The snapshot carries `generated_at` so staleness is detectable. A consumer
that finds this file missing or stale must report the gates as UNKNOWN, never
as clear. See skills/deal-desk-brief/SKILL.md.

Usage:
    python3 src/gate_status.py            # write the snapshot
    python3 src/gate_status.py --print    # write, and echo the markdown
"""
import argparse
import io
import json
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

INBOX = REPO_ROOT / "deals" / "_inbox"
SCRIPT_GATE_FILE = REPO_ROOT / "deals" / "_config" / "call-script.md"
COSTS_FILE = REPO_ROOT / "deals" / "_config" / "costs-la.md"


def _capture(fn):
    """Run a cmd_* function that prints, and return (text, error)."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            fn()
        return buf.getvalue(), None
    except SystemExit:
        # act807/dnc use exit codes to signal a closed gate; that is data,
        # not a crash. Keep whatever was printed before the exit.
        return buf.getvalue(), None
    except Exception as e:
        return buf.getvalue(), f"{type(e).__name__}: {e}"


def dnc_gate():
    import dnc
    text, err = _capture(dnc.cmd_status)
    if err:
        return {"gate": "ERROR", "open": False, "detail": err, "raw": text}
    open_ = "Scrub gate: 🟢 OPEN" in text
    return {
        "gate": "OPEN" if open_ else "CLOSED",
        "open": open_,
        "detail": ("registries loaded, scrub active" if open_ else
                   "FTC National and/or Louisiana PSC registry not loaded - "
                   "all live calls to non-consenting parties blocked"),
        "raw": text.strip(),
    }


def act807_gate():
    try:
        import act807
    except Exception as e:
        return {"gate": "ERROR", "open": False, "detail": str(e), "raw": ""}
    fn = getattr(act807, "cmd_check", None) or getattr(act807, "main", None)
    if fn is None:
        return {"gate": "ERROR", "open": False,
                "detail": "act807 exposes no cmd_check/main", "raw": ""}
    argv = sys.argv[:]
    sys.argv = ["act807.py", "--check"]
    try:
        text, err = _capture(fn)
    finally:
        sys.argv = argv
    if err:
        return {"gate": "ERROR", "open": False, "detail": err, "raw": text}
    open_ = "**Gate:** 🟢 OPEN" in text or "Gate: 🟢 OPEN" in text
    detail = "counsel-approved"
    if not open_:
        detail = "control profile not counsel-approved"
        if "CONFLICT" in text:
            detail += "; unresolved cancellation_days conflict (5 vs 14)"
    return {
        "gate": "OPEN" if open_ else "CLOSED",
        "open": open_,
        "detail": detail,
        "raw": text.strip(),
    }


def script_gate():
    if not SCRIPT_GATE_FILE.exists():
        return {"gate": "ERROR", "open": False,
                "detail": "call-script.md missing", "status_line": None}
    status = ""
    for line in SCRIPT_GATE_FILE.read_text().splitlines():
        if line.strip().startswith("**Status:") or line.strip().startswith("Status:"):
            status = line.strip()
            break
    open_ = "✅ APPROVED" in status
    return {
        "gate": "OPEN" if open_ else "CLOSED",
        "open": open_,
        "detail": ("operator-approved" if open_ else
                   "not operator-approved; production calls refused. The "
                   "--self-test carve-out still permits consented test calls "
                   "and that is expected, not a bypass."),
        "status_line": status,
    }


def cost_table():
    if not COSTS_FILE.exists():
        return {"gate": "ERROR", "open": False, "detail": "costs-la.md missing"}
    text = COSTS_FILE.read_text()
    testing = bool(re.search(r"\bTESTING\b", text))
    return {
        "gate": "TESTING" if testing else "OK",
        "open": not testing,
        "detail": ("synthetic figures - every number derived from this table "
                   "must carry the TESTING label into the brief"
                   if testing else "operator-supplied figures"),
    }


def build():
    gates = {
        "dnc_scrub": dnc_gate(),
        "act807": act807_gate(),
        "call_script": script_gate(),
        "cost_table": cost_table(),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "src/gate_status.py",
        "all_clear": all(g.get("open") for g in gates.values()),
        "gates": gates,
    }


ICON = {"OPEN": "🟢", "CLOSED": "🔴", "TESTING": "🟡", "OK": "🟢", "ERROR": "⚠️"}


def render(snap):
    ts = snap["generated_at"]
    out = [
        "# Gate Status Snapshot",
        "",
        f"**Generated:** {ts}",
        "**Source:** `src/gate_status.py`, run on the host by cron.",
        "",
        "The briefing agent cannot run these checks itself (`exec` denied by",
        "config). This file is the substitute. **If this file is missing or its",
        "timestamp is over 24h old, report the gates as UNKNOWN - never as",
        "clear.**",
        "",
    ]
    if snap["all_clear"]:
        out.append("**All gates clear.**")
    else:
        out.append("| Gate | State | Detail |")
        out.append("| --- | --- | --- |")
        for name, g in snap["gates"].items():
            icon = ICON.get(g["gate"], "")
            detail = (g.get("detail") or "").replace("\n", " ")
            out.append(f"| `{name}` | {icon} {g['gate']} | {detail} |")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="do_print", action="store_true")
    args = ap.parse_args()

    snap = build()
    INBOX.mkdir(parents=True, exist_ok=True)
    md = render(snap)

    (INBOX / "gate-status.json").write_text(json.dumps(snap, indent=2) + "\n")
    (INBOX / "gate-status.md").write_text(md)

    if args.do_print:
        print(md)
    else:
        state = "ALL CLEAR" if snap["all_clear"] else "GATES CLOSED"
        print(f"gate-status written ({state}) -> {INBOX}/gate-status.md")


if __name__ == "__main__":
    main()
