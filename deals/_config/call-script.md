# Buyer/Realtor Call Script — Approval Gate

**Status: ⛔ UNAPPROVED — NOT CONFIGURED. GATE FAILS CLOSED.**

`src/buyer_outreach.py` reads this file before placing any call. If `Status`
above is not exactly `✅ APPROVED`, every call attempt is refused — dry-run
only, regardless of any other flag.

This is not a bug to work around. See `deals/_config/act-807-controls.md`
for why this pattern exists.

---

## Required before this gate can open

- [ ] **Call purpose confirmed** — what is this call for? (new-deal
      notification / POF verification / relationship-building / other).
      Different purposes carry different disclosure requirements.
- [ ] **Target list confirmed** — realtors and cash buyers only, per the
      operator's own standing rule ("call only realtors, not individuals").
      No number from a parish-sweep or code-enforcement source may enter
      this list. `assert_target_permitted()` in code enforces this
      independently of this checkbox — see `src/buyer_outreach.py`.
- [ ] **Script text approved by the operator (your client), verbatim**,
      pasted below — not paraphrased, not drafted-and-assumed.
- [ ] **AI disclosure line confirmed present** in the script — the call
      must identify itself as an AI within the opening seconds. Run the
      script through `compliance-gate` before approval.
- [ ] **Retell agent built and pointed at the approved script** — as of
      2026-08-06 the Retell account has **zero agents configured**. This
      must exist and match the text below before the gate opens.
- [ ] **Twilio (if used) A2P/number registration complete**, or confirmed
      using Retell-native number provisioning instead.
- [ ] **Operator has explicitly set `Status: ✅ APPROVED` above**, dated and
      initialed in the line below.

## Approved script text

_(none yet — paste the exact, final, operator-approved words here once set)_

## Approval record

_(none yet — e.g. "Approved by H. Marigny, 2026-08-14, script v1")_
