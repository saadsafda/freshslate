#!/usr/bin/env python3
"""Retell AI outreach to realtors/cash buyers. Human-triggered, gate-enforced.

Fails closed until deals/_config/call-script.md is marked APPROVED. This
mirrors act807.py's pattern deliberately - see that file for why.

Usage:
    python3 src/buyer_outreach.py --to +15045550100 --name "Jane Realtor" \
        --context "123 Main St, Orleans, $185k ARV" --dry-run
    python3 src/buyer_outreach.py --to +15045550100 --name "Jane Realtor" \
        --context "123 Main St, Orleans, $185k ARV" --confirm
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / "secrets" / "retell.env"
SCRIPT_GATE_FILE = REPO_ROOT / "deals" / "_config" / "call-script.md"
CALL_LOG_DIR = REPO_ROOT / "deals" / "_inbox"

# Hard block, independent of the approval-gate checkbox. A parish-sweep or
# code-enforcement lead number must never reach this module's call path -
# this function is the enforcement, not the checklist item.
PROHIBITED_TARGET_MARKERS = ("seller", "homeowner", "distressed", "code_violation")


def load_env():
    if not ENV_FILE.exists():
        print(f"FATAL: {ENV_FILE} not found.", file=sys.stderr)
        sys.exit(1)
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    if not env.get("RETELL_API_KEY"):
        print("FATAL: RETELL_API_KEY not set in secrets/retell.env.", file=sys.stderr)
        sys.exit(1)
    return env


def assert_target_permitted(name: str, context: str, target_role: str):
    """Enforced in code, not just policy. See SOUL.md / AGENTS.md for why."""
    if target_role != "realtor_or_buyer":
        raise PermissionError(
            "BLOCKED: this module only calls realtors/cash buyers. "
            "Seller/homeowner outreach is not permitted by this system."
        )
    haystack = f"{name} {context}".lower()
    for marker in PROHIBITED_TARGET_MARKERS:
        if marker in haystack:
            raise PermissionError(
                f"BLOCKED: target context contains '{marker}' - looks like a "
                "seller/homeowner lead, not a realtor/buyer. Refusing."
            )


def check_script_gate():
    """Returns (is_open, status_line, approved_script_text)."""
    if not SCRIPT_GATE_FILE.exists():
        return False, "GATE FILE MISSING", None
    text = SCRIPT_GATE_FILE.read_text()
    status_match = re.search(r"\*\*Status:\s*(.+?)\*\*", text)
    status_line = status_match.group(1).strip() if status_match else "UNKNOWN"
    is_open = status_line == "✅ APPROVED"

    script_text = None
    if is_open:
        # Anchored to the two headings this file is known to contain, not a
        # generic "next ## heading" guess - the script text itself may
        # legitimately contain ## headings (e.g. "## Role"), which a
        # naive next-heading match would truncate on silently.
        m = re.search(
            r"## Approved script text\n\n(.+?)\n\n## Approval record",
            text, re.DOTALL,
        )
        if m and "_(none yet" not in m.group(1):
            script_text = m.group(1).strip()
        else:
            is_open = False
            status_line = "APPROVED status set but no script text found - treating as closed"

    return is_open, status_line, script_text


def build_call_payload(env, to_number, name, context, script_text):
    return {
        "to_number": to_number,
        "from_number": env.get("TWILIO_PHONE_NUMBER") or None,  # None -> Retell-native number
        "override_agent_id": env.get("RETELL_AGENT_ID"),  # must exist; see call-script.md checklist
        "retell_llm_dynamic_variables": {
            "contact_name": name,
            "deal_context": context,
        },
        "metadata": {
            "source": "freshslate-buyer-outreach",
            "requested_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def log_call_attempt(payload, dry_run, result):
    CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = CALL_LOG_DIR / f"{datetime.now(timezone.utc).date()}-buyer-outreach.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "to_number": payload["to_number"],
        "contact_name": payload["retell_llm_dynamic_variables"]["contact_name"],
        "result": result,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def place_call(env, payload):
    req = urllib.request.Request(
        "https://api.retellai.com/v2/create-phone-call",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {env['RETELL_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"ok": True, "response": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, help="E.164 phone number, e.g. +15045550100")
    ap.add_argument("--name", required=True)
    ap.add_argument("--context", required=True, help="Deal/reason for the call")
    ap.add_argument("--target-role", default="realtor_or_buyer",
                     choices=["realtor_or_buyer"],
                     help="Only realtor_or_buyer is accepted - hard-coded, see assert_target_permitted")
    ap.add_argument("--confirm", action="store_true", help="Actually place the call (else dry-run)")
    args = ap.parse_args()

    dry_run = not args.confirm

    try:
        assert_target_permitted(args.name, args.context, args.target_role)
    except PermissionError as e:
        print(f"⛔ {e}")
        sys.exit(1)

    env = load_env()
    is_open, status_line, script_text = check_script_gate()

    print(f"Script gate: {'🟢 OPEN' if is_open else '🔴 CLOSED'} ({status_line})")

    if not dry_run and not is_open:
        print("⛔ Refusing to place a live call - script gate is closed.")
        print(f"   Fix: get operator approval in {SCRIPT_GATE_FILE.relative_to(REPO_ROOT)}")
        sys.exit(1)

    payload = build_call_payload(env, args.to, args.name, args.context, script_text)

    if dry_run:
        print("🔸 DRY RUN - no call placed. Payload that would be sent:")
        print(json.dumps(payload, indent=2))
        log_call_attempt(payload, dry_run=True, result="dry_run_only")
        return

    if not payload.get("override_agent_id"):
        print("⛔ Refusing: no RETELL_AGENT_ID configured in secrets/retell.env.")
        print("   The Retell account currently has zero agents built. Build and")
        print("   approve the agent/script before this can go live.")
        sys.exit(1)

    result = place_call(env, payload)
    log_call_attempt(payload, dry_run=False, result=result)
    if result["ok"]:
        print("✅ Call placed.", json.dumps(result["response"], indent=2)[:500])
    else:
        print("❌ Call failed:", result["error"])
        sys.exit(1)


if __name__ == "__main__":
    main()
