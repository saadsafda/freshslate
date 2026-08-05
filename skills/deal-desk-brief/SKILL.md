---
name: deal-desk-brief
description: Produce the 7:00 AM operator briefing covering new leads, active deals, deadline risk, and required decisions
---

# Deal Desk Brief

## Structure

**1. DECISIONS NEEDED TODAY** — anything requiring operator action, with its deadline
**2. DEADLINE RISK** — contracts with due diligence, financing, or closing dates inside 7 days;
   flag anything with a missing document
**3. NEW SIGNALS** — top 5 from the overnight sweep, ranked, one line each
**4. ACTIVE PIPELINE** — one line per deal: address, stage, next action, owner
**5. STALLED** — anything with no movement in 5+ days

## Sources

- Overnight sweep: `deals/_inbox/YYYY-MM-DD-sweep.md`
- Active deals: `deals/_active/`
- Run `closing-watch` for deadline data rather than recomputing it

## Constraints

- **Maximum 400 words.** This is a briefing, not a report.
- **Lead with decisions.** Never bury a deadline below a lead list.
- Link to deal files rather than pasting their contents.
- Carry forward any warning attached to a number. If an estimate came from the TESTING cost
  table or was flagged THIN EVIDENCE, that label travels with it into the brief. A number that
  arrives in a briefing without its caveat reads as settled fact.
- If the overnight sweep failed or a source errored, **say so at the top.** An empty NEW SIGNALS
  section because the sweep crashed looks identical to a quiet night. Those are very different
  situations.
- Report content flags from the sweep immediately, above everything else.
