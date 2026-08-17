# Fresh Slate — Operational Readiness Plan

Pasted into the project by the operator on 2026-08-10. Source: operator (client-side
planning document, author outside this repo's history — treat as an external
compliance/business input, not something this repo's tooling generated).

This is the authoritative statement of legal gating for SMS, voice, and contracts
work until superseded by actual counsel review. It sits above and motivates the
technical gates already built in this repo (`act807.py`, `call-script.md`,
`buyer_outreach.py`) — those are the code-level enforcement; this document is the
business/legal readiness plan they exist to serve.

Key items directly relevant to code in this repo:

- **Gate 4 (AI voice)** requires Gates 2 (seller contact / DNC / attorney) and 3
  (A2P SMS) cleared first, plus a TCPA attorney review of the *specific* use,
  before any AI voice call goes live — including realtor/buyer calls, not just
  seller calls. Per Part 2's build order, the voice agent itself may be *built
  and self-tested* now (own phone / consenting parties only); it may not call
  real, non-consenting third parties (including realtors sourced from a listing)
  until Gate 4 clears.
- **"Cold-dialing a scraped list" is explicitly listed as "Do not."** The open
  question already flagged in `call-script.md` — where the realtor/buyer dial
  list actually comes from — is not a nice-to-have detail, it's the fact that
  determines whether `buyer_outreach.py` calls are even in-scope for Gate 4 or
  fall under the seller-side DNC/TCPA track instead.
- **Buyer-side email (CAN-SPAM) is the only outbound channel live today** — not
  buyer-side voice. `buyer_outreach.py`'s calling capability stays
  self-test-only until Gate 4, independent of whether `call-script.md`'s
  Status flag is flipped to APPROVED by the operator.
- SMS is out of scope for this repo entirely right now (A2P 10DLC not started);
  nothing here should be built assuming SMS delivery works.

---

## Full text as provided

FRESH SLATE — OPERATIONAL READINESS PLAN
From working AI to working business
Sequenced by what blocks what

### PART 0 — WHERE YOU ACTUALLY STAND

| Component | Status |
|---|---|
| OpenClaw + 4 Louisiana skills | Working, tested |
| Anthropic API | Connected |
| Case Study 001 | Complete |
| Course manuscript + marketing assets | Drafted |
| OpenClaw gateway | Down — CLI only, no Telegram/cron |
| SMS capability | Not registered — cannot legally send |
| Voice outreach | No DNC scrubbing — cannot legally dial |
| Contracts | No attorney review — cannot legally use |
| Parish data pipeline | Not built |
| CRM | Not configured |
| Buyer database | Not built |

Three of those are hard legal blocks. Not "should fix." Cannot proceed.

### PART 1 — THE CRITICAL PATH

The thing that determines your launch date is not the technology. It's the two
registrations and one attorney, all of which have lead times you cannot compress.

- A2P 10DLC registration → 1–4 weeks → SMS unlocked
- DNC subscriptions → 1–3 days → scrubbing possible
- Attorney engagement → 2–4 weeks → contracts usable
- Everything else (build in parallel — no external dependency): parish scrapers,
  CRM configuration, buyer database (live today, no gate), voice agent (build +
  self-test only)

Start the three gated items today, even if you do nothing else.

### PART 2 — TRACK A: SMS (A2P 10DLC)

US carriers require registration for A2P SMS; unregistered traffic is silently
filtered, not bounced. Two-stage process: Brand registration (legal entity vs.
public records — name, EIN, address, website, authorized contact) and Campaign
registration (how consent is obtained). Common rejection traps: no opt-in
mechanism described, website doesn't match campaign, missing/incomplete privacy
policy, sample messages lacking opt-out language, high-risk content categories.

Cold outreach to property owners who never opted in is not a clean A2P use case.
A2P governs carrier delivery; TCPA governs legality, separately. Defensible
structure: SMS as follow-up only after a seller responds; inbound-triggered;
buyer side restricted to buyers who explicitly opted in. Cold contact via direct
mail, door knock, or manually-dialed voice with DNC scrubbing — not automated SMS
blast. The original course material's SMS-blast-to-scraped-lists framing must
change before publication — largest liability in the manuscript.

Actions: confirm entity/EIN match SOS/IRS exactly, publish site with SMS-naming
privacy policy, write opt-in language, submit brand + campaign registration
(describing follow-up use, not cold blast), screenshot every submission as a
compliance file.

### PART 3 — TRACK B: VOICE AND DNC

Needed before dialing anyone: National DNC Registry access, Louisiana state DNC
list (separate registration/list), internal DNC list (permanent, legally
required), written DNC policy, call-time restrictions (federal 8am–9pm recipient
local time, verify LA rules), recording-consent verification for Louisiana.
Verify current fees/terms directly with the FTC registry and LA Public Service
Commission.

AI voice — do not build toward the manuscript's "5,000 calls/day." Automated/
prerecorded calls to cells without prior express consent carry statutory
damages per call; class actions are an established practice area in this space.

Defensible: AI answering inbound calls (clean), AI calling people who requested
a callback (clean), AI following up with an existing consented contact
(defensible). Not defensible: AI cold-dialing a scraped list (do not). Build the
agent, test on your own phone and consenting friends, point it at inbound first.

Actions: register National DNC + Louisiana state list, write internal DNC
policy, build the scrub step into the pipeline before any number reaches a
dialer, engage a TCPA attorney (separate from the real-estate attorney) for one
review session.

### PART 4 — TRACK C: CONTRACTS AND COUNSEL

Longest lead time — start today. Documents needed: Purchase and Sale Agreement
(LA-specific, assignment-ready), Assignment Agreement, As-Is/Redhibition
addendum (Art. 2548 formalities), Succession rider (signature blocks for all
heirs), seller disclosure script, buyer disclosure (assignment intent, fee
visibility), website terms + privacy policy, course disclaimers (FTC
earnings-claim protection).

Two attorneys needed: a Louisiana real estate attorney (contracts, Successions,
LREC posture, closing practice) and a TCPA/telecom attorney (automated
outreach — a real estate attorney won't know this area, and it's the largest
per-incident exposure). Bring the `contract-audit` skill's output on the current
template to the first meeting — a structured defect list instead of "please look
at this."

### PART 5 — TRACK D: DATA AND CRM (NO GATE — BUILD NOW)

Parish data pipeline: source mapping (Orleans, Jefferson, EBR — documented
sources + ToS review) → extraction (raw records + source URL/timestamp) →
consolidation (deduped, signal-stacked) → enrichment (owner, mailing address,
equity estimate) → CRM load (tagged, ready). Read each site's terms before
automating; if prohibited, use manual export or drop the source — a pipeline
built on a terms violation is a liability, not an asset.

CRM: pipeline stages with explicit entry/exit criteria, custom fields for both
seller leads and buyers, tag taxonomy (parish, signal type, buyer criteria), all
SMS workflows built but disabled until A2P clears.

OpenClaw integration once the gateway is fixed: 4am parish sweep, 7am deal
briefing, twice-daily closing watch. Until then, run skills from the CLI —
everything works, it just isn't scheduled.

### PART 6 — TRACK E: BUYER SIDE (LIVE TODAY)

The only outbound channel legally runnable right now — B2B email under
CAN-SPAM, not consumer telephony under TCPA. Also the most durable asset: a
verified cash-buyer database doesn't expire or need re-permission, and
determines whether a contract can move once one exists.

Build: pull conveyance records (transfers with no recorded mortgage = cash
purchase), resolve entities via Secretary of State (LLC → registered agent →
members), collapse shared agents (ten LLCs under one investor = one buyer), tag
by parish/price band/property type/purchase frequency, email with CAN-SPAM
compliance (accurate header, honest subject, physical address, working
opt-out), run every message through `compliance-gate` first.

CAN-SPAM requirements: accurate header (real from-name/address), non-deceptive
subject, physical postal address in every message, working opt-out honored
within 10 business days, identify as solicitation unless recipient consented.

### PART 7 — GO-LIVE GATES

Do not cross a gate until every item is true.

**Gate 1 — Buyer outreach (available now):** entity formed/EIN obtained,
physical address for CAN-SPAM, buyer database built with entities resolved,
email template through compliance-gate, opt-out mechanism working.

**Gate 2 — Seller contact (weeks 2–4):** attorney engaged/contracts reviewed,
DNC access active with scrub step built into the pipeline, internal DNC list +
written policy, disclosure scripts attorney-approved, TCPA review completed,
call-time restrictions configured, every asset through compliance-gate.

**Gate 3 — SMS (weeks 3–6):** A2P brand approved, A2P campaign approved,
opt-in mechanism live and documented, privacy policy published naming SMS,
opt-out automation tested end to end, use restricted to follow-up not cold
blast.

**Gate 4 — AI voice (weeks 4–8):** Gates 2 and 3 cleared, TCPA attorney
reviewed the specific use, AI disclosure in the first sentence, opt-out honored
immediately (tested), inbound and consented-callback only, recording consent
verified.

### PART 8 — THE OPERATING RHYTHM

Once live: 4am parish sweep (automated), 7am deal briefing (decisions first,
then deadlines), morning seller appointments/offers, midday underwrite new
properties, afternoon buyer outreach/disposition, 4pm closing watch (deadline
exceptions), weekly compliance audit of everything sent, monthly skill tuning
and cost review.

### PART 9 — HONEST TIMELINE

| Week | Milestone |
|---|---|
| 1 | Registrations filed, attorney engaged, buyer database started |
| 2 | Parish pipeline live, CRM configured, buyer outreach running |
| 3 | DNC active, contracts in attorney review |
| 4 | Contracts approved, seller outreach begins (manual dial) |
| 5–6 | A2P clears, SMS follow-up live |
| 6–8 | First contracts |
| 8–12 | First assignment closes |

Anyone promising faster than this is skipping a gate — worth saying in
marketing, since it's true and competitors won't say it.

### PART 10 — WHAT'S STILL BROKEN

| Item | Owner | Priority |
|---|---|---|
| OpenClaw gateway (1006 closure) | You or developer | Medium — CLI works |
| Manuscript SMS-blast content | You | High — publication blocker |
| Manuscript "5,000 calls/day" | You | High — publication blocker |
| Model references (Claude 3.5, GPT-4V) | You | Medium — ages the product |
| AGARA / Part V split | You | Low |
| Repair-variance test | You | Medium — needs a qualified proper |
