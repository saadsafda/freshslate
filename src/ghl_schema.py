#!/usr/bin/env python3
"""
GHL schema provisioning.

Creates the custom fields a wholesaling operation needs. The account ships with
a default marketing setup (one field, a generic pipeline); this adds the
acquisition schema on top without disturbing what is already there.

Design notes:

  * Seller and buyer fields share one contact record but are namespaced by
    prefix (`fs_seller_*` / `fs_buyer_*`) plus a `fs_contact_type` discriminator.
    Module 13's playbook asks for both in one CRM "without colliding" -- the
    discriminator is what the dialer filters on so a homeowner can never be
    pulled into a realtor campaign.

  * `fs_dnc_status` and `fs_optout_date` are written on every opt-out. They are
    a human-readable mirror of GHL's own dnd flag, which is the actual
    enforcement point (see ghl.py). Two records of the same fact is deliberate:
    the flag suppresses, the field explains.

  * Idempotent. Re-running skips anything already present. Safe on a live
    account, which is why it diffs before writing and never deletes.

Usage:
    python3 src/ghl_schema.py --plan     # show what would change
    python3 src/ghl_schema.py --apply    # create missing fields
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ghl import GHL  # noqa: E402
from secrets_loader import require  # noqa: E402

# dataType values accepted by the LeadConnector v2 custom-field API:
#   TEXT, LARGE_TEXT, NUMERICAL, PHONE, MONETORY, CHECKBOX, SINGLE_OPTIONS,
#   MULTIPLE_OPTIONS, FLOAT, TIME, DATE, TEXTBOX_LIST, FILE_UPLOAD, SIGNATURE, RADIO
# "MONETORY" is spelled that way by the API. It is not a typo here.
FIELDS = [
    # --- routing / safety -------------------------------------------------
    ("fs_contact_type", "TEXT",
     "realtor | homeowner | buyer — dialer filters on this. Never blank."),
    ("fs_dnc_status", "TEXT",
     "clear | requested | suppressed — mirrors the dnd flag in readable form."),
    ("fs_optout_date", "TEXT", "ISO timestamp the opt-out was recorded."),
    ("fs_consent_basis", "TEXT",
     "Why this number may be called: b2b_listing | prior_business | written_consent."),
    ("fs_dnc_checked_at", "TEXT", "ISO timestamp of last DNC scrub."),

    # --- provenance -------------------------------------------------------
    ("fs_source_dataset", "TEXT", "Originating dataset id, e.g. Socrata u6yx-v2tw."),
    ("fs_source_url", "TEXT", "Direct link to the source record."),
    ("fs_retrieved_at", "TEXT", "ISO timestamp the record was pulled."),
    ("fs_parish", "TEXT", "Orleans | Jefferson | East Baton Rouge."),

    # --- property ---------------------------------------------------------
    ("fs_situs_address", "TEXT", "Property address (may differ from mailing)."),
    ("fs_parcel_id", "TEXT", "Parish parcel identifier."),
    ("fs_signal_type", "TEXT", "tax_delinquency | code_violation | foreclosure | succession."),
    ("fs_signal_strength", "NUMERICAL", "0-100 ranking score from the sweep."),
    ("fs_property_type", "TEXT", "SFR | 2-4 unit | other."),

    # --- underwriting -----------------------------------------------------
    ("fs_arv", "MONETORY", "After-repair value used in the MAO calculation."),
    ("fs_repair_estimate", "MONETORY", "Base-case repair total."),
    ("fs_mao_base", "MONETORY", "Maximum allowable offer, base case."),
    ("fs_underwrite_status", "TEXT", "not_started | preliminary | operator_approved."),

    # --- call outcome -----------------------------------------------------
    ("fs_last_call_at", "TEXT", "ISO timestamp of last completed call."),
    ("fs_call_outcome", "TEXT",
     "interested | not_interested | callback_booked | opt_out | no_answer | escalate_human."),
    ("fs_call_summary", "LARGE_TEXT", "Post-call summary written by the voice agent."),
    ("fs_callback_at", "TEXT", "Requested callback time, operator's timezone."),
    ("fs_escalation_reason", "TEXT",
     "Why a human must take over: attorney | succession_dispute | legal_question | distress."),
    ("fs_call_recording_url", "TEXT", "Retell recording link for audit."),

    # --- Act 807 ----------------------------------------------------------
    ("fs_act807_gate", "TEXT", "open | closed — deterministic gate result."),
    ("fs_act807_notes", "LARGE_TEXT", "Unresolved findings from the compliance gate."),
]

TAGS = [
    "freshslate-realtor",
    "freshslate-homeowner",
    "freshslate-do-not-call",
    "freshslate-optout-requested",
    "freshslate-escalate-human",
    "freshslate-callback-booked",
    "freshslate-underwritten",
]


def plan(g):
    existing = {f.get("fieldKey") for f in g.custom_fields()}
    missing = []
    for key, dtype, desc in FIELDS:
        if f"contact.{key}" not in existing and key not in existing:
            missing.append((key, dtype, desc))
    return existing, missing


def apply(g, missing):
    created, failed = [], []
    for key, dtype, desc in missing:
        body = {
            "name": key.replace("fs_", "FS ").replace("_", " ").title(),
            "dataType": dtype,
            "fieldKey": key,
            "model": "contact",
        }
        try:
            r = g._request("POST", f"/locations/{g.location_id}/customFields", body=body)
            fid = (r or {}).get("customField", {}).get("id") or (r or {}).get("id")
            created.append((key, fid))
            print(f"  created  {key:26} {dtype:12} id={fid}")
        except Exception as e:
            failed.append((key, str(e)[:160]))
            print(f"  FAILED   {key:26} {str(e)[:160]}")
    return created, failed


def main():
    ap = argparse.ArgumentParser(description="Provision GHL custom fields for Fresh Slate")
    ap.add_argument("--plan", action="store_true", help="show what would change")
    ap.add_argument("--apply", action="store_true", help="create missing fields")
    args = ap.parse_args()

    if not (args.plan or args.apply):
        ap.error("choose --plan or --apply")

    require("ghl")
    g = GHL()
    loc = g.location()
    print(f"Account: {loc.get('name')} ({loc.get('city')}, {loc.get('state')})\n")

    existing, missing = plan(g)
    print(f"Existing custom fields: {len(existing)}")
    print(f"Fields in Fresh Slate schema: {len(FIELDS)}")
    print(f"Missing: {len(missing)}\n")

    if not missing:
        print("Schema complete. Nothing to do.")
    elif args.plan:
        print("Would create:")
        for key, dtype, desc in missing:
            print(f"  {key:26} {dtype:12} {desc}")
        print("\nRun with --apply to create these.")
    else:
        print("Creating fields:")
        created, failed = apply(g, missing)
        print(f"\nCreated {len(created)}, failed {len(failed)}")
        if failed:
            print("\nFailures need manual creation in Settings > Custom Fields:")
            for k, e in failed:
                print(f"  {k}: {e}")

    print("\nTags to ensure exist (created automatically on first use):")
    for t in TAGS:
        print(f"  {t}")


if __name__ == "__main__":
    main()
