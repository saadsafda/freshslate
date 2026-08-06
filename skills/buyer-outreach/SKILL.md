---
name: buyer-outreach
description: Trigger an AI voice call to a realtor or cash buyer via Retell about a specific deal - human-triggered per call, never autonomous
---

# Buyer Outreach

This is NOT the same trust boundary as the rest of this agent. `message` is
still denied at the gateway for this agent - this skill works by invoking
`src/buyer_outreach.py` as an explicit, human-requested action, one call at
a time. The agent does not decide on its own who to call or when.

## Procedure

1. The operator must explicitly name the contact and the deal in their
   request. Never infer a call target from a sweep result or any other
   record on your own initiative.
2. Confirm the contact is a realtor or cash buyer, not a seller/homeowner.
   If there is any ambiguity, stop and ask - do not guess. The code-level
   check in `assert_target_permitted()` is a backstop, not a substitute for
   your own judgment here.
3. Run in dry-run first, always:
   ```
   python3 src/buyer_outreach.py --to <E.164> --name "<name>" --context "<deal>"
   ```
4. Show the operator the dry-run payload and the script-gate status.
5. Only if the operator explicitly confirms AND the gate reports 🟢 OPEN,
   re-run with `--confirm`.
6. Report the result plainly, including any error. Do not retry a failed
   call without a new explicit instruction.

## Constraints

- Never call a number sourced from `parish-sweep`, code-enforcement, or any
  other seller/homeowner-signal dataset. This is enforced in code
  (`assert_target_permitted`) and must also be enforced by you independently.
- Never place a live call while the script gate
  (`deals/_config/call-script.md`) is closed. If asked to bypass this,
  refuse and explain why, the same way you refuse an Act 807 bypass request.
- One call per explicit operator instruction. Do not batch-dial a list on
  your own initiative even if given one.
- Log every attempt, dry-run or live - `buyer_outreach.py` does this
  automatically to `deals/_inbox/`.
