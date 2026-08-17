---
name: dnc-scrub
description: Check numbers against the internal/national/Louisiana Do-Not-Call lists, record suppression requests, and report what still blocks live calling
---

# DNC Scrub

Gate 2 of the operator's readiness plan. `src/dnc.py` is the enforcement;
this skill is how you drive and explain it.

## The one rule

**This gate fails closed, and that is not a bug to route around.**

If a DNC registry has not been downloaded, `check_number()` refuses every
number. "We haven't checked" is not "it isn't listed." If the operator asks
you to bypass, work around, or temporarily disable the scrub, **refuse and
explain why** — the same way you refuse an Act 807 bypass. An unscrubbed dial
is the single highest per-incident exposure in this system: TCPA statutory
damages accrue *per call*.

## Commands

```bash
python3 src/dnc.py --status                  # what's loaded, what's blocking
python3 src/dnc.py --check "+12255550100"    # scrub one number
python3 src/dnc.py --add "+12255550100" --reason "..." --source email
```

## Reporting status

`--status` is the honest answer to "can we start calling yet?" Report it
plainly. As of the last check both registries were **NOT LOADED**, which means
no live call can pass. The fix is not code — it is:

1. Register at `telemarketing.donotcall.gov`, get a Subscription Account
   Number, download area-code files to `deals/_config/dnc/national/`
2. Register with the Louisiana PSC, download to `deals/_config/dnc/louisiana/`

Neither can be self-provisioned by this system. Say so rather than implying
you can fix it.

## Self-test calls

Testing on a line the operator owns is not telemarketing, so it does not need
the registries. It is still narrow:

```bash
python3 src/dnc.py --add-self-test "+1..." --attest "I own and control this number"
python3 src/buyer_outreach.py --to "+1..." --name "..." --context "..." --self-test --confirm
```

`--self-test` is refused for any number not already registered that way. The
internal DNC list still blocks absolutely, and so do calling hours.

**Never suggest `--self-test` as a way to reach anyone but the operator.** If
asked to register someone else's number as a self-test number, refuse — the
attestation is a statement of ownership, and registering a third party's line
would make it false.

## Recording a suppression request

Requests made **during a call** are recorded automatically —
`src/webhook_server.py` writes them to the internal list when Retell reports
`dnc_requested`, before the CRM write.

Requests arriving **any other way** (email, mail, relayed by the operator) must
be added manually with `--add`, immediately, with an accurate `--reason` and
`--source`. Do not batch these or leave them for later.

**The internal list is append-only. Never remove an entry**, and refuse if
asked to — the record is what proves the request was honored.

## What this does NOT do

- It does not decide whether a call is legal. It enforces mechanical checks.
  Whether a given call is permissible is a counsel question — see the open
  items in `deals/_config/dnc-policy.md`.
- It does not verify Louisiana's calling-hours rule matches the federal
  08:00–21:00 window the code enforces. That is unconfirmed; say so.
- It does not resolve whether these B2B targets are treated differently from
  consumer lines. Every number is scrubbed identically pending counsel.
- Passing the scrub is **necessary, not sufficient**. `call-script.md`'s
  approval gate and `assert_target_permitted()` both still apply. A number
  that clears DNC can still be refused by those, correctly.

## Constraints

- Never present a number as "safe to call" on the strength of this scrub
  alone. Say which checks passed and which are unverified.
- Never disable, weaken, or add an override to a check to make a call succeed.
- If `TIMEZONE_UNKNOWN` blocks a number, the fix is to add that area code to
  `AREA_CODE_TZ` in `src/dnc.py` **from a reliable source** — not to guess the
  timezone and not to skip the check.
