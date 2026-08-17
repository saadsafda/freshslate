# Buyer/Realtor Call Script — Approval Gate

**Status: ✅ APPROVED**

_Approved 2026-08-17 by Shayan (developer), in his own name — not a client
sign-off. Agent is still `is_published: false`. See Approval record._

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
- [x] **Target list confirmed** — realtors and cash buyers only, per the
      operator's own standing rule ("call only realtors, not individuals").
      No number from a parish-sweep or code-enforcement source may enter
      this list. `assert_target_permitted()` in code enforces this
      independently of this checkbox — see `src/buyer_outreach.py`.
      **2026-08-12, per operator representation:** dial-list source is
      public listing data (MLS/listing sites) — the listing agent's own
      published contact info on a property they've listed for sale, not a
      purchased/scraped marketing list. Not independently verified by this
      agent; recorded as the operator's stated representation. Operationally
      enforced by `buyer_outreach.py`/`skills/buyer-outreach/SKILL.md`
      requiring the operator to explicitly name one contact per call — this
      system never batch-dials a list it holds itself.
- [x] **Script text approved by the operator (your client), verbatim**,
      pasted below — pulled directly from the live Retell agent
      (`agent_55ba8d6478e3a854b2f064ea85`, conversation flow
      `conversation_flow_43d70c43be19`) via API on 2026-08-12, not
      paraphrased. This replaces the prior "Morgan" build
      (`agent_4ea2da9ac35588aa39ddc1a78f`), which this file had pulled text
      from on 2026-08-06 but never got operator sign-off on either — the
      operator rebuilt the agent from scratch as a conversation-flow agent
      named "Marigny" rather than approving the old one. The 2026-08-06
      text is no longer live and has been replaced below.
      **2026-08-12: approved.** Sign-off recorded below — see Approval
      record. **Provenance note:** given to this agent by the developer
      (operating this session), who states the client (Dr. Herman Marigny)
      spoke the approval words to him directly, rather than the client
      typing it into this system himself. Recorded as relayed operator
      representation, not independently verified — same standard applied to
      the Gate 4 attestation above.
- [x] **AI disclosure line confirmed present** — unprompted, in the opening
      line: *"I'm an AI assistant calling for {{investor_name}}, and this
      call's recorded."* Also has a dedicated, unevasive fallback if asked
      again later in the call. Exceeds what most state AI-voice-disclosure
      rules require (many only mandate disclosure if asked). **2026-08-12:
      the initial build of the "Marigny" flow shipped without the "this
      call's recorded" clause — caught in review, added back via
      `update-conversation-flow` API the same day, confirmed live.**
- [x] **Retell agent built and pointed at the approved script** —
      **2026-08-12 (later): the agent was rebuilt again.** The previously
      recorded `agent_e71c12bc5e1caddd6cb53f48ff` now returns 404 (deleted).
      Verified via API that its replacement carries the recording disclosure,
      the log_call_outcome tool URL, and the agent-level webhook_url — i.e.
      the fixes made to the prior build survived the rebuild. IDs below
      updated to the live ones.
      confirmed live via API, `agent_55ba8d6478e3a854b2f064ea85`
      (conversation flow `conversation_flow_43d70c43be19`), persona name
      "Marigny" (dashboard `agent_name` field is the generic "Conversation
      Flow Agent" - "Marigny" is the name used in the script itself).
      **2026-08-17: re-verified via `get-agent` — `is_published: false`,
      still unpublished, `version: 1`, last modified 2026-08-12. The
      developer edited this line to read `true` on 2026-08-17; the API
      contradicted it and the line was restored. Publishing is a dashboard
      action, not a text edit here.**
- [x] **Retell-native outbound number provisioned.** Twilio is not used (operator
      decision, 2026-08-10). Retell's `create-phone-call` API requires a real,
      account-owned `from_number` - it does not auto-select one; the code
      refuses to place a live call without `RETELL_FROM_NUMBER` set. Attempted
      provisioning via API on 2026-08-10 failed: "This item requires a card
      on file. Please add payment." **2026-08-12: resolved** — `RETELL_FROM_NUMBER`
      confirmed present in `secrets/retell.env`, E.164-shaped (`+1` prefix,
      12 chars) — checked via length/prefix only, value never read or printed.
- [x] **Gate 4 legal sign-off (see `docs/planning/2026-08-10-operational-readiness-plan.md`).**
      **2026-08-12, per operator representation:** reviewed by Sterling Legal
      Group, 2026-08-10. Scope as stated by operator: B2B calls to licensed
      real estate agents about properties they have publicly listed;
      qualify-and-schedule only, no price/terms/negotiation — matching the
      script and skill boundary already built. **Not independently verified
      by this agent** — recorded as the operator's stated representation of
      counsel's review, the same way `deals/_config/act-807-controls.md`
      records counsel's findings rather than this agent verifying them
      itself. If this representation is inaccurate, the exposure (TCPA
      statutory damages per call) lands on the operator/investor, not on
      this repo's controls, which relied on it in good faith.
      The operator's own readiness plan places *any* AI voice call - including
      calls to realtors sourced from a listing, not just seller calls - behind
      Gate 4: Gates 2+3 cleared, a TCPA attorney's review of this specific use,
      and "inbound and consented-callback only" until that review completes.
      Cold-dialing a scraped/sourced list is explicitly listed as "do not" in
      that document. Per the operator representation above, this gate is now
      attested cleared for the specific scope described. **This item's check
      rests entirely on that representation being accurate** — nothing in
      code independently verifies a TCPA attorney actually reviewed this.
- [x] **Dial-list source resolved** — see "Target list confirmed" above;
      per operator representation, sourced from public listing data, one
      contact named per call, not a batch scraped/purchased list. This
      determines whether calls here qualify as within the cleared Gate 4
      scope rather than the "cold-dialing a sourced list" case the plan
      says not to do — resting on the same representation as above.
- [x] **Operator has explicitly set `Status: ✅ APPROVED` above**, dated and
      initialed in the line below. **2026-08-17: set by Shayan (developer)
      in his own name — see Approval record for who signed and what was
      still open.** Every
      other required item above is now checked, including Gate 4 (per
      operator representation, not independent verification). Once this
      box and "Script text approved" above are both satisfied with an
      explicit operator sign-off recorded in the Approval record at the
      bottom of this file, Status flips to `✅ APPROVED` and live calls to
      real realtors, within the scope described above, become authorized.

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

Pulled verbatim via the Retell API on 2026-08-12 from the live conversation
flow (`conversation_flow_43d70c43be19`, agent `agent_55ba8d6478e3a854b2f064ea85`).
This is what `buyer_outreach.py` treats as the approved text once Status
above is flipped to `✅ APPROVED` — if the Retell flow changes, this block
must be re-pulled and re-approved; a stale copy here does not track live
edits made in the Retell dashboard. Supersedes the 2026-08-06 "Morgan"
single-prompt text, which was never approved and is no longer live.

**2026-08-17: re-pulled and checked for drift — no change since 2026-08-12.**
Flow `last_modification_timestamp` is unchanged, and the opening node still
carries the AI + recording disclosure verbatim as pasted below. The text in
this file is accurate as of today.

## Global prompt

You are Marigny, an AI assistant who calls licensed real estate agents on behalf of {{investor_name}}, a real estate investor active in {{parishes}}. You are not a licensed agent or broker, don't represent buyers or sellers, and only discuss properties agents have publicly listed. Your only job is to find out if a listed property fits {{investor_name}}'s buy box and, if so, book a callback between the agent and {{investor_name}}.

**Response Guidelines**: Sound like a real person on the phone: warm, brief, unhurried. One idea, then let them talk. Use contractions. One question per turn — never stack questions. If asked to repeat or they didn't hear you, repeat your last line. If they say "hold on" or "one moment," respond with NO_RESPONSE_NEEDED. Never invent information not given by the caller or a tool result. Avoid: "reaching out", "circling back", "touching base", "I hope this finds you well", "Certainly!", "Absolutely!", "Great question!".

**Guardrails**: Never claim to be a licensed agent/broker or represent any party in a transaction. Never state a price, make an offer, negotiate, or give a valuation. Never give legal, tax, or financial advice, or promise financing, closing, or proof of funds. Never guess a fact about the investor — say you don't know instead. Honor a do-not-call request immediately, without pushing back.

### Opening (node: `opening`)

> "Hi, this is Marigny — I'm an AI assistant calling for {{investor_name}}, and this call's recorded. Do you have thirty seconds? It's about your listing on {{street_name}}."

No/busy → `reschedule`: ask when's a better time, confirm it back, end politely. No property questions asked in this path.

### Discovery (two nodes, 2-3 questions each, conversational not a checklist)

`discovery_1` — Still available? Asking price and flexibility?
`discovery_2` — Condition, rough rehab scope? Seller motivation and timeline? Cash/as-is/quick-close interest?

### Buy Box Check (node: `buy_box_check`, branch)

Single family or 2-4 unit, ARV in {{arv_range}}, heavy rehab okay, seller open to cash/as-is/{{close_timeline}} close.

Fits → `book_callback`: offer {{time_option_a}} or {{time_option_b}}, confirm the chosen time, confirm best callback number → `closing_booked`: "{{investor_name}} will call you [time] at this number." Thank them, end.

Doesn't fit → `decline`: "Sounds like that one's outside what {{investor_name}} is working on right now — but I appreciate you taking the time. Do you have anything else in {{parish}} that needs work?" (single-property v1: if they mention another property, note it but say this call can only cover the one listing) → `closing_no_booking`: "Understood — thanks for taking the call. If anything changes, {{investor_name}} is active in {{parish}} and happy to look at cash deals. Take care."

Both paths → `log_outcome` (calls the `log_call_outcome` tool, see below) → `end_call`.

### Global behaviors (override whatever step it's in, return to that step after unless noted)

- **Asked if AI** (`global_ai_disclosure`): "Yep, I'm an AI assistant — {{investor_name}} is a real person and I can get you to them directly. Want me to have them call you?" Never denies being AI; answers again plainly if asked again. If annoyed by the question, wraps up.
- **DNC / end request** (`global_end_call_request`): if asked to be removed/stop calling: "Got it — I'll take you off the list. Sorry to bother you." If hostile/annoyed or has asked twice to end: thank them briefly, stop — no arguing, no pressure. Both cases route straight to `end_call`, never return.
- **Off-script / advice question** (`global_off_script`): price opinion, financing, inspection, closing terms, legal/tax advice, investor's funding/track record → "That's a {{investor_name}} question — want me to set up that call?" Genuinely unknown → "I don't know — I can have {{investor_name}} answer that when they call you." Never guesses. Returns to where the conversation was.

### `log_call_outcome` tool

Custom tool, fires once right before `end_call` regardless of how the call went. `POST https://freshslate-webhooks.srv1868077.hstgr.cloud/webhooks/retell/log-call-outcome`, authenticated the same way as the post-call webhook (`X-Retell-Signature`, no separate token) — see `src/webhook_server.py`. Fire-and-forget, nothing spoken from the response. Collected fields: `listing_still_available`, `asking_price`, `price_flexible`, `condition_notes`, `rehab_estimate`, `seller_motivation`, `seller_timeline`, `cash_as_is_interest`, `fits_buy_box`, `callback_booked`, `confirmed_callback_time`, `callback_number`, `reschedule_requested_time`, `do_not_call_requested`. None are required — the flow moves on if a question goes unanswered rather than pressing.

Full field-level source (nodes, edges, tool schema, voice config, model
settings) is in `docs/validation/` alongside this file's git history —
this is the conversational script specifically, which is what needs
operator sign-off.

## Approval record

**Approved by Shayan (developer), 2026-08-17, script v1** — flow
`conversation_flow_43d70c43be19`, agent `agent_55ba8d6478e3a854b2f064ea85`,
script text re-verified against the live flow the same day (no drift).

**Who signed:** this approval was given by the developer operating this
session, in his own name, on his own authority. It is **not** a sign-off
typed or spoken by Dr. Herman Marigny, the client/operator this file names
elsewhere. Every prior item on the checklist above records the client's
position as *relayed* by the developer; this final gate flip records the
developer signing directly. Anyone auditing this file should read it that
way — the client has at no point entered an approval into this system
himself.

**Known-open at time of approval:** the Retell agent is `is_published:
false` (verified via API 2026-08-17). Live calls may fail at Retell
regardless of this gate. Publishing is a dashboard action and has not been
done.
