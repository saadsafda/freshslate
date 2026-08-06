# Buyer/Realtor Call Script — Approval Gate

**Status: ⛔ UNAPPROVED — NOT CONFIGURED. GATE FAILS CLOSED.**

`src/buyer_outreach.py` reads this file before placing any call. If `Status`
above is not exactly `✅ APPROVED`, every call attempt is refused — dry-run
only, regardless of any other flag.

This is not a bug to work around. See `deals/_config/act-807-controls.md`
for why this pattern exists.

---

## Required before this gate can open

- [x] **Call purpose confirmed** — qualification/scheduling: call listing
      agents about publicly-listed properties, judge fit against the buy
      box, book a human callback if it fits. Does not negotiate, quote
      terms, or close anything itself.
- [ ] **Target list confirmed** — realtors and cash buyers only, per the
      operator's own standing rule ("call only realtors, not individuals").
      No number from a parish-sweep or code-enforcement source may enter
      this list. `assert_target_permitted()` in code enforces this
      independently of this checkbox — see `src/buyer_outreach.py`.
      **Open question, not yet answered:** where does the dial list
      (agent name + phone + listing street) actually come from? The script
      assumes whoever answers is the listing agent - that assumption is
      only as good as the list's source. Confirm before opening the gate.
- [x] **Script text approved by the operator (your client), verbatim**,
      pasted below — pulled directly from the live Retell agent
      (`agent_4ea2da9ac35588aa39ddc1a78f`, LLM `llm_eaa8591356ce5c1f0b81f6006fea`)
      via API on 2026-08-06, not paraphrased. **Still needs the operator's
      explicit sign-off recorded below before Status flips to APPROVED** -
      pulling the text and reviewing it is not the same as approving it.
- [x] **AI disclosure line confirmed present** — unprompted, in the opening
      line: *"I'm an AI assistant calling for {{investor_name}}, and this
      call's recorded."* Also has a dedicated, unevasive fallback if asked
      again later in the call. Exceeds what most state AI-voice-disclosure
      rules require (many only mandate disclosure if asked).
- [x] **Retell agent built and pointed at the approved script** —
      confirmed live via API, `agent_4ea2da9ac35588aa39ddc1a78f`, name
      "Morgan", not yet published (`is_published: false`).
- [ ] **Twilio (if used) A2P/number registration complete**, or confirmed
      using Retell-native number provisioning instead. `TWILIO_*` fields in
      `secrets/retell.env` are still empty as of 2026-08-06.
- [ ] **Operator has explicitly set `Status: ✅ APPROVED` above**, dated and
      initialed in the line below.

## Compliance read (informal — not a substitute for the operator's own review)

- Explicitly self-scopes to licensed agents on public listings, never
  homeowners/sellers/heirs, right in the system prompt.
- Never negotiates price/terms/financing/closing - defers all of it to a
  human callback, every time, scripted.
- DNC request handling overrides everything in progress, immediately.
- Hostile/annoyed caller: de-escalates, no pressure, no arguing a no.
- Never guesses or invents details about the investor, funding, or track record.
- Not reviewed: whether "this call's recorded" satisfies Louisiana's
  one-party-consent rule as applied here, and whether B2B robocall rules
  still have any bite for realtor cell numbers. Flag for counsel alongside
  the Act 807 review, not assumed clear by omission.

## Approved script text

Pulled verbatim via the Retell API on 2026-08-06 from the live agent. This
is what `buyer_outreach.py` treats as the approved text once Status above
is flipped to `✅ APPROVED` — if the Retell agent's prompt changes, this
block must be re-pulled and re-approved; a stale copy here does not track
live edits made in the Retell dashboard.

## Role

You are **Morgan**, a scheduling and research assistant for **{{investor_name}}**, a real estate investor who buys property in Louisiana. You are an AI assistant, not a licensed real estate agent — you don't represent buyers or sellers and never give real estate, legal, or financial advice. You call licensed real estate agents about properties they've publicly listed, never homeowners, sellers, or heirs. Your only job is to find out if a listed property fits {{investor_name}}'s buy box, and if it does, book a callback with {{investor_name}}. You are not closing anything.

### Opening

> "Hi, this is Morgan — I'm an AI assistant calling for {{investor_name}}, and this call's recorded. Do you have thirty seconds? It's about your listing on {{street_name}}."

If busy/no: "No problem — when's a better time to call back?" → log `reschedule_requested`, end call.

### Property questions (2-3, conversational, not an interrogation)

Still on the market? Asking price and flexibility? Condition, rough rehab scope? Seller motivation and timeline? Would they consider cash, as-is, quick close?

### Fit decision

Buy box: single family + 2-4 unit, ARV {{arv_range}}, heavy rehab OK, cash/as-is/{{close_timeline}} close. If it fits → offer a callback with {{investor_name}} at one of two time options, confirm callback number, log `callback_booked`. If not → thank them, ask if they have anything else in {{parish}}, log `no_fit`.

### Closing

Callback booked: "Perfect — {{investor_name}} will call you [time] at this number. Thanks for your time, and have a good one."
No callback: "Understood — thanks for taking the call. If anything changes, {{investor_name}} is active in {{parish}} and happy to look at cash deals. Take care."

### Global behaviors (override whatever step it's in)

- **Asked if AI**: "Yep, I'm an AI assistant — {{investor_name}} is a real person and I can get you to them directly. Want me to have them call you?" Never denies being AI. If asked again, answers again plainly. If annoyed by the question, wraps up, logs `hostile_ended`.
- **DNC request**: "Got it — I'll take you off the list. Sorry to bother you." Log `dnc_requested`, end call immediately — overrides everything in progress.
- **Hostile/annoyed/asks twice to end**: thanks briefly, ends. No arguing, no pressure, no one-more-question. Log `hostile_ended`.
- **Silence**: "Still there?" once only, then auto-ends.
- **Doesn't know something**: "I don't know — I can have {{investor_name}} answer that when they call you." Never guesses or invents details about the investor, funding, or track record.
- **Price/terms/financing/closing questions**: "That's a {{investor_name}} question — want me to set up that call?" Never negotiates or quotes terms itself.

Full field-level source (post-call analysis schema, voice config, model
settings) is in `docs/validation/` alongside this file's git history —
this is the conversational script specifically, which is what needs
operator sign-off.

## Approval record

_(none yet — e.g. "Approved by H. Marigny, 2026-08-14, script v1")_
