#!/usr/bin/env python3
"""
Parish sweep -> GoHighLevel.

Pushes sweep records into the CRM as contacts, carrying full provenance so the
operator can answer "where did this come from?" from inside GHL.

Two hard rules, both enforced here rather than downstream:

  1. Sweep records are HOMEOWNERS in distress. They are tagged
     `freshslate-homeowner` with `fs_contact_type=homeowner`, which the dialer's
     campaign gate uses to refuse any realtor-campaign dial. There is no flag on
     this script that can label them otherwise.

  2. Sweep records carry no phone number and none is invented. They import as
     research records. Calling them requires a separately sourced, DNC-scrubbed
     number and a homeowner campaign -- which itself requires --dnc-verified.

Usage:
    python3 src/sync_to_ghl.py --file deals/_inbox/2026-08-17-sweep.json --dry-run
    python3 src/sync_to_ghl.py --file ... --apply --limit 50
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ghl import GHL  # noqa: E402
from secrets_loader import require  # noqa: E402

FIELD_MAP = {
    "fs_situs_address": "situs_address",
    "fs_parcel_id": "parcel_id",
    "fs_signal_type": "signal_type",
    "fs_signal_strength": "signal_strength",
    "fs_parish": "parish",
    "fs_source_dataset": "source_dataset",
    "fs_source_url": "source_url",
    "fs_retrieved_at": "retrieved_at",
}

SELLER_PIPELINE = "Fresh Slate — Seller Acquisition"
INTAKE_STAGE = "1. Signal Identified"

# Sweep records carry no phone and no email, which drives two API constraints
# that are not obvious and were both found the hard way:
#
#   POST /contacts/upsert  400s without a phone or email. It cannot be used here.
#   POST /contacts/        succeeds but silently creates a DUPLICATE every run.
#
# So dedup is ours to do: search on the parcel ID before writing. A nightly
# sweep re-reports the same adjudicated parcels for months, and without this the
# board fills with copies of the same property.
DEDUP_TAG_PREFIX = "fs-parcel-"


def parcel_key(record):
    """Stable identity for a sweep record. Parcel first, then case number."""
    return (record.get("parcel_id") or record.get("source_case_no") or "").strip()


def find_by_parcel(g, parcel, cache=None):
    """
    Locate an existing contact for this parcel.

    Uses a per-run tag index rather than a search call per record -- the search
    endpoint does not reliably match on custom field values, and one API call
    per record is slow and burns rate limit on a 500-record sweep.
    """
    if cache is None or not parcel:
        return None
    return cache.get(parcel.lower())


def build_parcel_cache(g):
    """
    Map {parcel_id: contact} for everything previously imported by the sweep.

    Paginates the homeowner-tagged contacts once per run and indexes them on the
    fs_parcel_id custom field.
    """
    fmap = g.field_map()
    parcel_fid = fmap.get("contact.fs_parcel_id") or fmap.get("fs_parcel_id")
    if not parcel_fid:
        return {}

    cache, page = {}, 1
    while page <= 20:  # ceiling: 20 x 100 = 2000 contacts
        r = g._request("POST", "/contacts/search",
                       body={"locationId": g.location_id, "pageLimit": 100, "page": page})
        contacts = (r or {}).get("contacts", [])
        if not contacts:
            break
        for c in contacts:
            for f in c.get("customFields", []) or []:
                if f.get("id") == parcel_fid and f.get("value"):
                    cache[str(f["value"]).strip().lower()] = c
        page += 1
    return cache


def build(record):
    """One sweep record -> upsert kwargs. Owner name is used only if sourced."""
    custom = {"fs_contact_type": "homeowner"}
    for fkey, rkey in FIELD_MAP.items():
        val = record.get(rkey)
        if val not in (None, ""):
            custom[fkey] = val

    owner = record.get("owner_of_record")
    first = last = None
    if owner and record.get("owner_source") != "inferred":
        # Parish records are "LAST, FIRST MIDDLE".
        if "," in owner:
            last, _, rest = owner.partition(",")
            last, first = last.strip().title(), rest.strip().split(" ")[0].title()
        else:
            parts = owner.split()
            first, last = parts[0].title(), (parts[-1].title() if len(parts) > 1 else None)

    return {
        "first_name": first,
        "last_name": last,
        "tags": ["freshslate-homeowner"],
        "custom": custom,
        "source": f"Fresh Slate parish sweep ({record.get('source_dataset','unknown')})",
    }


def load_records(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("records", data.get("results", []))
    return data


def main():
    ap = argparse.ArgumentParser(description="Sync parish sweep records into GHL")
    ap.add_argument("--file", required=True, help="sweep JSON from parish_sweep.py")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--apply", action="store_true", help="write to the CRM")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--opportunities", action="store_true", default=True,
                    help="also open a deal in stage 1 (default on)")
    ap.add_argument("--no-opportunities", dest="opportunities", action="store_false",
                    help="import contacts only, no board cards")
    args = ap.parse_args()

    require("ghl")
    g = GHL()

    records = load_records(args.file)[: args.limit]
    print(f"Records : {len(records)}")
    print(f"Mode    : {'APPLY — writing to CRM' if args.apply else 'DRY RUN'}")
    print(f"Account : {g.location().get('name')}\n")

    print("!! These are homeowners in financial distress. They import as research")
    print("!! records tagged `freshslate-homeowner`. No phone number is created,")
    print("!! and the dialer will refuse them in any realtor campaign.\n")

    # Resolve the intake stage once. Missing pipeline is a hard stop, not a
    # silent skip -- contacts without opportunities are invisible on the board.
    pipeline = stage_id = None
    if args.opportunities:
        pls = {p["name"]: p for p in g.pipelines()}
        pipeline = pls.get(SELLER_PIPELINE)
        if not pipeline:
            sys.exit(f"error: pipeline {SELLER_PIPELINE!r} not found. "
                     f"Run: python3 src/ghl_pipelines.py --apply")
        match = [s for s in pipeline["stages"] if s["name"] == INTAKE_STAGE]
        if not match:
            sys.exit(f"error: stage {INTAKE_STAGE!r} not found in {SELLER_PIPELINE!r}")
        stage_id = match[0]["id"]
        print(f"Pipeline: {SELLER_PIPELINE} -> {INTAKE_STAGE}\n")

    cache = {}
    if args.apply:
        cache = build_parcel_cache(g)
        print(f"Indexed {len(cache)} previously-imported parcels for dedup\n")

    created = updated = opps = skipped = no_address = failed = 0
    for r in records:
        kw = build(r)
        # Real parish records do carry null addresses (sheriff-sale rows keyed only
        # by case number). Import them anyway -- the parcel and case number are
        # still the operator's lead -- but never format a None.
        addr = r.get("situs_address") or f"(no address — parcel {r.get('parcel_id') or '?'})"
        if not r.get("situs_address"):
            no_address += 1

        parcel = parcel_key(r)
        if not args.apply:
            dup = "  [would update]" if parcel.lower() in cache else ""
            print(f"  [--] {addr[:42]:44} {r.get('signal_type','?'):16}{dup}")
            skipped += 1
            continue

        try:
            existing = find_by_parcel(g, parcel, cache)
            if existing:
                cid = existing["id"]
                g._request("PUT", f"/contacts/{cid}",
                           body={"customFields": _cf_payload(g, kw["custom"])})
                print(f"  [UP] {addr[:42]:44} id={cid}")
                updated += 1
                continue

            body = {"locationId": g.location_id, "source": kw["source"],
                    "tags": kw["tags"], "customFields": _cf_payload(g, kw["custom"])}
            if kw.get("first_name"):
                body["firstName"] = kw["first_name"]
            if kw.get("last_name"):
                body["lastName"] = kw["last_name"]

            resp = g._request("POST", "/contacts/", body=body)
            c = (resp or {}).get("contact", resp) or {}
            cid = c.get("id")
            if not cid:
                raise RuntimeError("no contact id returned")
            if parcel:
                cache[parcel.lower()] = c
            created += 1

            if args.opportunities:
                name = f"{addr} — {r.get('signal_type','signal')}"
                o = g.create_opportunity(cid, pipeline["id"], stage_id, name[:120])
                oid = ((o or {}).get("opportunity") or {}).get("id")
                opps += 1 if oid else 0
                print(f"  [OK] {addr[:42]:44} id={cid} opp={oid}")
            else:
                print(f"  [OK] {addr[:42]:44} id={cid}")

        except Exception as e:
            failed += 1
            print(f"  [!!] {addr[:42]:44} {type(e).__name__}: {str(e)[:80]}")

    print(f"\ncreated={created} updated={updated} opportunities={opps} "
          f"failed={failed} dry_run={skipped} without_address={no_address}")
    if no_address:
        print(f"note: {no_address} record(s) carry no situs address — the source row "
              f"has none. Parcel/case number is retained; address is not inferred.")
    if not args.apply:
        print("Re-run with --apply to write.")


def _cf_payload(g, custom):
    """{fieldKey: value} -> [{id, value}], dropping unknown keys loudly."""
    fmap = g.field_map()
    out, dropped = [], []
    for key, val in (custom or {}).items():
        if val in (None, ""):
            continue
        fid = fmap.get(f"contact.{key}") or fmap.get(key)
        if fid:
            out.append({"id": fid, "value": str(val)})
        else:
            dropped.append(key)
    if dropped:
        print(f"       warning: unmapped fields dropped: {dropped}")
    return out


if __name__ == "__main__":
    main()
