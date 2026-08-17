# GHL Pipelines — Stage Gates

**Account:** Fresh Slate LLC (Baton Rouge) · **Provisioned:** 2026-08-17

Two pipelines, because a seller deal and a buyer relationship move through
genuinely different states. Forcing both onto one board produces a column that
means different things depending on which record you're looking at.

| Pipeline | ID | Stages |
|---|---|---|
| Fresh Slate — Seller Acquisition | `EtNdM32kSjHfny7ngTMg` | 11 |
| Fresh Slate — Buyer / Disposition | `dTzhxCox2ROpeS4b3eyT` | 8 |

The default **Marketing Pipeline** was left untouched. Delete it in the UI once
anything you care about has been migrated.

> The CRM stores stage *names*. It does not store the rules for moving between
> them — that is this document. Recreate stages with `python3 src/ghl_pipelines.py --apply`.

---

## Seller Acquisition

### 1. Signal Identified
Distress signal found by the parish sweep. **No contact attempted.**

- **Enter:** record imported from a sweep, tagged `freshslate-homeowner`
- **Required:** `fs_parcel_id`, `fs_situs_address`, `fs_signal_type`, `fs_source_url`, `fs_retrieved_at`
- **Exit:** parcel and situs address confirmed against the source

### 2. Research / Underwriting
Repair scope and MAO being prepared. **Still no seller contact.**

- **Required:** `fs_arv`, `fs_repair_estimate`, `fs_mao_base`, `fs_underwrite_status`
- **Exit:** MAO computed from an **operator-approved** cost table, presented as a range

> ⛔ Blocked while `costs-la.md` is unapproved — estimates carry a TESTING banner
> and must not support a real offer. See [COST-INTAKE.md](COST-INTAKE.md).

### 3. Owner Contact Attempted
A **human** has attempted contact.

- **Required:** `fs_consent_basis`, `fs_dnc_checked_at`, `fs_dnc_status = clear`
- **Exit:** owner reached, or attempts exhausted per policy

> ⛔ Homeowner calling requires DNC scrubbing and A2P registration. The dialer
> refuses a homeowner campaign without `--dnc-verified`. Not cleared as of
> 2026-08-17.

### 4. Conversation / Qualifying
Owner engaged. Motivation, timeline, and title questions open.

- **Watch for:** succession/heirs, attorney mentions, distress → escalate to human
- **Exit:** seller indicates willingness to consider an offer

### 5. Offer Presented
Written offer delivered **by a human**. Never by the agent.

- **Exit:** seller accepts, counters, or declines

### 6. Act 807 Compliance Gate 🛑
**Hard gate.** Every requirement satisfied and evidenced **before** any contract
is signed.

| Requirement | Field |
|---|---|
| Written disclosure before execution | `fs_act807_gate` |
| Wholesaling intent + financial gain disclosed | `fs_act807_notes` |
| Seller advised to seek legal advice | `fs_act807_notes` |
| Cancellation form provided | `fs_act807_notes` |
| Prescribed notice near signature | `fs_act807_notes` |
| Deposit ≥ 1% of purchase price | `fs_act807_notes` |
| Louisiana escrow / seller account | `fs_act807_notes` |

- **Exit:** `fs_act807_gate = open` — set by a **human after counsel review**, never automatically

> ⛔ **Unresolved:** the cancellation window is **5 vs 14 days** depending on
> source. `src/act807.py` fails closed and surfaces the conflict. A wrong number
> here makes every contract voidable. Needs a Louisiana attorney.

### 7. Under Contract
PSA executed. **The cancellation period is running.**

- **Exit:** cancellation window elapsed without rescission

> This is deliberately *not* the last stage. A board that shows a deal as done
> during a live cancellation window teaches the wrong instinct.

### 8. Cancellation Period Elapsed
Statutory right to cancel has expired.

- **Exit:** confirmed in writing; deposit and escrow in order

### 9. Assigned / Marketing to Buyers
Marketing the **equitable interest in the contract** — never the property itself.

- **Required:** all copy passes `compliance-gate` before it goes out
- **Exit:** assignment agreement executed with an end buyer

> Marketing the property rather than your interest is the LREC licensing line.
> R.S. 37:1459. Over-flag: a false positive costs a minute.

### 10. Closed — Assigned
Assignment fee collected. Terminal.

### 11. Dead / Lost
Did not proceed. Record the reason — dead deals are the training data for the
next hundred.

---

## Buyer / Disposition

| # | Stage | Exit criterion |
|---|---|---|
| 1 | Identified | Entity resolved; duplicate LLCs merged to **one** buyer |
| 2 | Contact Attempted | Buyer responds |
| 3 | Qualifying | Parishes, price ceiling, rehab appetite captured |
| 4 | Buy Box Confirmed | Buyer receives a matching deal |
| 5 | Active — Deal Sent | Buyer commits or passes |
| 6 | Under Contract w/ Buyer | Closing completes |
| 7 | Closed — Repeat Buyer | Terminal (recurring) — priority list |
| 8 | Inactive / Unqualified | Terminal |

**Stage 1 matters more than it looks.** Ten LLCs sharing a registered agent are
one buyer, not ten. Merging them before outreach is what stops you emailing the
same person ten times on day one.

---

## Rules that apply to every stage

**Opt-out overrides everything.** A contact with `dnd = true` or a
`freshslate-do-not-call` tag is suppressed regardless of stage. Nothing in this
system un-suppresses a number programmatically.

**Contact type is immutable.** `fs_contact_type` is `realtor`, `homeowner`, or
`buyer`. The dialer refuses cross-campaign calls on this field. Never edit it to
move a record into a different campaign — create a new record instead.

**The agent never advances a stage past 5.** Offers, contracts, compliance
sign-off, and assignment are human decisions. The agent drafts and prepares; a
human moves the card.

**Provenance is not optional.** `fs_source_url` and `fs_retrieved_at` travel with
the record to closing. When someone asks where a lead came from, the answer is on
the card.

---

## Rebuilding

```bash
python3 src/ghl_pipelines.py --plan    # diff against the live account
python3 src/ghl_pipelines.py --apply   # create anything missing
```

Idempotent and additive — existing pipelines are skipped by name, never renamed
or deleted. Stage *definitions* live in `src/ghl_pipelines.py`; the rules for
moving between them live here.
