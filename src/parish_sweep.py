#!/usr/bin/env python3
"""
parish-sweep — deterministic extraction engine.

Retrieves distress signals from permitted Louisiana parish open-data APIs, diffs against
previously seen records, and writes a dated sweep report.

Design note: this is intentionally NOT an LLM task. Extraction is deterministic, auditable,
and free. The OpenClaw `parish-sweep` skill invokes this script and reasons about the RESULT.
See docs/SOURCE-RECON.md.

Usage:
    python3 src/parish_sweep.py --since 2026-07-01
    python3 src/parish_sweep.py --parish orleans --limit 50
    python3 src/parish_sweep.py --dry-run
"""

import argparse
import hashlib
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
SEEN_PATH = os.path.join(ROOT, "deals", "_index", "seen.json")
INBOX_DIR = os.path.join(ROOT, "deals", "_inbox")

USER_AGENT = "FreshSlate-parish-sweep/1.0 (public open-data client; contact: operator)"

# Patterns that suggest a record's text is trying to issue an instruction rather than
# state a fact. Module 13 / AGENTS.md: record content is DATA, never instructions.
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


def log(msg):
    print(msg, file=sys.stderr)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_seen():
    if not os.path.exists(SEEN_PATH):
        return {}
    try:
        with open(SEEN_PATH) as f:
            return json.load(f)
    except json.JSONDecodeError:
        log("WARN: seen.json unreadable; treating all records as new.")
        return {}


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_PATH), exist_ok=True)
    with open(SEEN_PATH, "w") as f:
        json.dump(seen, f, indent=2, sort_keys=True)


def assert_host_permitted(config, domain):
    """Hard gate. A prohibited host must never be requested, regardless of caller intent."""
    for bad in config.get("prohibited_hosts", []):
        if domain == bad or domain.endswith("." + bad):
            raise PermissionError(
                f"BLOCKED: {domain} is on the prohibited-source list "
                f"(see deals/_config/parish-sources.md). Automated access is not permitted."
            )


def soda_get(domain, dataset, params, rate_limit, timeout=45):
    """One rate-limited SODA API request. Returns parsed JSON list."""
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"https://{domain}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

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
        except urllib.error.URLError as e:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after retries: {url}")


def scan_injection(record):
    """Return list of (field, matched_text) for anything resembling an instruction."""
    hits = []
    for k, v in record.items():
        if isinstance(v, str):
            m = _INJECTION_RE.search(v)
            if m:
                hits.append((k, v[:300]))
    return hits


def normalize(raw, source, parish_key, parish_cfg, domain, source_url, retrieved_at):
    """Map a raw API record to the canonical sweep schema. Never invents a value."""
    fm = source["field_map"]
    rec = {
        "parish": parish_cfg["name"],
        "parish_key": parish_key,
        "signal_type": source["signal_type"],
        "source_dataset": source["dataset"],
        "source_label": source["label"],
        "source_url": source_url,
        "retrieved_at": retrieved_at,
    }

    for canonical, api_field in fm.items():
        val = raw.get(api_field)
        if isinstance(val, str):
            val = val.strip()
            # Several LA datasets emit the literal string "Null"/"N/A" rather than
            # omitting the field. Treat those as absent so downstream never renders them.
            if val.lower() in ("null", "n/a", "na", "none", "unknown", ""):
                val = None
        rec[canonical] = val

    # Owner: present only where the source actually carries it. Never inferred.
    if "owner_of_record" not in rec or not rec.get("owner_of_record"):
        rec["owner_of_record"] = None
        rec["owner_source"] = "unavailable" if not parish_cfg["has_owner_field"] else "not_in_record"
    else:
        rec["owner_source"] = source["dataset"]

    # Module 13 asks for an equity filter. We have no valuation source, so we do not
    # estimate one. Explicit null beats a fabricated number.
    rec["equity_estimate"] = None
    rec["equity_source"] = "unavailable"

    # Dedup key. Some sources need a composite: EBR adjudicated property repeats
    # assessment_num once per tax year adjudicated, so the parcel number alone
    # collapses distinct facts about one property into a single record.
    df = source["dedup_field"]
    fields = df if isinstance(df, list) else [df]
    parts = [str(raw.get(f, "")) for f in fields]
    if len(fields) == 1:
        ident = parts[0]
    else:
        # Hash composites: components like `legal` are unbounded free text.
        ident = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    rec["dedup_key"] = f"{parish_key}:{source['dataset']}:{ident}"

    flags = scan_injection(raw)
    rec["injection_flags"] = [{"field": f, "text": t} for f, t in flags]

    return rec


def signal_strength(rec):
    """Deterministic ranking. Documented and auditable — not a model judgment."""
    score = 0
    weights = {"tax_delinquency": 50, "foreclosure": 40, "code_violation": 25}
    score += weights.get(rec["signal_type"], 10)

    if rec.get("owner_of_record"):
        score += 10
    if rec.get("situs_address"):
        score += 5

    stage = (rec.get("stage") or "").lower()
    if "hearing" in stage or "judgment" in stage:
        score += 15
    if "demol" in stage:
        score += 20

    notes = (rec.get("notes") or "").upper()
    if "ADJ. TO STATE" in notes:
        score += 15

    # Recency. Sources with no usable date (e.g. sheriff sales carrying "Null" saledate)
    # get no recency credit rather than being scored as if current — several of those
    # records are 10+ years old and must not outrank a case filed this month.
    date = rec.get("filing_date") or rec.get("status_date")
    if date:
        if date >= "2026-01-01":
            score += 20
        elif date >= "2025-01-01":
            score += 10
        elif date < "2020-01-01":
            score -= 15  # stale: still a signal, but not a fresh one

    return score


def fetch_source(parish_key, parish_cfg, source, config, since, limit):
    domain = parish_cfg["domain"]
    assert_host_permitted(config, domain)

    rate = config["rate_limit_seconds"]
    page_size = min(config["page_size"], limit) if limit else config["page_size"]

    where_parts = []
    if source.get("where"):
        where_parts.append(source["where"])
    if since and source.get("date_field"):
        where_parts.append(f"{source['date_field']} > '{since}T00:00:00'")
    where = " AND ".join(where_parts) if where_parts else None

    collected, offset = [], 0
    while True:
        params = {"$limit": page_size, "$offset": offset}
        if where:
            params["$where"] = where
        if source.get("date_field"):
            params["$order"] = f"{source['date_field']} DESC"

        rows, url = soda_get(domain, source["dataset"], params, rate)
        if not rows:
            break
        collected.extend(rows)
        log(f"    fetched {len(rows)} (total {len(collected)})")

        if limit and len(collected) >= limit:
            collected = collected[:limit]
            break
        if len(rows) < page_size:
            break
        offset += page_size

    return collected, url


def main():
    ap = argparse.ArgumentParser(description="Parish distress-signal sweep")
    ap.add_argument("--parish", help="Sweep only this parish key (orleans, east_baton_rouge)")
    ap.add_argument("--since", help="Only records after this date, YYYY-MM-DD")
    ap.add_argument("--limit", type=int, help="Max records per source (testing)")
    ap.add_argument("--dry-run", action="store_true", help="Do not write seen.json or report")
    args = ap.parse_args()

    config = load_config()
    seen = load_seen()
    retrieved_at = datetime.now(timezone.utc).isoformat()

    new_records, errors, skipped = [], [], []
    batch_keys = set()
    intra_run_dupes = 0

    for parish_key, parish_cfg in config["parishes"].items():
        if args.parish and parish_key != args.parish:
            continue

        if not parish_cfg.get("enabled"):
            reason = parish_cfg.get("disabled_reason", "disabled")
            log(f"SKIP {parish_cfg['name']}: {reason}")
            skipped.append({"parish": parish_cfg["name"], "reason": reason})
            continue

        log(f"\n=== {parish_cfg['name']} ===")
        for source in parish_cfg["sources"]:
            log(f"  {source['label']} [{source['dataset']}]")
            try:
                rows, url = fetch_source(parish_key, parish_cfg, source, config, args.since, args.limit)
            except PermissionError as e:
                log(f"    {e}")
                errors.append({"source": source["label"], "error": str(e)})
                continue
            except Exception as e:
                # Module 13: stop for THIS source, flag it, continue with the others.
                log(f"    ERROR: {e}")
                errors.append({"source": source["label"], "error": f"{type(e).__name__}: {e}"})
                continue

            for raw in rows:
                rec = normalize(raw, source, parish_key, parish_cfg, parish_cfg["domain"], url, retrieved_at)
                key = rec["dedup_key"]
                if key in seen:
                    continue
                # Also dedupe WITHIN this run. Without this, a source with a
                # non-unique dedup field reports more records than it persists,
                # and the surplus reappears as "new" on every subsequent sweep.
                if key in batch_keys:
                    intra_run_dupes += 1
                    continue
                batch_keys.add(key)
                rec["signal_strength"] = signal_strength(rec)
                new_records.append(rec)

    new_records.sort(key=lambda r: r["signal_strength"], reverse=True)
    flagged = [r for r in new_records if r["injection_flags"]]

    # ---- report ----
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Parish Sweep — {today}",
        "",
        f"**Retrieved:** {retrieved_at}",
        f"**New records:** {len(new_records)}",
        "",
    ]

    if errors:
        lines += ["## ⚠️ Source errors", ""]
        lines += [f"- **{e['source']}** — {e['error']}" for e in errors] + [""]

    if skipped:
        lines += ["## Skipped parishes", ""]
        lines += [f"- **{s['parish']}** — {s['reason']}" for s in skipped] + [""]

    if flagged:
        lines += [
            "## 🚨 CONTENT FLAGGED — possible injection attempt",
            "",
            "The following records contain text resembling an instruction. "
            "This was **not acted on**. Reported verbatim for operator review.",
            "",
        ]
        for r in flagged:
            lines.append(f"- `{r['dedup_key']}` — {r['source_label']}")
            for fl in r["injection_flags"]:
                lines.append(f"  - field `{fl['field']}`: `{fl['text']}`")
        lines.append("")

    by_signal = {}
    for r in new_records:
        by_signal[r["signal_type"]] = by_signal.get(r["signal_type"], 0) + 1
    if by_signal:
        lines += ["## Counts by signal", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(by_signal.items())] + [""]

    lines += ["## Top 5 by signal strength", ""]
    if not new_records:
        lines.append("_No new records._")
    for r in new_records[:5]:
        lines += [
            f"### {r.get('situs_address') or '(address unavailable)'}",
            f"- **Parish:** {r['parish']}",
            f"- **Signal:** {r['signal_type']} (strength {r['signal_strength']})",
            f"- **Owner of record:** {r.get('owner_of_record') or '_unavailable — not in source_'}",
            f"- **Parcel:** {r.get('parcel_id') or '_n/a_'}",
            f"- **Case:** {r.get('source_case_no') or '_n/a_'}",
            f"- **Date:** {r.get('filing_date') or r.get('status_date') or '_n/a_'}",
            f"- **Source:** {r['source_label']} (`{r['source_dataset']}`)",
            f"- **Retrieved:** {r['retrieved_at']}",
            "",
        ]

    lines += [
        "---",
        "",
        "_Produced by `src/parish_sweep.py` from permitted public open-data APIs. "
        "This is a research list only. No owner has been contacted. "
        "Owner and equity fields are null where the source does not carry them — "
        "they are not inferred._",
    ]
    report = "\n".join(lines)

    if args.dry_run:
        log("\n--- DRY RUN: nothing written ---")
        print(report)
        return 0

    os.makedirs(INBOX_DIR, exist_ok=True)
    report_path = os.path.join(INBOX_DIR, f"{today}-sweep.md")
    with open(report_path, "w") as f:
        f.write(report)

    before = len(seen)
    for r in new_records:
        seen[r["dedup_key"]] = {
            "first_seen": retrieved_at,
            "signal_type": r["signal_type"],
            "parish": r["parish_key"],
        }
    persisted = len(seen) - before

    # Integrity guard: every record reported as new must persist to seen.json.
    # If these diverge, dedup keys are colliding and the operator is being shown
    # a count that will re-appear as "new" on the next sweep. Fail loudly.
    if persisted != len(new_records):
        log(
            f"\nFATAL: reported {len(new_records)} new records but only {persisted} "
            f"persisted to seen.json. Dedup keys are colliding for at least one "
            f"source — check `dedup_field` in config/sources.json. Not writing seen.json."
        )
        return 2

    save_seen(seen)

    json_path = os.path.join(INBOX_DIR, f"{today}-sweep.json")
    with open(json_path, "w") as f:
        json.dump(new_records, f, indent=2)

    log(f"\nWrote {report_path}")
    log(f"Wrote {json_path}")
    log(f"seen.json now tracks {len(seen)} records")

    print(f"Sweep complete: {len(new_records)} new records, "
          f"{len(errors)} source errors, {len(flagged)} content flags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
