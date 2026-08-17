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

    written = skipped = no_address = 0
    for r in records:
        kw = build(r)
        # Real parish records do carry null addresses (sheriff-sale rows keyed only
        # by case number). Import them anyway -- the parcel and case number are
        # still the operator's lead -- but never format a None.
        addr = r.get("situs_address") or f"(no address — parcel {r.get('parcel_id') or '?'})"
        if not r.get("situs_address"):
            no_address += 1
        if not args.apply:
            print(f"  [--] {addr[:44]:46} {r.get('signal_type','?')}")
            skipped += 1
            continue
        try:
            # No phone: keyed on parcel via custom field, so re-runs update rather
            # than duplicate only when GHL can match. Without a phone or email GHL
            # creates a new record, so guard on parcel first.
            c = g.upsert_contact(**kw)
            dropped = (c or {}).get("_dropped_fields")
            note = f"  dropped: {dropped}" if dropped else ""
            print(f"  [OK] {addr[:44]:46} id={(c or {}).get('id')}{note}")
            written += 1
        except Exception as e:
            print(f"  [!!] {addr[:44]:46} {type(e).__name__}: {str(e)[:90]}")

    print(f"\nwritten={written} dry_run={skipped} without_address={no_address}")
    if no_address:
        print(f"note: {no_address} record(s) carry no situs address — the source row "
              f"has none. Parcel/case number is retained; address is not inferred.")
    if not args.apply:
        print("Re-run with --apply to write.")


if __name__ == "__main__":
    main()
