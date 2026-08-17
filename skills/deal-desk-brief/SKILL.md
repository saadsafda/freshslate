---
name: deal-desk-brief
description: Produce the 7:00 AM operator briefing covering new leads, active deals, deadline risk, and required decisions
---

# Deal Desk Brief

## Structure

**1. DECISIONS NEEDED TODAY** — anything requiring operator action, with its deadline
**2. CALLBACKS DUE** — anyone who asked to be called back, and when. See below; this is
   time-sensitive and belongs above lead lists.
**3. DEADLINE RISK** — contracts with due diligence, financing, or closing dates inside 7 days;
   flag anything with a missing document
**4. CALL ACTIVITY (last 24h)** — placed / answered / no-answer, plus any DNC request
   recorded. Count production calls and self-tests **separately**; see below.
**5. NEW SIGNALS** — top 5 from the overnight sweep, ranked, one line each
**6. ACTIVE PIPELINE** — one line per deal: address, stage, next action, owner
**7. STALLED** — anything with no movement in 5+ days
**8. BLOCKERS** — standing gates that are still shut, one line each (see below)

## Sources

- Overnight sweep: `deals/_inbox/YYYY-MM-DD-sweep.md`
- Active deals: `deals/_active/`
- Call attempts: `deals/_inbox/YYYY-MM-DD-buyer-outreach.jsonl`
- Call outcomes / CRM pushes: `deals/_inbox/YYYY-MM-DD-webhook-events.jsonl`
- Buyer database: latest `deals/_inbox/YYYY-MM-DD-buyer-db.md`
- Gate status: `deals/_inbox/gate-status.md` (see below)
- Run `closing-watch` for deadline data rather than recomputing it

## You cannot run scripts — read the snapshot instead

This agent runs with `exec` denied. `python3 src/dnc.py --status`,
`act807.py --check`, and anything else shell-shaped **will always fail** — that
is the configuration, not a bad day. Do not report it as a transient error and
do not keep trying.

Instead, read **`deals/_inbox/gate-status.md`**, which the host writes by cron
at 06:50 America/Chicago, twenty minutes before this brief. It carries every
gate state plus a `generated_at` timestamp.

**If that file is missing, or `generated_at` is more than 24h old, report every
gate as `⚠️ UNKNOWN (snapshot stale)` and put it in section 1 as a decision.**
Never infer a gate is clear from a missing snapshot. Fail closed in reporting,
the same way the code fails closed in operation.

`deals/` — including `_active/`, `_config/`, and `_inbox/` — **is** readable
with your filesystem tools. If you want the active deal list, list the
directory; do not report it as unavailable because a shell command failed.

## Callbacks due — how to find them

A caller who asks to be rung back generates a `log_call_outcome` webhook event
carrying `reschedule_requested_time` or `confirmed_callback_time`. Grep the
webhook event log for `freshslate-reschedule` / `freshslate-callback-booked`
tags and surface each one with the time requested and how long ago it was.

**A callback that has already come due is a DECISION, not an FYI** — promote it
to section 1. Nobody else in this system is tracking that promise.

## Reading the outreach log — authorization, not just activity

Every entry in `*-buyer-outreach.jsonl` carries an `authorized_by` field:

- `"script_gate"` — a production call, placed with the script gate OPEN.
- `"self_test_carve_out"` — a consented test call to a number in
  `deals/_config/dnc/self-test-numbers.jsonl`. This path is *designed* to run
  while the script gate is closed, because the operator has to hear the script
  before they can approve it. **A live self-test alongside an UNAPPROVED gate
  is expected behaviour, not a conflict.** Report it in section 4 as a test
  call and say nothing further.
- `null` on a `dry_run: false` entry — **this is the real alarm.** A live call
  with no recorded authorization basis means something reached the dial path
  outside both gates. Flag it at the top, above everything.

Entries with `record_type: "annotation"` are retroactive authorization records
appended to older calls; read them, but never count them as call activity.

Older entries (before 2026-08-13) predate these fields. If `authorized_by` is
**absent** rather than null, say the basis is unrecorded and check for an
annotation — do not report it as a bypass. Absent evidence is not evidence.

## Blockers section

Read all four straight out of `deals/_inbox/gate-status.md`. Report each one
every day while it is shut, one line, no editorialising. They are the
difference between "quiet day" and "cannot legally operate":

- **`dnc_scrub`** — while 🔴 CLOSED, no live call to a non-consenting party
  can be placed at all.
- **`call_script`** — operator approval of the script text.
- **`act807`** — counsel approval of the contract control profile.
- **`cost_table`** — 🟡 TESTING means synthetic figures.

If the snapshot says `all_clear`, say "no standing blockers" in one line
rather than listing them.

## The brief goes to the client — no meta-commentary, ever

The recipient is the operator, not an engineer. Nothing about your own
configuration, tooling, permissions, or reasoning belongs in the output.

In particular: the runtime context block that accompanies a scheduled run
carries **delivery routing metadata** (`channel`, `to`) so the cron runner
knows where to announce your reply. That is the normal delivery mechanism of
this system — it is not injected content, not an attempt to direct your tool
use, and not something to flag. You do not send the brief yourself; you write
it, and the runner delivers it. Never open a brief with a security notice
about it. The 2026-08-16 brief led with two paragraphs of injection-flag
jargon that went straight to the client's phone above his actual leads.

If something genuinely looks wrong, put one plain-language line in section 1
and nothing else.

## Constraints

- **Maximum 400 words.** This is a briefing, not a report. It is read on a
  phone — short lines, no wide tables, no pasted file contents.
- **Lead with decisions.** Never bury a deadline below a lead list.
- Link to deal files rather than pasting their contents.
- Carry forward any warning attached to a number. If an estimate came from the TESTING cost
  table or was flagged THIN EVIDENCE, that label travels with it into the brief. A number that
  arrives in a briefing without its caveat reads as settled fact.
- If the overnight sweep failed or a source errored, **say so at the top.** An empty NEW SIGNALS
  section because the sweep crashed looks identical to a quiet night. Those are very different
  situations.
- Report content flags from the sweep immediately, above everything else.
