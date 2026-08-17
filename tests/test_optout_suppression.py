"""Verify an opt-out reaches BOTH local stores, even with GHL unavailable."""
import os, sys, json, tempfile, pathlib

sys.path.insert(0, "/opt/freshslate/src")
tmp = tempfile.mkdtemp()

import dnc, dialer, webhook_server

# Redirect both stores; the real internal-dnc.jsonl is append-only and permanent.
dnc.DNC_DIR = pathlib.Path(tmp)
dnc.INTERNAL_LIST = pathlib.Path(tmp) / "internal-dnc.jsonl"
dialer.SUPPRESSION = os.path.join(tmp, "suppression-list.txt")
webhook_server.LOG_DIR = os.path.join(tmp, "calls")

NUM = "+15045550142"

payload = {
    "event": "call_analyzed",
    "call": {
        "call_id": "test_call_001",
        "to_number": NUM,
        "transcript": "Agent: Hi, calling about a property.\n"
                      "User: Take me off your list and do not call me again.",
        "call_analysis": {"call_summary": "Consumer requested no further contact.",
                          "custom_analysis_data": {"contact_type": "realtor"}},
        "retell_llm_dynamic_variables": {"contact_type": "realtor"},
    },
}

# ghl=None simulates the CRM being down - the case that used to drop the opt-out.
result = webhook_server.process_call_event(payload, ghl=None)

print("outcome :", result["outcome"])
print("opt_out :", result["opt_out"])
print("actions :", result["actions"])

txt = os.path.join(tmp, "suppression-list.txt")
in_txt = os.path.exists(txt) and NUM in open(txt).read()
# dnc.py stores bare 10-digit NANP, not E.164 - compare in its own format.
in_jsonl = (dnc.INTERNAL_LIST.exists()
            and dnc.normalize(NUM) in dnc.INTERNAL_LIST.read_text())
print("\nin suppression-list.txt :", in_txt)
print("in internal-dnc.jsonl   :", in_jsonl)

# The union read is what dialer.py scrubs against on every dial.
blocked = NUM in dialer.load_suppression()
print("dialer would block it   :", blocked)

assert result["opt_out"], "opt-out not detected"
assert "suppressed_local" in result["actions"], "local suppression not recorded"
assert in_txt and in_jsonl, "opt-out missing from a store"
assert blocked, "dialer would still dial an opted-out number"
print("\nPASS - opt-out persisted to both stores with GHL unavailable")

# Regression guard: an entry that exists ONLY in dnc.py's store must still
# block a dial. This is the cross-format case that silently failed before.
only_dnc = "+15045550199"
dnc.add_internal(only_dnc, reason="registered via dnc.py only", source="test")
assert only_dnc in dialer.load_suppression(), \
    "number in internal-dnc.jsonl is not blocked by the dialer (format mismatch)"
print("PASS - dnc.py-only entry is honoured by the dialer")
