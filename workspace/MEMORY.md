# Memory

Curated long-term facts. Loads into context every session — **keep it short.** Working notes go
in the daily log (`memory/YYYY-MM-DD.md`), not here.

## ⛔ Never write PII to this file

No owner names, property addresses, phone numbers, email addresses, heir names, or family
details from Succession filings.

Reference deals by ID: `see deal 2026-0042`. The deal folder is scoped, auditable, and
deletable. This file is none of those things — it loads into every context, including sessions
that have nothing to do with that deal, and it persists indefinitely.

The records this operation handles describe people in financial distress. Minimizing where their
information lives is not bureaucracy; it is the reason the deployment is defensible.

## Operating facts

- Parishes live: **Orleans**, **East Baton Rouge**. Jefferson is **not** configured — no
  permitted data source. Do not improvise one.
- `nolaassessor.com` is a **hard block**, enforced in code. Do not attempt access.
- Parish extraction runs via cron at 04:00 → `deals/_inbox/`. The agent reads the output; it
  does not scrape.
- Cost table is **TESTING** (synthetic figures). Every underwrite output carries a banner until
  the operator approves real numbers.
- Act 807 control profile is **UNVERIFIED** — sources conflict on the cancellation period (5 vs
  14 days). The gate is closed until Louisiana counsel resolves it.

## Standing constraints

- The `message` tool is denied. The agent cannot contact anyone.
- Every property fact carries a citation: parish, document type, date, source, timestamp.
- Absent fields are `null` with provenance. Never inferred, never guessed.
- "I could not find it" is always an acceptable answer.

## Deal facts

_(Confirmed facts about active deals go here, by ID only.)_
