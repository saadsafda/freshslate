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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dnc  # noqa: E402  - DNC scrub; see assert_callable() below

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / "secrets" / "retell.env"
SCRIPT_GATE_FILE = REPO_ROOT / "deals" / "_config" / "call-script.md"
CALL_LOG_DIR = REPO_ROOT / "deals" / "_inbox"
CALL_VARS_FILE = REPO_ROOT / "config" / "call-variables.json"

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


def load_call_vars():
    if not CALL_VARS_FILE.exists():
        print(f"FATAL: {CALL_VARS_FILE} not found.", file=sys.stderr)
        sys.exit(1)
    with open(CALL_VARS_FILE) as f:
        return json.load(f)


def build_dynamic_variables(cfg, args):
    """Assemble exactly the variables the Marigny conversation flow references.

    The flow is the contract. If it is edited to use a new {{variable}}, this
    must be updated to match - a variable the flow expects but never receives
    renders as an empty string mid-sentence on a live call, which is worse
    than an error because it still dials.
    """
    return {
        "investor_name": cfg.get("investor_name", ""),
        "parishes": cfg.get("parishes", ""),
        "arv_range": cfg.get("arv_range", ""),
        "close_timeline": cfg.get("close_timeline", ""),
        "street_name": args.street or "",
        "parish": args.parish or "",
        "time_option_a": args.time_a or cfg.get("default_time_option_a", ""),
        "time_option_b": args.time_b or cfg.get("default_time_option_b", ""),
    }


def assert_variables_complete(dv):
    """Refuse rather than dial with a blank in the middle of a spoken line."""
    missing = [k for k, v in dv.items() if not str(v).strip()]
    if missing:
        print("⛔ Refusing: the Marigny flow needs these variables and they are blank:")
        for k in missing:
            hint = {
                "street_name": "pass --street \"Magnolia Street\"",
                "parish": "pass --parish \"Orleans\"",
                "time_option_a": "pass --time-a \"tomorrow at 2pm\" (or set default_time_option_a)",
                "time_option_b": "pass --time-b \"Thursday morning\" (or set default_time_option_b)",
            }.get(k, f"set \"{k}\" in {CALL_VARS_FILE.relative_to(REPO_ROOT)}")
            print(f"   - {k}: {hint}")
        print("\n   Each of these is spoken aloud or used to judge buy-box fit.")
        print("   A blank renders as silence mid-sentence, so this refuses instead.")
        sys.exit(1)


def build_call_payload(env, to_number, dynamic_variables, script_text):
    return {
        "to_number": to_number,
        "from_number": env.get("RETELL_FROM_NUMBER"),  # required by Retell's API - no auto-select
        "override_agent_id": env.get("RETELL_AGENT_ID"),  # must exist; see call-script.md checklist
        "retell_llm_dynamic_variables": dynamic_variables,
        "metadata": {
            "source": "freshslate-buyer-outreach",
            "requested_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def self_test_authorization(to_number):
    """The registry entry that authorized a self-test call, for the audit log.

    Returns None if the number is not registered. The scrub blocks that case
    before we ever reach here, so a None recorded alongside self_test=True
    means something bypassed the scrub - which is worth being able to see.
    """
    try:
        entry = dnc.load_self_test().get(dnc.normalize(to_number))
    except Exception:
        return None
    if not entry:
        return None
    return {
        "relationship": entry.get("relationship"),
        "person": entry.get("person"),
        "attestation": entry.get("attestation"),
        "registered_at": entry.get("added_at"),
    }


def log_call_attempt(to_number, contact_name, dry_run, result, dynamic_variables=None,
                     self_test=False, script_gate_open=None):
    """Contact name is logged separately from the payload: the Marigny flow has
    no contact_name variable (it does not greet by name), but the audit log
    still needs to record who the operator said they were calling.

    `self_test` / `script_gate_open` / `authorized_by` record the *authorization
    basis* for the call, not just the fact of it. Without them, a live call
    logged while the script gate reads UNAPPROVED is indistinguishable from a
    gate bypass - the 2026-08-13 brief flagged exactly that on three consented
    test calls and could not resolve it from the log alone. A compliance log
    that cannot answer "what permitted this call?" is not a compliance log.
    """
    CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = CALL_LOG_DIR / f"{datetime.now(timezone.utc).date()}-buyer-outreach.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "to_number": to_number,
        "contact_name": contact_name,
        "self_test": bool(self_test),
        "script_gate_open": script_gate_open,
        "authorized_by": (
            "script_gate" if script_gate_open
            else "self_test_carve_out" if self_test
            else None
        ),
        "self_test_consent": self_test_authorization(to_number) if self_test else None,
        "dynamic_variables": dynamic_variables,
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
    ap.add_argument("--context", required=True,
                    help="Deal/reason for the call. Recorded in the call log and used by "
                         "assert_target_permitted; not spoken by the agent.")
    ap.add_argument("--street", help="Listing street, spoken in the opening line "
                                     "(flow variable street_name), e.g. \"Magnolia Street\"")
    ap.add_argument("--parish", help="Parish of the property, spoken in the decline/close "
                                     "lines (flow variable parish), e.g. \"Orleans\"")
    ap.add_argument("--time-a", help="First callback slot offered, e.g. \"tomorrow at 2pm\"")
    ap.add_argument("--time-b", help="Second callback slot offered, e.g. \"Thursday morning\"")
    ap.add_argument("--target-role", default="realtor_or_buyer",
                     choices=["realtor_or_buyer"],
                     help="Only realtor_or_buyer is accepted - hard-coded, see assert_target_permitted")
    ap.add_argument("--confirm", action="store_true", help="Actually place the call (else dry-run)")
    ap.add_argument("--self-test", action="store_true",
                    help="Call a number YOU own, registered via `dnc.py --add-self-test`. "
                         "Waives the DNC registries (testing your own line is not "
                         "telemarketing). Does NOT waive internal DNC or calling hours.")
    args = ap.parse_args()

    dry_run = not args.confirm

    try:
        assert_target_permitted(args.name, args.context, args.target_role)
    except PermissionError as e:
        print(f"⛔ {e}")
        sys.exit(1)

    # DNC scrub. Gate 2 of the readiness plan, enforced here rather than
    # trusted to a checklist. On a live call this is strict: an undownloaded
    # registry blocks, because "not checked" is not "not listed". A dry run
    # waives only the registry-presence check so the operator can still see
    # the calling-hours and internal-list results.
    scrub = dnc.check_number(
        args.to,
        allow_unloaded_registries=dry_run and not args.self_test,
        self_test=args.self_test,
    )
    scrub_state = "🟢 CLEAR" if scrub["allowed"] else "⛔ BLOCKED"
    print(f"DNC scrub: {scrub_state}" + ("  [SELF-TEST MODE]" if args.self_test else ""))
    for b in scrub["blocks"]:
        print(f"  ⛔ {b['code']}: {b['reason']}")
    for w in scrub["warnings"]:
        print(f"  ⚠️  {w['code']}: {w['reason']}")
    if not scrub["allowed"]:
        log_call_attempt(
            args.to, args.name, dry_run=dry_run,
            result={"refused_by": "dnc_scrub",
                    "blocks": [b["code"] for b in scrub["blocks"]]},
            self_test=args.self_test,
        )
        print("\n⛔ Refusing: number did not pass the DNC scrub.")
        print("   Run `python3 src/dnc.py --status` for what is missing.")
        sys.exit(1)

    env = load_env()
    is_open, status_line, script_text = check_script_gate()

    print(f"Script gate: {'🟢 OPEN' if is_open else '🔴 CLOSED'} ({status_line})")

    if not dry_run and not is_open and not args.self_test:
        print("⛔ Refusing to place a live call - script gate is closed.")
        print(f"   Fix: get operator approval in {SCRIPT_GATE_FILE.relative_to(REPO_ROOT)}")
        print("   Or, to hear the script on a line you own first:")
        print("     python3 src/dnc.py --add-self-test \"<your number>\" --attest \"...\"")
        print("     python3 src/buyer_outreach.py ... --self-test --confirm")
        sys.exit(1)

    if args.self_test and not is_open:
        # Deliberate: the script gate exists to stop an unapproved script from
        # reaching a third party. A call to a line the operator owns reaches
        # no third party, and is how the operator decides whether to approve
        # in the first place - requiring approval before that test would be
        # circular. Narrow to registered self-test numbers by the scrub above.
        print("ℹ️  Script gate is closed, but this is a registered test call")
        print("   (see the SELF_TEST_MODE line above for who consented and when).")
        print("   Proceeding. This does NOT authorize calling anyone else.")

    cfg = load_call_vars()
    dynamic_variables = build_dynamic_variables(cfg, args)
    assert_variables_complete(dynamic_variables)
    payload = build_call_payload(env, args.to, dynamic_variables, script_text)

    if dry_run:
        print("🔸 DRY RUN - no call placed. Payload that would be sent:")
        print(json.dumps(payload, indent=2))
        log_call_attempt(args.to, args.name, dry_run=True, result="dry_run_only",
                         dynamic_variables=dynamic_variables,
                         self_test=args.self_test, script_gate_open=is_open)
        return

    if not payload.get("override_agent_id"):
        print("⛔ Refusing: no RETELL_AGENT_ID configured in secrets/retell.env.")
        print("   The Retell account currently has zero agents built. Build and")
        print("   approve the agent/script before this can go live.")
        sys.exit(1)

    if not payload.get("from_number"):
        print("⛔ Refusing: no RETELL_FROM_NUMBER configured in secrets/retell.env.")
        print("   Retell requires a number actually purchased/imported in your")
        print("   account - it will not auto-select one. Provision a number in")
        print("   the Retell dashboard (requires a card on file) or via the")
        print("   create-phone-number API, then set RETELL_FROM_NUMBER.")
        sys.exit(1)

    result = place_call(env, payload)
    log_call_attempt(args.to, args.name, dry_run=False, result=result,
                     dynamic_variables=dynamic_variables,
                     self_test=args.self_test, script_gate_open=is_open)
    if result["ok"]:
        print("✅ Call placed.", json.dumps(result["response"], indent=2)[:500])
    else:
        print("❌ Call failed:", result["error"])
        sys.exit(1)


if __name__ == "__main__":
    main()
