# Act 807 Control Profile — Louisiana Wholesaling

**Status: ⛔ UNVERIFIED — NOT COUNSEL-APPROVED. GATES FAIL CLOSED.**

**Statute:** La. R.S. 37:1448.5, enacted by Act 807 (HB 468, 2026 Regular Session)
**Effective:** August 1, 2026
**Counsel of record:** [TBD]
**Approved by:** _nobody_

---

## ⚠️ Read this before using any value below

The parameters in this file are **UNVERIFIED**. They were drawn from secondary sources —
a client email and web summaries — **not** from the statutory text.

**A material conflict was found in those sources:**

| Source | Cancellation period |
|---|---|
| RAE email (2026-08-04) | **five** calendar days |
| Web summary of enrolled bill | **fourteen** calendar days |

These cannot both be right. Getting this wrong makes a contract **voidable at the seller's sole
discretion until title transfers**, with penalties reported up to **$5,000 per violation**.

An attempt to retrieve the enrolled text from `legis.la.gov` on 2026-08-05 failed (host
unreachable). **No value in this file has been confirmed against primary source.**

Until Louisiana counsel supplies and signs off on each value, `compliance-gate` and
`contract-audit` **must refuse to pass any contract** and must say why.

---

## Parameters — ALL UNVERIFIED

| Parameter | Value | Status |
|---|---|---|
| `cancellation_days` | **CONFLICT: 5 vs 14** | ⛔ must be resolved by counsel |
| `cancellation_notice_text` | [TBD] | ⛔ exact prescribed wording required |
| `deposit_minimum_pct` | 1% of purchase price (reported) | ⛔ unverified |
| `escrow_requirement` | Louisiana escrow or seller account (reported) | ⛔ unverified |
| `wholesaling_intent_disclosure` | required, prominent | ⛔ exact wording unverified |
| `legal_advice_advisory` | required | ⛔ exact wording unverified |
| `notice_placement` | near seller's signature | ⛔ unverified |
| `mandatory_cancellation_form` | required | ⛔ form not obtained |
| `penalty_per_violation` | up to $5,000 (reported) | ⛔ unverified |
| `contract_voidability` | voidable until title transfer, seller's discretion | ⛔ unverified |

---

## Reported requirements (secondary sources only)

Treat as a research checklist for counsel, **not** as rules to enforce:

1. Written disclosure before execution
2. Disclosure of wholesaling intent and intent to profit from assignment
3. Advisory that the seller should seek legal advice before signing
4. Seller right to cancel for any reason, without penalty, for at least [N] calendar days
   after execution by seller or wholesaler, **whichever is later**
5. Prescribed notice near the seller's signature, reported as:
   `"NOTICE REQUIRED BY LOUISIANA LAW: You may cancel this contract at any time before
   11:59 PM of [Insert Date]"` — **exact wording must be confirmed**
6. A mandatory cancellation form
7. Deposit of at least 1% of purchase price
8. Louisiana escrow or seller-account requirement
9. Prohibited representations that the wholesaler advises or represents the seller
10. Contract voidable for any omission

---

## How to approve this file

1. Louisiana counsel obtains the enrolled text of Act 807 / La. R.S. 37:1448.5 and the LREC
   mandatory forms.
2. Counsel fills in each parameter with the statutory value and cites the subsection.
3. Counsel sets the status line to `APPROVED BY [name], [bar number] ON [date]`.
4. Re-run `python3 src/act807.py --check` to confirm the gate opens.

**Do not approve this file yourself.** Neither the developer nor the operator can approve a
legal control profile. Module 13: *"It flags issues; counsel resolves them."*

---

## Change triggers

Reassess whenever: the statute is amended, LREC issues or revises forms or guidance, a court
interprets any provision, or the operator begins working in a new jurisdiction.
