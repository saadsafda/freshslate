# Jefferson Parish — Public Records Request

**Purpose:** obtain the tax-delinquency and adjudicated-property data for Jefferson
Parish that Orleans and East Baton Rouge publish as open data.

**Why this route:** Jefferson has no open-data API, and every scrapable candidate is
either restricted or unverified — CivicSource's Terms of Use prohibit robot
monitoring outright (see [SOURCE-RECON.md §7](SOURCE-RECON.md)). A public records
request has no terms-of-service conflict at all, returns bulk data rather than
paginated HTML, and produces a document you can show anyone who asks where the data
came from.

**Status:** ready to send. Requires the operator's name, entity, and contact details.

---

## 1. Legal basis

Louisiana Public Records Act, **La. R.S. 44:1 et seq.** Assessment rolls and tax
records are public records. Key provisions to cite if there is friction:

| Provision | Effect |
|---|---|
| R.S. 44:31 | Right of any person to inspect, copy, or reproduce public records |
| R.S. 44:32(A) | Custodian shall present records promptly |
| R.S. 44:32(D) | **Response required within 3 business days**, or a written explanation of the delay |
| R.S. 44:33(B) | Custodian must provide copies in the medium requested where practicable |
| R.S. 44:35 | Enforcement, attorney fees, and civil penalties for arbitrary denial |

R.S. 44:32(D) is the one that matters in practice. Three business days is a statutory
deadline, not a courtesy, and citing it in the request tends to shorten the reply.

**Electronic format:** ask explicitly for CSV or Excel. Custodians frequently default
to PDF, which is far more work to parse and loses field structure. R.S. 44:33(B)
supports requesting the medium.

---

## 2. Where to send it

### Primary — Jefferson Parish Government (NextRequest portal)

**https://jeffersonparishla.nextrequest.com/**

Jefferson runs a real records portal. This is the preferred channel: requests are
tracked, timestamped, and produce an auditable record automatically.

> Submit through a browser. The portal sits behind a bot-protection layer, which is
> normal for a government intake form and is not an obstacle to a person using it.
> Do not automate it.

Parish switchboard: **504-736-6000**

### Secondary — Jefferson Parish Sheriff's Office (Tax Collector)

The Sheriff is the **tax collector** in Louisiana parishes, so the delinquent tax
roll and tax-sale records are most likely held there rather than at the Parish.

> `jpso.com` did not respond during recon on 2026-08-17, from this network. That may
> be filtering rather than an outage — **verify by phone before assuming it is down.**

### Tertiary — Jefferson Parish Assessor

Holds the assessment roll, ownership, homestead exemption status, and assessed
values. Verified reachable at `www.jpassessor.com`.

Listed phone numbers: **504-362-4100**, **504-736-6370**

> Confirm the correct department and the current records custodian by phone before
> sending. Ten minutes on the phone routes the request correctly and saves a
> two-week misdirection.

---

## 3. What to ask for

Scoped to match the fields the sweep already produces for Orleans and EBR, so
Jefferson data drops into the same schema.

1. **Adjudicated property roll** — all property adjudicated to Jefferson Parish or
   any municipality within it for nonpayment of ad valorem taxes, currently held.
   *(Mirrors EBR dataset `a4h4-zi7e`, the strongest distress signal in the system.)*

2. **Delinquent tax roll** — parcels with ad valorem taxes delinquent **three or more
   years**, per the Module 13 filter.

3. **Tax sale listings** — properties noticed for, or sold at, tax sale in the last
   24 months, including sale date and status.

4. **Code enforcement / blight** — open violations, condemnations, and blight
   adjudications. *(Mirrors Orleans dataset `u6yx-v2tw`.)*

5. **Assessment roll extract** — for the parcels above: parcel ID, situs address,
   owner of record, mailing address, homestead exemption status, assessed value,
   and last sale date/price.

**Fields requested per record:** parcel/assessment ID · situs address · owner of
record · owner mailing address · assessment or filing date · amount delinquent ·
years delinquent · adjudication or sale date · current status · homestead
exemption flag.

**Format:** CSV or Excel. Explicitly *not* PDF.

**Recurrence:** ask whether a **standing monthly or quarterly extract** can be
established, or whether a bulk data agreement or subscription exists. A recurring
feed converts this from a one-off into the same cadence the sweep runs on for the
other two parishes — and it is the single highest-value question in the request.

---

## 4. Request letter — ready to send

Fill the five bracketed fields and send. Written for the NextRequest portal; adapt
the salutation for email to the Sheriff or Assessor.

```
Subject: Public Records Request — Adjudicated and Tax-Delinquent Property Data

To the Custodian of Records:

Pursuant to the Louisiana Public Records Act, La. R.S. 44:1 et seq., I request
copies of the following records:

1. The current roll of property adjudicated to Jefferson Parish or to any
   municipality within Jefferson Parish for nonpayment of ad valorem taxes.

2. A list of parcels with ad valorem taxes delinquent three (3) or more years.

3. Properties noticed for or sold at tax sale within the last twenty-four (24)
   months, including sale date and current status.

4. Open code enforcement violations, condemnations, and blight adjudications.

5. For the parcels responsive to items 1-4, an assessment roll extract containing:
   parcel/assessment identification number; situs address; owner of record; owner
   mailing address; assessment or filing date; amount and number of years
   delinquent; adjudication or sale date; current status; and homestead exemption
   status.

FORMAT: Please provide these records in electronic form as CSV or Microsoft Excel
files. Per R.S. 44:33(B), I request the records in the medium in which they are
maintained where practicable. Please do not convert them to PDF, as that removes
the field structure needed to use them.

RECURRING ACCESS: Please advise whether a standing monthly or quarterly extract can
be arranged, or whether the Parish offers a bulk data agreement or subscription for
these records. I would prefer a recurring arrangement to repeated individual
requests, which would reduce the administrative burden on your office.

FEES: I am willing to pay reasonable costs of reproduction. If you anticipate the
cost will exceed $[AMOUNT, e.g. 100], please contact me with an estimate before
proceeding.

CLARIFICATION: If any part of this request is unclear, or if narrowing its scope
would let you respond faster, please contact me. I would rather adjust the request
than have it delayed.

CUSTODIAN: If your office is not the custodian for any of these records, I would be
grateful if you would identify the correct custodian so I can direct the request
appropriately.

I understand that R.S. 44:32(D) requires a response within three business days of
receipt, or a written explanation if the records cannot be produced in that time.

Thank you for your assistance.

[FULL NAME]
[ENTITY NAME], a Louisiana [LLC/corporation]
[MAILING ADDRESS]
[PHONE]  |  [EMAIL]
```

**Before sending, fill:** `[FULL NAME]` · `[ENTITY NAME]` · `[MAILING ADDRESS]` ·
`[PHONE]` · `[EMAIL]` · `[AMOUNT]`

---

## 5. What to expect

| Stage | Timeline | Note |
|---|---|---|
| Acknowledgement | 1–3 business days | Statutory. Chase on day 4. |
| Custodian routing | 3–10 days | Common — Sheriff vs Parish vs Assessor hold different pieces |
| Fee estimate | 1–2 weeks | Usually modest for electronic records; negotiate the format here |
| Records produced | 2–4 weeks | Varies with request size |

**Realistic:** 2–4 weeks to first data, faster if narrowed to items 1 and 2 only.

If speed matters more than completeness, **send items 1 and 2 alone first.** The
adjudicated roll plus the 3-year delinquent list is most of the signal value, and a
short request moves faster through any records office.

---

## 6. When the data arrives

The extraction path is already built — this is a loader, not a new pipeline.

1. Save the raw file to `deals/_inbox/` **unmodified**. It is the provenance
   artifact; every downstream record cites it.
2. Add a `jefferson` entry to `config/sources.json` with
   `"type": "public_records_request"`, the request date, custodian, and file path.
3. Map the supplied column names to the existing normalized schema — the same
   `field_map` shape the Socrata sources use.
4. Set `enabled: true` only once the mapping is verified against real rows.
5. Run `python3 src/validate.py` — citation discipline (Test 12) and the
   no-fabrication probe (Test 13) apply to these records exactly as they do to the
   API-sourced ones.

Provenance for records-request data: `source_dataset` = the request tracking number,
`source_url` = the portal request URL, `retrieved_at` = the date of production.
A parcel sourced this way must be as auditable as one pulled from Socrata.

---

## 7. Not a blocker for the seminar

Orleans and East Baton Rouge run live today on real, current data. Jefferson is a
third parish, not a prerequisite.

**Recommended framing:** demo the two live parishes and describe Jefferson honestly —
"no open-data API exists there, so we're obtaining it through a public records
request rather than scraping a site whose terms prohibit it." That is a stronger
position in front of a room than a scraper that breaks, and it teaches the
read-the-terms-first discipline the course is selling.
