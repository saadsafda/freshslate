# Property Data Sources — Decision Document

**Date:** 2026-08-05
**Purpose:** Turn the provider survey into a costed decision.

---

## Summary

The survey is correct on the important point: **do not scrape Zillow or Redfin.** Their terms
prohibit it, they enforce it, and their photos are MLS-licensed so they can't be republished in
course material regardless.

It's also correct that *"some counties have APIs."* **Orleans and East Baton Rouge do, and they
are already built and working** — see `docs/SOURCE-RECON.md`. That's the free tier of the
recommended stack, already delivered.

What follows is what to add on top, with real prices.

---

## Layer 1 — Parish open data ✅ BUILT, $0/mo

| Parish | Source | Signals | Status |
|---|---|---|---|
| Orleans | `data.nola.gov` | code violations, sheriff sales | ✅ live |
| East Baton Rouge | `data.brla.gov` | adjudicated property, tax roll | ✅ live |
| Jefferson | none found | — | ⛔ needs recon |

**Answers:** *which properties are distressed?*
**Cannot answer:** who owns Orleans properties (no owner field), what anything is worth.

---

## Layer 2 — Owner and valuation enrichment

This is the gap. Parish data says a property is in trouble; it doesn't say who owns it or what
it's worth.

### Costed options

| Provider | Free tier | Entry paid | Gives us | Verdict |
|---|---|---|---|---|
| **RentCast** | **50 req/mo** | $74/mo (1k), $199 (5k), $449 (25k) | owner, mailing address, `ownerOccupied`, tax assessments, sale history, AVM | ✅ **build now** |
| ATTOM | none | commercial contract | mortgages, liens, pre-foreclosure, AVM | 🟡 integrated, dormant until key |
| CoreLogic | none | enterprise | deepest data | ❌ overkill at this stage |
| Estated | limited | ~$0.10/lookup | parcel, owner, sales | 🟡 alternative to RentCast |
| PropStream / PropertyRadar / BatchLeads | none | ~$99–$199/mo | investor-packaged lead lists | ⚠️ see below |
| MLS / RESO | n/a | membership + broker | active listings | ❌ requires brokerage affiliation |

**Both RentCast and ATTOM are implemented in `src/providers.py` right now.** Neither has a key,
so both self-skip and records keep null fields with provenance. Add a key, enrichment turns on.
Nothing else changes.

### Recommendation

**Start with RentCast's free tier — $0, 50 lookups/month.**

Enough for the seminar and early testing. Enrich only the top-ranked records, never the whole
sweep. `--enrich N` caps it, and the budget ceiling is enforced in code so a runaway loop can't
produce a surprise bill.

Upgrade to Foundation ($74/mo) only when real volume justifies it.

### ⚠️ On PropStream / PropertyRadar / BatchLeads

These bundle skip-tracing — **phone numbers for distressed homeowners**. That is a different
compliance posture entirely: TCPA, the DNC registry, and Louisiana telemarketing law all attach
the moment those numbers exist in the system.

Module 13 already handles this correctly by denying the `message` tool at the architecture
level, so the agent physically cannot dial or text. **Keep that.** If these tools enter the
stack, they should feed a human-operated calling process, never the agent.

---

## Layer 3 — Comps and repair estimation

`underwrite` needs ARV comps and repair costs.

- **Comps:** RentCast provides an AVM and sale comparables on the same key as Layer 2.
- **Repair costs:** must come from the operator. Module 13 is explicit — *"Do NOT use national
  averages."* This is `deals/_config/costs-la.md` and it is **still blocking**.

---

## What we deliberately do not use

| Source | Why not |
|---|---|
| Zillow | Terms prohibit automated access; MLS-licensed photos can't be republished |
| Redfin | Same |
| `nolaassessor.com` | HTTP 403 site-wide; robots.txt expressly reserves rights |
| Google Street View | Google-copyrighted; can't ship in course material |

All four are enforced or documented, not left to judgment. `nolaassessor.com` is a hard block in
code (`assert_host_permitted`) that raises before any request is made.

---

## Honest limits of what we compute

Per the survey's own compliance note — *"If your AI estimates equity, clearly label it as an
estimate"*:

**Equity** is derived as `assessed_value − last_sale_price`. It is **LOW confidence** and
labeled as such on every record. It is not an AVM, it ignores mortgage balances and liens, and
**Louisiana assesses residential property at 10% of fair market value**, so assessed and sale
figures are not directly comparable. It is a triage signal, nothing more.

Module 13's ">40% equity" filter **cannot be computed reliably** from current sources. Saying so
is the correct answer.

**Absentee owner** uses documented fields only, in priority order:
1. `ownerOccupied` from the provider (authoritative)
2. mailing address vs situs address (documented comparison)
3. EBR `homestead_exempt_type == "NO"` (parish field)

If none are available it returns `null`, never a guess.

---

## Recommended stack

| Layer | Choice | Cost |
|---|---|---|
| Distress signals | Parish open data (built) | $0 |
| Owner + valuation | RentCast free tier | $0 |
| Repair costs | Operator's own table | $0 — **blocking** |
| LLM | Claude via OpenClaw | ~$90–150/mo per Module 13 |

**Total to run the seminar demo: the LLM cost only.**

Upgrade path when volume justifies it: RentCast Foundation $74/mo → ATTOM on contract.

---

## Open decisions for the client

1. **Approve RentCast free tier?** Free, no card, 5-minute signup. Needed for owner data on
   Orleans records.
2. **Skip-tracing tools — in or out?** Materially changes compliance posture. Recommend out for
   now.
3. **Jefferson Parish** — fund a separate recon, or ship two parishes?
4. **The cost table** — still the top blocker for `underwrite`.
