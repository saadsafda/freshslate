---
name: closing-watch
description: Monitor active contracts for missing documents and approaching deadlines, and alert the operator
---

# Closing Watch

## Procedure

For each deal in `deals/_active/`, verify against its checklist:

- [ ] Executed PSA with all required signatures
- [ ] EMD receipt from the neutral escrow holder
- [ ] Title/notary package acknowledgment
- [ ] Buyer proof of funds
- [ ] Executed assignment agreement
- [ ] Seller ID confirmation
- [ ] Preliminary settlement statement with the assignment fee line itemized

**Succession deals additionally:**
- [ ] Signature block for every heir identified in `succession-map.md`
- [ ] Attorney sign-off that the heir list is complete

**Act 807 (once counsel approves the control profile):**
- [ ] Seller cancellation period elapsed, or cancellation right acknowledged
- [ ] Mandatory cancellation form delivered
- [ ] Deposit meets the statutory minimum and is properly held

## Alert schedule

| Trigger | Action |
|---|---|
| T-7 days | Any missing item |
| T-5 days | Buyer POF still absent |
| T-3 days | Any missing item — escalate priority |
| T-48 hours | Settlement statement audit — confirm the fee line is present and the amount is correct |

## Constraints

- **Alert the operator only. Never contact the title company, notary, seller, or buyer.** Not to
  chase a document, not to confirm a date. Draft the message if asked; a human sends it.
- If a deadline has already passed, say so plainly and immediately. Do not soften it.
- If a deal folder is missing its checklist or key dates, report that as a finding rather than
  assuming the deal is fine.
- Do not compute a cancellation deadline from `deals/_config/act-807-controls.md` unless counsel
  has approved that file. The cancellation period is currently unresolved (sources conflict
  between 5 and 14 days) — an alert computed from the wrong number is worse than no alert.
