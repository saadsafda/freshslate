# What I Need From You — GHL, Voice Agent, and Underwriting

**To:** Dr. Marigny
**From:** Shayan
**Date:** 2026-08-10
**Re:** Information required to wire the voice agent to GoHighLevel

---

## Why I'm asking

The voice agent needs to log call outcomes somewhere. You've told me that's GoHighLevel.
Before I can wire that up, I need the specifics below — I can't guess at field names or
pipeline stages, because a wrong guess writes bad data into your live CRM.

Everything below is grouped by urgency. **Section 1 blocks the voice agent today.**
Sections 2–4 block other work already in progress.

---

## ⚠️ Two things to decide before anything is wired

### A. Realtors or sellers?

You told me the voice agent calls **realtors, not individual homeowners**. Your own Prompt 4.3
in the build playbook is written for calling **property owners**. These are different systems:

| | Realtors (B2B) | Distressed homeowners |
|---|---|---|
| DNC registry | Generally not applicable | **Applies** |
| TCPA exposure | Lower | **High** |
| Consent needed | Business contact | Prior express consent for automated calls |
| Pipeline | Agent/broker outreach | Seller acquisition |

**These need separate GHL pipelines and separate tags.** If they share one pipeline, a realtor
list and a distressed-seller list will eventually get called by the wrong workflow. Please
confirm which one we are building first.

### B. Is A2P/DNC cleared?

Your build playbook says plainly:

> *"Test target for today: your own phone only. A2P and DNC aren't cleared. Three consenting
> friends maximum, recorded with permission."*

If that's still true, the webhook can be built but **must not be pointed at a real call
campaign**. Please confirm the current status:

- [ ] A2P 10DLC brand + campaign registered and approved?
- [ ] DNC scrubbing process in place, and who runs it?
- [ ] Call recording consent language approved by counsel? (Louisiana is one-party consent, but
      your recording disclosure still needs review)

---

## 1. GoHighLevel — needed to wire the voice agent

### 1.1 Access

- **Location ID** (GHL sub-account ID — found in Settings → Business Profile)
- **API key or Private Integration token** — GHL v2 API preferred
- **Agency or sub-account?** Which level am I integrating at?

> **Do not email these.** Per RAE's own instruction: *"Please do not send passwords, API keys,
> account credentials... by email."* Use a password manager share, or put them directly into the
> server environment and tell me the variable names.

### 1.2 Pipeline structure

For the pipeline the voice agent writes to:

- **Pipeline name and ID**
- **Every stage name, in order**
- **Which stage does a new call outcome land in?**
- **Which stage means "book a callback with a human"?**

### 1.3 Custom fields

I need the exact **field key** (not the display label) for anything the agent should write:

| What the agent knows | GHL field key | Type |
|---|---|---|
| Call outcome (answered / voicemail / no answer / opted out) | ? | ? |
| Call disposition / interest level | ? | ? |
| Callback requested date-time | ? | ? |
| Recording URL | ? | ? |
| Call transcript or summary | ? | ? |
| Parish | ? | ? |
| Signal type (tax delinquency / code violation / foreclosure) | ? | ? |
| Parcel ID | ? | ? |
| Source dataset | ? | ? |

**Easiest way to give me this:** GHL → Settings → Custom Fields → screenshot the list. Or export
one existing contact as JSON and send it with personal details redacted.

### 1.4 Tags

Your playbook calls for a tag taxonomy covering parish, signal type, buyer criteria, deal stage.
**Does it exist yet?** If yes, send the list. If no, I'll propose one and you approve it.

### 1.5 Opt-out handling

**This is the one I most need answered.** When someone says "stop calling me":

- Which GHL tag or field records it?
- Does it trigger a workflow that suppresses all future contact?
- Who maintains the suppression list?

An opt-out that logs but doesn't suppress is a TCPA violation waiting to happen. If this doesn't
exist yet, it must be built **before** the first real call.

---

## 2. Underwriting cost figures — still the top blocker

The `underwrite` skill is built and working, but every number in it is a **placeholder I
invented**. Every output currently carries a warning saying so.

I need your real Gulf South figures:

**Per-unit costs:** roof (per square), siding (per sf), interior paint, flooring by type, full
kitchen, full bath, electrical rewire, panel replacement, HVAC, water heater, pier leveling,
sheetrock, plumbing repipe, mold remediation, debris haul.

**Deal parameters:** contingency %, target assignment fee, holding cost per month, closing costs.

**MAO formula:** currently `(ARV × 0.70) − repairs − fee`. Is 0.70 right? Does it change by
parish, price band, or property type?

**Any format is fine** — spreadsheet, photo of a handwritten list, or an old scope of work.

Module 13 says explicitly: *"Do NOT use national averages."* Until your numbers replace mine,
the skill cannot produce a usable offer.

---

## 3. Louisiana counsel — Act 807 blocker

Act 807 (La. R.S. 37:1448.5) took effect **August 1, 2026**. Penalties up to **$5,000 per
violation**, and a contract missing a required element is **voidable at the seller's discretion
until title transfers**.

**I found a conflict I cannot resolve:**

| Source | Seller cancellation period |
|---|---|
| RAE's email | **5** calendar days |
| Summary of the enrolled bill | **14** calendar days |

I could not reach `legis.la.gov` to confirm which is correct. **A Louisiana attorney needs to
pull the enrolled text and resolve this**, along with the exact prescribed notice wording,
deposit minimum, and escrow requirements.

The compliance gate is currently **closed** — it refuses to check any contract until this is
resolved. That is deliberate. RAE's own instruction was that these be *"counsel-owned, versioned
transaction gates — not merely warnings in an agent prompt."*

**Who is your attorney, and when can they review?**

---

## 4. Documents I still need

| # | Item | For |
|---|---|---|
| 4.1 | LREC-compliant contract templates — PSA, assignment, redhibition waiver, As-Is addendum | `contract-audit` audits against *your* forms, not a generic checklist |
| 4.2 | One Succession filing, **names redacted** | `succession-mapper` — I need the document structure, not the people |
| 4.3 | 2–3 past marketing pieces (SMS, postcard, ad copy) | `compliance-gate` screens real material |
| 4.4 | Confirm buy box: SFR + 2-4 unit, ARV $120k–400k, assignment fee $10–15k | `USER.md` |
| 4.5 | How you organize a deal folder today | `closing-watch`, `deal-desk-brief` |

---

## 5. Where the build stands

**Working now:**

- Parish data extraction — **live** against official Orleans (`data.nola.gov`) and East Baton
  Rouge (`data.brla.gov`) open-data APIs. Verified against current records.
- Underwriting calculator — three-scenario MAO, per-line confidence, flags what photos don't show
- Act 807 compliance gate — built, correctly refusing to operate until counsel signs off
- 7 skills, operating files, 14-point validation gate (10/10 automated tests passing)

**Two findings you should know about:**

1. **The Orleans Assessor site cannot be scraped.** It returns HTTP 403 site-wide behind
   Cloudflare, and its robots.txt expressly reserves rights against automated collection.
   **Module 13 teaches scraping it — that section needs correcting before you teach it.**
   The official open-data APIs are better anyway: free, sanctioned, faster, and they don't break
   when a page layout changes.

2. **Jefferson Parish has no open-data API.** It needs separate work — roughly 1–2 weeks. I'd
   recommend not promising it until that's scoped.

**Cost to run today:** parish data $0, RentCast free tier $0 (50 lookups/month), LLM roughly
$90–150/month per operator.

---

## 6. Fastest path

If you can only do three things this week:

1. **Send the cost figures** — unblocks underwriting entirely
2. **Name your attorney** — unblocks the Act 807 gate
3. **Answer the two questions at the top** — realtors vs. sellers, and A2P/DNC status

Everything else can follow.
