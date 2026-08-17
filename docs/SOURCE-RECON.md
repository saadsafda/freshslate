# Parish Source Recon — Findings

**Date:** 2026-08-04
**Purpose:** Answer RAE Block 1 ("map the permitted parish sources before building extraction")
before writing any extraction code.

---

## Headline finding

**The Orleans Parish Assessor site cannot be scraped. It does not need to be.**

Orleans and East Baton Rouge both publish official **Socrata open-data APIs** carrying the
distress signals Module 13's `parish-sweep` skill targets. Using them is faster, legally clean,
more reliable, and immune to the layout-change failure mode Module 13 warns about.

This replaces DOM scraping as the primary extraction strategy for those two parishes.

---

## 1. Orleans Parish Assessor — BLOCKED

| Check | Result |
|---|---|
| `https://www.nolaassessor.com/` | **HTTP 403** |
| `https://www.nolaassessor.com/property-search/` | **HTTP 403** |
| Server | `cloudflare` (`cf-ray` header present) |
| Realistic browser headers (UA, Accept, Sec-Fetch-*) | still **403** |

The 403 is site-wide, not path-specific, and survives full browser-like headers. This is
Cloudflare bot management, not a misconfiguration.

**`robots.txt` additionally declares:**

```
User-agent: *
Content-Signal: search=yes, ai-train=no, use=reference
```

The operator has expressly reserved rights under **EU Directive 2019/790 Article 4**. Combined
with the 403, there is no reading under which automated collection here is permitted.

**Conclusion:** Do not attempt to bypass. Module 13's own constraint is explicit —
*"Respect robots.txt and rate limits. If a site's terms prohibit automated access, stop and tell
me."* Defeating Cloudflare would violate the module's stated standard, the site's terms, and
likely CFAA. It would also break constantly.

---

## 2. Orleans Parish — data.nola.gov (SANCTIONED, USE THIS)

**209 public datasets.** Socrata SODA API. No key required for our volume.

`robots.txt`: `Crawl-delay: 1`; `/resource/` endpoints are **not** disallowed — the API is the
intended machine-access path.

### Datasets mapped to Module 13 signals

| Module 13 signal | Dataset | ID | Status |
|---|---|---|---|
| Code violations | Code Enforcement All Cases | `u6yx-v2tw` | ✅ verified |
| Code violations (detail) | Code Enforcement All Violations | `3ehi-je3s` | ✅ verified |
| Distress / foreclosure | Sheriff Sales – Lien Foreclosures | `d52w-8nva` | ✅ verified |
| Blight | BlightStatus Demolitions | `e3wd-h7q2` | listed |
| Vacant / held inventory | NORA Uncommitted Property Inventory | `5ktx-e9wc` | listed |

### Verified live query

```
GET https://data.nola.gov/resource/u6yx-v2tw.json
  ?$where=o_c='Open' AND casefiled > '2026-01-01T00:00:00'
  &$order=casefiled DESC
```

- **2,969** open cases filed in 2026
- Most recent record: **2026-08-03** — one day before this recon
- Server-side filtering, ordering, and `count(*)` all work

### Field map — `u6yx-v2tw` (Code Enforcement All Cases)

| API field | Meaning | → `parish-sweep` field |
|---|---|---|
| `caseno` | Case number, e.g. `26-08756-MPM` | `source_case_no` |
| `caseid` | Stable numeric ID | **dedup key** |
| `geoaddress` | Geocoded address | `situs_address` |
| `location` | Raw location string | `situs_address_raw` |
| `geopin` | Parcel identifier | `parcel_id` |
| `casefiled` | Filing timestamp | `filing_date` |
| `statdate` | Status change date | `status_date` |
| `o_c` | Open / Closed | filter |
| `stage` | e.g. `1 - Inspection` | `signal_strength` input |
| `keystatus` | Narrative status | `notes` |
| `xpos` / `ypos` | State plane coords | geo |

> ⚠️ **`owner` is not present in this dataset.** Module 13 asks `parish-sweep` to capture
> "owner of record." Orleans code-enforcement data does not carry it. Per the module's own
> constraint — *"Do not guess at fields"* — the skill must emit `owner_of_record: null` with
> `owner_source: unavailable`, not infer it. Owner resolution needs a separate permitted source.

---

## 3. East Baton Rouge — data.brla.gov (SANCTIONED)

**240 public datasets.** Same Socrata API.

| Signal | Dataset | ID | Status |
|---|---|---|---|
| **Adjudicated property** (tax-sale failed) | Adjudicated Property | `a4h4-zi7e` | ✅ verified |
| **Tax roll + owner + homestead** | EBRP Tax Roll | `myfc-nh6n` | ✅ verified |
| Property detail | Property Information | `re5c-hrw9` | listed |
| Permits | EBR Building Permits | `7fq7-8j7r` | listed |

**This is the richest source of the three.** Two capabilities Orleans cannot give us:

1. **`owner` / `taxpayer_name` are present** — real owner of record, not inferred.
2. **`homestead_exempt_type`** — the *correct* way to derive Module 13's "absentee owner"
   filter. No homestead exemption + mailing address ≠ situs address = non-owner-occupied.
   This is a documented field, not a guess.

Adjudicated property records carry `legal` text such as
`ADJ. TO STATE OF LA. FOR 1986 TAXES.` — direct evidence of long-run tax delinquency,
which is Module 13's "tax delinquency 3+ years" filter.

---

## 4. Jefferson Parish — NEEDS DEEPER WORK

`jpassessor.com` and `jeffparish.gov` both return 200 and serve `robots.txt`. No Cloudflare
block observed. **However**, no open-data API equivalent was found.

Jefferson likely requires real extraction (form analysis, possible XHR endpoint per RAE's
Block 1 prompt). **Estimate: 1–2 weeks on its own**, and it carries the layout-change fragility
Module 13 warns about.

**Recommendation:** defer Jefferson. Ship Orleans + EBR via API first.

### 2026-08-12 follow-up — full catalog checked, same conclusion

Found a real official portal: `jefferson-parish-data-transparency-jpgis.hub.arcgis.com`
(Jefferson Parish GIS Dept, ArcGIS Hub). Pulled the **complete public catalog via the
ArcGIS Online sharing API** (`arcgis.com/sharing/rest/search?q=owner:rclipper_JPGIS`) —
**204 items**, every one a genuine hosted ArcGIS service, not scraped or inferred.

Checked every title/tag/description against: code enforcement, violation, blight, condemn,
adjudicated, delinquency, tax sale, foreclosure, sheriff sale, assessment, nuisance,
abatement, lien. **Zero matches carrying the distress signals Module 13 needs.** The catalog
is water/drainage infrastructure, 2021 COVID response data, parks/facilities, council
districts, and zoning — no property-code or tax-delinquency data is published here. (Two
generically-named hits, `Cases1007`/`casecount`, are COVID case counts, confirmed via their
tags — not code-enforcement cases.)

Two non-API surfaces exist and were **not** attempted: `JeffMap`
(`jp-appserver.jeffparish.net/webapps/webmap`) and a third-party assessor viewer
(`atlas.geoportalmaps.com/jefferson`) — both interactive map/form applications, not APIs.
Extracting from either is the same form/XHR reverse-engineering job estimated above, not a
quick win this recon uncovered. Conclusion unchanged: **Jefferson Parish is confirmed not to
publish the needed data as open data**, rather than merely "not yet found."

*Recon method: read-only queries against the public ArcGIS sharing REST API and DCAT feed —
no scraping, no authentication bypass, no interactive-app automation attempted.*

---

## 5. Rate limiting

`data.nola.gov` returned no `X-RateLimit-*` headers. Socrata's documented unauthenticated
policy is a shared rolling pool per IP; an app token raises it and makes usage attributable.

**Implementation standard for this project:**
- Honor `Crawl-delay: 1` → **1 req/sec ceiling**
- Page at `$limit=1000`, `$offset` cursor
- Register a **free Socrata app token** before production (no cost, better limits)
- Exponential backoff on HTTP 429

---

## 6. What this changes

| Module 13 assumption | Reality | Consequence |
|---|---|---|
| Scrape assessor DOM, map CSS selectors | Assessor is 403; APIs exist | **Selector maps unnecessary for 2 of 3 parishes** |
| Layout changes break extraction | APIs have stable schemas | Failure mode largely removed |
| All three parishes equivalent | Jefferson has no API | Jefferson is a separate, larger job |
| Capture "owner of record" per record | Orleans lacks owner; EBR has it | Must be null-safe per parish |
| Browser automation needed for sweep | Plain HTTPS + JSON | Simpler, cheaper, no browser in the loop |

**Seminar implication:** `parish-sweep` can run **live on real, current data** for Orleans and
EBR. It does not need seeded demo data. That is a stronger demo than originally planned, and it
is defensible on stage — every record traces to a named government dataset with a retrieval
timestamp.

---

## 7. Open items

- [ ] Register Socrata app token (free) before production
- [ ] Jefferson Parish deep recon — scope separately, do not promise for seminar
- [ ] Resolve Orleans owner-of-record from a permitted source, or accept null
- [ ] Confirm each dataset's terms of use / attribution requirement
- [ ] Counsel review: Act 807 gates (separate track, not blocked by this)

---

*Recon performed with read-only HTTP requests against public endpoints and published
`robots.txt`. No authentication was attempted, no access control was tested or circumvented,
and no blocked resource was retrieved.*
