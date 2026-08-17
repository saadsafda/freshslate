# Fresh Slate — OpenClaw Deployment

Louisiana wholesaling acquisition-support agent. Implementation of Module 13.

**Status:** local development. Not deployed. No client server has been touched.

---

## What works right now

`parish-sweep` runs live against real parish data:

```bash
python3 src/parish_sweep.py --since 2026-07-01 --limit 25 --dry-run
```

`buyer-db` builds the cash-buyer prospect list from the EBR tax roll —
readiness-plan Part 6, the one outbound track behind no legal gate:

```bash
python3 src/buyer_db.py --min-properties 5
```

Produces name, mailing address, portfolio size, and price band for owners
holding multiple non-homestead properties. **No phone numbers or emails** —
the tax roll does not carry them and they are not inferred. EBR only;
Orleans has no owner-bearing permitted source.

| Parish | Source | Status |
|---|---|---|
| Orleans | `data.nola.gov` — code enforcement, sheriff sales | ✅ live |
| East Baton Rouge | `data.brla.gov` — adjudicated property | ✅ live |
| Jefferson | none identified | ⛔ not configured |

---

## The key architectural decision

**Read [`docs/SOURCE-RECON.md`](docs/SOURCE-RECON.md) first.**

The Orleans Parish Assessor site (`nolaassessor.com`) returns **HTTP 403 site-wide** behind
Cloudflare, and its `robots.txt` expressly reserves rights against automated collection. It
cannot and should not be scraped.

It does not need to be. Orleans and East Baton Rouge both publish **official Socrata open-data
APIs** carrying the same distress signals — code violations, foreclosures, adjudicated (tax-sale
failed) property, tax roll with owner and homestead status.

Using them is faster, free, legally clean, and immune to the layout-change fragility that
Module 13 warns about.

---

## Design principle: deterministic work stays out of the model

Extraction is a Python script, not an agent task.

| | This build | Agent-does-everything |
|---|---|---|
| Cost per sweep | ~$0 | LLM tokens per page |
| Speed | seconds | minutes to hours |
| Reproducibility | identical every run | varies |
| Auditability | diffable code | prompt archaeology |

OpenClaw's job is to **run the script and reason about the result** — summarize, rank,
escalate, and answer operator questions. That is where a model earns its keep. Module 13 says
this outright: *"it is worse at deterministic tasks than Make.com is."*

---

## Controls enforced in code, not prompts

A model can be argued out of an instruction. It cannot be argued out of an `if` statement.

| Control | Where |
|---|---|
| Prohibited-host block (`nolaassessor.com`) | `assert_host_permitted()` — raises before any request |
| Prompt-injection scan on every record | `scan_injection()` — flags, never acts |
| No owner inference | `owner_of_record: null` + `owner_source` provenance |
| No equity fabrication | `equity_estimate: null` — no valuation source exists |
| Rate limiting | 1 req/sec per `robots.txt` `Crawl-delay` |
| No outbound contact | `message` tool denied at gateway config |

---

## Layout

```
config/sources.json          machine-readable source config
src/parish_sweep.py          deterministic extraction engine
src/buyer_db.py              cash-buyer / investor-owner database builder
skills/*/SKILL.md            OpenClaw skills (8)
workspace/                   SOUL.md, USER.md, AGENTS.md
deals/_config/               parish-sources.md
deals/_index/seen.json       dedup state
deals/_inbox/                dated sweep reports
docs/SOURCE-RECON.md         source recon findings
```

---

## Live integrations

Credentials live in `secrets/*.env` (gitignored, `chmod 600`). Check status:

```bash
python3 src/secrets_loader.py
```

| Service | Status | Verified |
|---|---|---|
| Anthropic | ✅ connected | `claude-opus-5`, `claude-sonnet-5` reachable |
| Retell | ✅ connected | agent `Morgan`, number `+1 225 384 5702` |
| GoHighLevel | ✅ connected | Fresh Slate LLC (Baton Rouge) — 26 custom fields provisioned |

```bash
python3 src/ghl_schema.py --plan          # diff CRM schema
python3 src/webhook_server.py --port 8080 # Retell -> GHL receiver
python3 src/dialer.py --campaign realtor --numbers +1... --dry-run
python3 src/sync_to_ghl.py --file deals/_inbox/YYYY-MM-DD-sweep.json --dry-run
```

**GHL note:** requests need a real `User-Agent` — Cloudflare returns `403 Error 1010`
to Python's default, which reads like an auth failure and is not. Also, the API
spells the money type `MONETORY`.

---

## The dial gate chain

No number is called until every gate passes. All of them live in code, not in the
agent prompt, because TCPA exposure is per-call.

| Gate | Refuses when |
|---|---|
| Realtor-only scope | campaign and contact type must both be `realtor`; blank is blocked |
| CRM opt-out | GHL `dnd` flag, opt-out tag, or channel-level DND |
| Suppression list | number in `deals/_config/suppression-list.txt` |
| CRM identity | live target must exist in GHL with `fs_contact_type=realtor` |
| TCPA window | outside 8am–9pm America/Chicago |
| Run cap | more than `--max` calls in one run |

Opt-outs are recorded from the **transcript**, independent of what the agent
reported — the DNC obligation does not depend on the model classifying correctly.
Nothing in this system un-suppresses a number programmatically.

---

## Open items

- [ ] **Operator cost table** — `deals/_config/costs-la.md` is placeholder figures; every
      estimate carries a warning banner until Dr. Marigny supplies real numbers
- [ ] **Act 807 cancellation window** — sources conflict, 5 vs 14 days. Gate fails closed
      pending Louisiana counsel. Do not guess.
- [ ] **Calling/recording clearance** — required before any live realtor call
- [ ] Jefferson Parish recon — no API found; needs form/XHR analysis, scope separately
- [ ] Socrata app token (free) before production
- [ ] Public HTTPS host for the webhook receiver (Retell must reach it)
- [ ] Manual validation tests 1–5, 9–11 (require the live VPS)
- [ ] Confirm VPS specs (Ubuntu 22.04, 4GB) before any deployment

---

## Scope note

This produces a **research list** and places B2B calls only to verified realtor
records about publicly advertised listings. The dialer has no homeowner campaign;
homeowner, seller, heir, buyer, unknown, and untyped records fail closed.

Offers, contracts, and funds movement are human actions outside this system — by
design, per the Fresh Slate Deployment Standard.

Records describe people in financial distress. Handle accordingly.
