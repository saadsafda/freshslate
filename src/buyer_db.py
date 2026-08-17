#!/usr/bin/env python3
"""
buyer-db — deterministic cash-buyer / investor-owner database builder.

Implements Part 6 ("Track E: Buyer Side") of
docs/planning/2026-08-10-operational-readiness-plan.md — the one outbound track
the operator's own plan places behind no legal gate.

Identifies active property investors in East Baton Rouge Parish from the
public EBRP Tax Roll: owners holding multiple NON-homestead-exempt properties.
Produces a ranked, tagged research list with full provenance.

WHAT THIS PRODUCES: entity/person name, mailing address, portfolio size,
price band, property mix.

WHAT THIS DOES NOT PRODUCE: phone numbers or email addresses. The tax roll
does not carry them and this script does not infer, guess, or look them up
elsewhere. Contactability is a separate, unsolved step — see
"Known limits" in the generated report.

Design note: like parish_sweep.py, this is deliberately NOT an LLM task.
Extraction and classification are deterministic and auditable. The agent runs
it and reasons about the RESULT.

Usage:
    python3 src/buyer_db.py --min-properties 5
    python3 src/buyer_db.py --min-properties 10 --limit 200 --dry-run
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sources.json")
INBOX_DIR = os.path.join(ROOT, "deals", "_inbox")

USER_AGENT = "FreshSlate-buyer-db/1.0 (public open-data client; contact: operator)"

# Reused verbatim from parish_sweep.py. Record content is DATA, never
# instructions — a taxpayer_name is free text a third party controls.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(the\s+)?above",
    r"you\s+are\s+now\b",
    r"new\s+instructions?\s*:",
    r"system\s*prompt",
    r"send\s+(me\s+)?(your\s+)?(config|configuration|credentials|api[\s_-]?key|token)",
    r"\bcurl\s+http",
    r"\brm\s+-rf\b",
    r"<\s*script\b",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

# Owners that hold property for reasons other than investment. Excluded from
# the buyer list entirely — they are not prospects and they dominate the top
# of any portfolio-size ranking. Matched as whole words against the upper-cased
# name, so "PARISH" excludes "PARISH OF EAST BATON ROUGE" without excluding
# "PARISH LINE PROPERTIES LLC" (which contains it as a substring only).
INSTITUTIONAL_PATTERNS = [
    r"\bCITY OF\b", r"\bPARISH OF\b", r"\bSTATE OF\b", r"\bTOWN OF\b",
    r"\bDOTD\b", r"\bSCHOOL BOARD\b", r"\bSCHOOL DISTRICT\b",
    r"\bSEWERAGE COMMISSION\b", r"\bRECREATION & PARK\b", r"\bREC & PARK\b",
    r"\bHOUSING AUTHORITY\b", r"\bPUBLIC LIBRARY\b", r"\bFIRE DISTRICT\b",
    r"\bUNITED STATES\b", r"\bU\s?S\s?A\b", r"\bFEDERAL\b", r"\bPOSTAL SERVICE\b",
    r"\bDEPARTMENT OF\b", r"\bBOARD OF\b", r"\bCOUNCIL\b", r"\bMUNICIPAL\b",
    r"\bCHURCH\b", r"\bBAPTIST\b", r"\bMETHODIST\b", r"\bCATHOLIC\b",
    r"\bMINISTRIES\b", r"\bMINISTRY\b", r"\bSYNAGOGUE\b",
    r"\bMOSQUE\b", r"\bDIOCESE\b", r"\bCONGREGATION\b",
    r"\bHOSPITAL\b", r"\bMEDICAL CENTER\b", r"\bHEALTH SYSTEM\b",
    r"\bCEMETERY\b", r"\bRAILROAD\b", r"\bRAILWAY\b", r"\bPIPELINE\b",
    r"\bEXXON\b", r"\bENTERGY\b", r"\bCHEVRON\b", r"\bSHELL OIL\b",
    r"\bBELLSOUTH\b", r"\bAT&T\b", r"\bTELEPHONE\b", r"\bELECTRIC CO\b",
]
_INSTITUTIONAL_RE = re.compile("|".join(INSTITUTIONAL_PATTERNS))

# Words that are institutional in isolation but also appear in Baton Rouge
# street names and as surnames. Excluding on these alone produced false
# positives in QA (2026-08-12): "2100 COLLEGE DRIVE PARTNERSHIP" (College Dr
# is a street) and "TEMPLE, COLLIS B, JR" (a person holding 57 properties —
# i.e. exactly the prospect this list exists to find). Guarded below.
AMBIGUOUS_INSTITUTIONAL_PATTERNS = [
    r"\bUNIVERSITY\b", r"\bCOLLEGE\b", r"\bSEMINARY\b", r"\bTEMPLE\b",
]
_AMBIGUOUS_RE = re.compile("|".join(AMBIGUOUS_INSTITUTIONAL_PATTERNS))

_STREET_SUFFIX_RE = re.compile(
    r"\b(DR|DRIVE|ST|STREET|AVE|AVENUE|BLVD|BOULEVARD|RD|ROAD|LN|LANE|"
    r"WAY|CT|COURT|PL|PLACE|HWY|HIGHWAY|PKWY|PARKWAY)\b"
)
# This roll writes natural persons as "SURNAME, FIRST M". Matching that shape
# is what keeps a surname collision from deleting a real prospect.
_PERSON_NAME_RE = re.compile(r"^[A-Z][A-Za-z'\-]*,\s+[A-Z]")

# Name patterns suggesting the owner acquires property as a business.
# These BOOST rank; their absence does not exclude (many investors hold under
# a personal name or a neutral entity name).
INVESTOR_PATTERNS = [
    r"\bHOME ?BUYERS?\b", r"\bWE BUY\b", r"\bCASH\b", r"\bACQUISITIONS?\b",
    r"\bINVEST(MENT|MENTS|ORS?)?\b", r"\bPROPERT(Y|IES)\b", r"\bHOLDINGS?\b",
    r"\bREALTY\b", r"\bREAL ESTATE\b", r"\bRENTALS?\b", r"\bLEASING\b",
    r"\bCAPITAL\b", r"\bEQUITY\b", r"\bASSETS?\b", r"\bVENTURES?\b",
    r"\bPORTFOLIO\b", r"\bREI\b", r"\bHOMES? ?LLC\b",
]
_INVESTOR_RE = re.compile("|".join(INVESTOR_PATTERNS))

# Homebuilders / developers. Legitimate entities but a DIFFERENT segment from
# a distressed-property cash buyer: they build new, they do not typically buy
# someone else's rehab. Tagged separately so the operator can filter, not
# silently mixed into the buyer list.
BUILDER_PATTERNS = [
    r"\bCONSTRUCTION\b", r"\bBUILDERS?\b", r"\bBUILDING CO\b",
    r"\bDEVELOP(ERS?|MENT)\b", r"\bCONTRACTORS?\b", r"\bD R HORTON\b",
    r"\bDSLD\b", r"\bHOMEBUILDERS?\b",
]
_BUILDER_RE = re.compile("|".join(BUILDER_PATTERNS))

# Entity-suffix detection. An individual's name in this roll is "LAST, FIRST M".
ENTITY_PATTERNS = [
    r"\bL\.?\s?L\.?\s?C\.?\b", r"\bINC\.?\b", r"\bCORP(ORATION)?\b",
    r"\bL\.?\s?P\.?\b", r"\bLTD\.?\b", r"\bPARTNERSHIP\b", r"\bCOMPANY\b",
    r"\bTRUST\b", r"\bASSOCIATES?\b", r"\bGROUP\b", r"\bENTERPRISES?\b",
    r"\bFUND\b", r"\bSERIES\b",
]
_ENTITY_RE = re.compile("|".join(ENTITY_PATTERNS))


def log(msg):
    print(msg, file=sys.stderr)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def assert_host_permitted(config, domain):
    """Same hard gate as parish_sweep.py. Prohibited hosts are never requested."""
    for bad in config.get("prohibited_hosts", []):
        if domain == bad or domain.endswith("." + bad):
            raise PermissionError(
                f"BLOCKED: {domain} is on the prohibited-source list "
                f"(see deals/_config/parish-sources.md). Automated access is not permitted."
            )


def soda_get(domain, dataset, params, rate_limit, timeout=90):
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"https://{domain}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        req.add_header("X-App-Token", token)

    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            time.sleep(rate_limit)
            return data, url
        except urllib.error.HTTPError as e:
            if e.code == 429:
                backoff = 2 ** attempt
                log(f"  429 rate limited; backing off {backoff}s")
                time.sleep(backoff)
                continue
            raise
        except urllib.error.URLError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after retries: {url}")


def scan_injection(record):
    hits = []
    for k, v in record.items():
        if isinstance(v, str):
            m = _INJECTION_RE.search(v)
            if m:
                hits.append({"field": k, "text": v[:300]})
    return hits


def is_institutional(name):
    """True if this owner holds property for a non-investment reason.

    Order matters: the natural-person check runs first so a surname that
    collides with an institutional word (TEMPLE, CHURCH, BISHOP) does not
    delete a real prospect.
    """
    name = name.strip()
    up = name.upper()
    if _PERSON_NAME_RE.match(name):
        return False
    if _INSTITUTIONAL_RE.search(up):
        return True
    if _AMBIGUOUS_RE.search(up):
        # A street suffix or a leading house number means the name is derived
        # from an address ("2100 College Drive Partnership"), not an institution.
        if _STREET_SUFFIX_RE.search(up) or re.match(r"^\d+\s", up):
            return False
        return True
    return False


def classify(name):
    """Deterministic tags from the owner name. Documented, not a model judgment."""
    up = name.upper()
    tags = []
    owner_type = "entity" if _ENTITY_RE.search(up) else "individual"
    tags.append(owner_type)
    if _INVESTOR_RE.search(up):
        tags.append("investor-named")
    if _BUILDER_RE.search(up):
        tags.append("builder-developer")
    return owner_type, tags


def price_band(avg_val):
    """Bands over EBR fair market value.

    NOTE: `fair_market_val` in this dataset is the real market figure, not the
    10%-of-FMV assessed value (that is `total_value`/`taxpayer_val`). Verified
    against sample records where total_value == fair_market_val * 0.10.
    """
    if avg_val is None:
        return "unknown"
    if avg_val < 100_000:
        return "entry (<$100k)"
    if avg_val < 250_000:
        return "mid ($100k-$250k)"
    if avg_val < 500_000:
        return "upper ($250k-$500k)"
    return "premium ($500k+)"


def buyer_score(rec):
    """Deterministic ranking. Higher = better fit as a distressed-property cash buyer."""
    score = 0
    n = rec["property_count"]

    # Portfolio size is the primary signal, with diminishing returns: an owner
    # of 400 units is an institutional landlord, not a wholesale deal buyer.
    if n >= 100:
        score += 25
    elif n >= 40:
        score += 45
    elif n >= 15:
        score += 50
    elif n >= 8:
        score += 40
    else:
        score += 25

    if "investor-named" in rec["tags"]:
        score += 25
    if "builder-developer" in rec["tags"]:
        score -= 15  # different segment; keep but rank down
    if rec["owner_type"] == "entity":
        score += 10

    # Entry/mid price bands are where distressed wholesale product actually sits.
    band = rec["price_band"]
    if band.startswith("entry"):
        score += 20
    elif band.startswith("mid"):
        score += 15
    elif band.startswith("premium"):
        score -= 10

    if rec.get("mailing_address"):
        score += 5

    return score


def fetch_owners(config, parish_key, min_properties, limit):
    """Aggregate the tax roll by owner. Uses server-side $group so we never pull
    172k raw parcel rows to count them locally."""
    src = config["buyer_sources"][parish_key]
    domain = src["domain"]
    assert_host_permitted(config, domain)

    rate = config["rate_limit_seconds"]
    page = min(config["page_size"], limit) if limit else config["page_size"]

    select = (
        "taxpayer_name, taxpayer_addr_1, taxpayer_addr_2, count(*) AS n, "
        "avg(fair_market_val) AS avg_val, min(fair_market_val) AS min_val, "
        "max(fair_market_val) AS max_val, sum(fair_market_val) AS total_val"
    )
    where = src["where"].format(tax_year=src["tax_year"])

    collected, offset, url = [], 0, None
    while True:
        params = {
            "$select": select,
            "$where": where,
            "$group": "taxpayer_name, taxpayer_addr_1, taxpayer_addr_2",
            "$having": f"count(*) >= {min_properties}",
            "$order": "n DESC",
            "$limit": page,
            "$offset": offset,
        }
        rows, url = soda_get(domain, src["dataset"], params, rate)
        if not rows:
            break
        collected.extend(rows)
        log(f"    fetched {len(rows)} owner groups (total {len(collected)})")
        if limit and len(collected) >= limit:
            collected = collected[:limit]
            break
        if len(rows) < page:
            break
        offset += page

    return collected, url, src


def build(config, parish_key, min_properties, limit):
    retrieved_at = datetime.now(timezone.utc).isoformat()
    raw_rows, url, src = fetch_owners(config, parish_key, min_properties, limit)

    buyers, excluded_institutional, flagged = [], 0, []

    for raw in raw_rows:
        name = (raw.get("taxpayer_name") or "").strip()
        if not name:
            continue
        if is_institutional(name):
            excluded_institutional += 1
            continue

        injection = scan_injection(raw)

        def num(field):
            v = raw.get(field)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        avg_val = num("avg_val")
        owner_type, tags = classify(name)

        addr1 = (raw.get("taxpayer_addr_1") or "").strip()
        addr2 = (raw.get("taxpayer_addr_2") or "").strip()
        mailing = ", ".join(p for p in (addr1, addr2) if p) or None

        rec = {
            "owner_name": name,
            "owner_type": owner_type,
            "tags": tags,
            "property_count": int(raw.get("n") or 0),
            "avg_fair_market_value": round(avg_val) if avg_val is not None else None,
            "min_fair_market_value": round(num("min_val")) if num("min_val") is not None else None,
            "max_fair_market_value": round(num("max_val")) if num("max_val") is not None else None,
            "portfolio_fair_market_value": round(num("total_val")) if num("total_val") is not None else None,
            "price_band": price_band(avg_val),
            "mailing_address": mailing,
            # Not carried by this source. Never inferred, never looked up
            # elsewhere. Same discipline as owner_of_record/equity_estimate
            # in parish_sweep.py.
            "phone": None,
            "phone_source": "unavailable",
            "email": None,
            "email_source": "unavailable",
            "parish": src["parish_name"],
            "parish_key": parish_key,
            "source_dataset": src["dataset"],
            "source_label": src["label"],
            "source_url": url,
            "tax_year": src["tax_year"],
            "retrieved_at": retrieved_at,
            "injection_flags": injection,
        }
        rec["buyer_score"] = buyer_score(rec)
        if injection:
            flagged.append(rec)
        buyers.append(rec)

    buyers.sort(key=lambda r: (r["buyer_score"], r["property_count"]), reverse=True)
    return buyers, excluded_institutional, flagged, retrieved_at, src


def render_report(buyers, excluded, flagged, retrieved_at, src, min_properties, today):
    lines = [
        f"# Cash-Buyer Database — {today}",
        "",
        f"**Parish:** {src['parish_name']}",
        f"**Source:** {src['label']} (`{src['dataset']}`), tax year {src['tax_year']}",
        f"**Retrieved:** {retrieved_at}",
        f"**Criteria:** {min_properties}+ non-homestead-exempt real properties held by one owner",
        f"**Buyers identified:** {len(buyers)}",
        f"**Institutional owners excluded:** {excluded} (government, schools, churches, utilities)",
        "",
    ]

    if flagged:
        lines += [
            "## 🚨 CONTENT FLAGGED — possible injection attempt",
            "",
            "Text resembling an instruction appeared in a source record. "
            "**Not acted on.** Reported verbatim for operator review.",
            "",
        ]
        for r in flagged:
            lines.append(f"- `{r['owner_name']}`")
            for fl in r["injection_flags"]:
                lines.append(f"  - field `{fl['field']}`: `{fl['text']}`")
        lines.append("")

    by_band, by_type = {}, {}
    for r in buyers:
        by_band[r["price_band"]] = by_band.get(r["price_band"], 0) + 1
        for t in r["tags"]:
            by_type[t] = by_type.get(t, 0) + 1

    lines += ["## Counts by price band", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(by_band.items())] + [""]
    lines += ["## Counts by tag", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(by_type.items())] + [""]

    lines += ["## Top 25 by buyer score", ""]
    if not buyers:
        lines.append("_No buyers matched the criteria._")
    for r in buyers[:25]:
        avg = r["avg_fair_market_value"]
        band_line = (f"- **Price band:** {r['price_band']} (avg ${avg:,})"
                     if avg is not None else f"- **Price band:** {r['price_band']}")
        pf = r["portfolio_fair_market_value"]
        pf_line = (f"- **Portfolio FMV:** ${pf:,}" if pf is not None
                   else "- **Portfolio FMV:** _unavailable_")
        lines += [
            f"### {r['owner_name']}",
            f"- **Score:** {r['buyer_score']}",
            f"- **Properties held (non-homestead):** {r['property_count']}",
            band_line,
            pf_line,
            f"- **Type:** {', '.join(r['tags'])}",
            f"- **Mailing address:** {r['mailing_address'] or '_unavailable_'}",
            f"- **Phone:** _unavailable — not carried by this source_",
            f"- **Email:** _unavailable — not carried by this source_",
            f"- **Source:** {r['source_label']} (`{r['source_dataset']}`), tax year {r['tax_year']}",
            f"- **Retrieved:** {r['retrieved_at']}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Known limits — read before using this list",
        "",
        "1. **No phone numbers or email addresses.** The tax roll does not carry",
        "   them. They are not inferred, and no other source was consulted.",
        "   Every record here is contactable by **mail only** until entity",
        "   resolution (Louisiana Secretary of State → registered agent) is built",
        "   as a separate, permitted step.",
        "2. **\"Cash buyer\" here means \"holds multiple non-owner-occupied",
        "   properties\" — not \"purchased without a mortgage.\"** The operator's",
        "   readiness plan (Part 6) specifies conveyance records with no recorded",
        "   mortgage as the cash-purchase signal. Neither permitted portal",
        "   publishes conveyance/mortgage records, so that exact signal is not",
        "   computable. Portfolio size + absence of homestead exemption is the",
        "   substitute, and it is a weaker claim. Do not describe these as",
        "   verified cash purchasers.",
        "3. **Purchase frequency is not computable.** The tax roll is a snapshot of",
        "   current ownership, not a transaction history. Portfolio size is a",
        "   stock, not a flow — an owner of 40 units may have bought none this year.",
        "4. **East Baton Rouge only.** Orleans Parish publishes no owner-bearing",
        "   dataset through a permitted source (the Assessor is hard-blocked; code",
        "   enforcement carries no owner field). Jefferson Parish publishes no",
        "   usable open data at all. See `docs/SOURCE-RECON.md`.",
        "5. **Homestead exemption is a proxy for non-owner-occupied**, per",
        "   `deals/_config/parish-sources.md`. It is a documented field, not an",
        "   inference — but a second home or a recently-purchased residence can",
        "   also lack the exemption.",
        "",
        "_Produced by `src/buyer_db.py` from a permitted public open-data API._",
        "_This is a research list only. No buyer has been contacted._",
        "_Any outbound use must clear `compliance-gate` first (CAN-SPAM for email,_",
        "_and note that buyer-side **voice** remains behind the call-script gate)._",
    ]
    return "\n".join(lines)


def write_mail_csv(buyers, path, segment_note):
    """Mail-merge export. Mailing address is the ONLY contact channel this
    source carries, so it is the only one exported. `phone` and `email`
    columns are present but always empty — a downstream tool that expects
    them should see them absent, not silently missing."""
    cols = [
        "owner_name", "owner_type", "tags", "mailing_address",
        "property_count", "price_band", "avg_fair_market_value",
        "portfolio_fair_market_value", "buyer_score",
        "phone", "email",
        "parish", "source_dataset", "tax_year", "retrieved_at",
    ]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"# {segment_note}"])
        w.writerow(["# phone/email intentionally empty - not carried by the tax roll; never inferred"])
        w.writerow(cols)
        for r in buyers:
            w.writerow([
                r["owner_name"], r["owner_type"], "|".join(r["tags"]),
                r["mailing_address"] or "", r["property_count"], r["price_band"],
                r["avg_fair_market_value"] or "", r["portfolio_fair_market_value"] or "",
                r["buyer_score"], "", "",
                r["parish"], r["source_dataset"], r["tax_year"], r["retrieved_at"],
            ])


def core_segment(buyers):
    """The realistic distressed-property cash-buyer segment: active but not
    institutional, in the price bands wholesale product actually sits in,
    excluding new-construction builders, and reachable by mail."""
    return [
        r for r in buyers
        if "builder-developer" not in r["tags"]
        and r["price_band"].startswith(("entry", "mid"))
        and 8 <= r["property_count"] <= 60
        and r["mailing_address"]
    ]


def main():
    ap = argparse.ArgumentParser(description="Build the cash-buyer / investor-owner database")
    ap.add_argument("--parish", default="east_baton_rouge", help="Parish key (default: east_baton_rouge)")
    ap.add_argument("--min-properties", type=int, default=5,
                    help="Minimum non-homestead properties held to qualify (default: 5)")
    ap.add_argument("--limit", type=int, help="Max owner groups to fetch (testing)")
    ap.add_argument("--dry-run", action="store_true", help="Print the report, write nothing")
    ap.add_argument("--export-csv", action="store_true",
                    help="Also write mail-merge CSVs (full list + core prospect segment)")
    args = ap.parse_args()

    config = load_config()
    if args.parish not in config.get("buyer_sources", {}):
        log(f"FATAL: no buyer source configured for parish '{args.parish}'.")
        log(f"Configured: {list(config.get('buyer_sources', {}).keys())}")
        return 1

    log(f"=== Building buyer database: {args.parish} ===")
    try:
        buyers, excluded, flagged, retrieved_at, src = build(
            config, args.parish, args.min_properties, args.limit
        )
    except PermissionError as e:
        log(str(e))
        return 2

    today = datetime.now().strftime("%Y-%m-%d")
    report = render_report(buyers, excluded, flagged, retrieved_at, src,
                           args.min_properties, today)

    if args.dry_run:
        log("\n--- DRY RUN: nothing written ---")
        print(report)
        return 0

    os.makedirs(INBOX_DIR, exist_ok=True)
    report_path = os.path.join(INBOX_DIR, f"{today}-buyer-db.md")
    json_path = os.path.join(INBOX_DIR, f"{today}-buyer-db.json")
    with open(report_path, "w") as f:
        f.write(report)
    with open(json_path, "w") as f:
        json.dump(buyers, f, indent=2)

    log(f"\nWrote {report_path}")
    log(f"Wrote {json_path}")

    if args.export_csv:
        seg = core_segment(buyers)
        all_csv = os.path.join(INBOX_DIR, f"{today}-buyer-db-all.csv")
        seg_csv = os.path.join(INBOX_DIR, f"{today}-buyer-db-core-segment.csv")
        write_mail_csv(buyers, all_csv,
                       f"All identified investor-owners, {src['parish_name']}, "
                       f"{src['label']} tax year {src['tax_year']}")
        write_mail_csv(seg, seg_csv,
                       "Core prospect segment: 8-60 non-homestead properties, "
                       "entry/mid price band, excludes builder-developers")
        log(f"Wrote {all_csv} ({len(buyers)} rows)")
        log(f"Wrote {seg_csv} ({len(seg)} rows)")

    print(f"Buyer database built: {len(buyers)} buyers, "
          f"{excluded} institutional owners excluded, {len(flagged)} content flags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
