#!/usr/bin/env python3
"""
GHL pipeline provisioning for a Louisiana wholesaling operation.

Creates two pipelines, because seller deals and buyer relationships have
genuinely different stage logic and forcing them into one board produces a
column that means different things depending on the record.

  Seller Acquisition   a property moving from signal to assigned contract
  Buyer / Disposition  a cash buyer moving from cold record to repeat buyer

Two things this encodes that a generic sales pipeline does not:

  * The Act 807 gate is its own stage. Louisiana requires written disclosures,
    a cancellation form, a deposit, and escrow BEFORE a wholesale contract is
    executed. That is not paperwork inside "Negotiation" -- it is a gate the
    deal either passes or does not, so it gets a stage where a stuck deal is
    visible on the board.

  * "Under Contract" is followed by a cancellation-period stage rather than
    going straight to assignment. The seller can rescind, and a board that
    shows a deal as done during a live cancellation window teaches the operator
    the wrong instinct.

Stage entry/exit criteria live in docs/GHL-PIPELINE.md -- the CRM stores stage
names, not the rules for moving between them.

Idempotent: existing pipelines with the same name are left alone. Additive
only; nothing is renamed or deleted.

Usage:
    python3 src/ghl_pipelines.py --plan
    python3 src/ghl_pipelines.py --apply
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ghl import GHL  # noqa: E402
from secrets_loader import require  # noqa: E402

SELLER_PIPELINE = "Fresh Slate — Seller Acquisition"
BUYER_PIPELINE = "Fresh Slate — Buyer / Disposition"

# (stage name, what it means, what must be true to LEAVE it)
SELLER_STAGES = [
    ("1. Signal Identified",
     "Distress signal found by the parish sweep. No contact attempted.",
     "Parcel and situs address confirmed; source cited."),
    ("2. Research / Underwriting",
     "Repair scope and MAO being prepared. Still no seller contact.",
     "MAO computed from an operator-approved cost table, with a range."),
    ("3. Owner Contact Attempted",
     "Human has attempted contact. DNC and consent basis recorded.",
     "Owner reached, or attempts exhausted per policy."),
    ("4. Conversation / Qualifying",
     "Owner is engaged. Motivation, timeline, and title questions open.",
     "Seller indicates willingness to consider an offer."),
    ("5. Offer Presented",
     "Written offer delivered by a human. Never by the agent.",
     "Seller accepts, counters, or declines."),
    ("6. Act 807 Compliance Gate",
     "HARD GATE. Disclosures, cancellation form, deposit, escrow verified "
     "before any contract is signed.",
     "Every Act 807 requirement satisfied and evidenced. Counsel-owned."),
    ("7. Under Contract",
     "PSA executed. Cancellation period is running.",
     "Cancellation window elapsed without rescission."),
    ("8. Cancellation Period Elapsed",
     "Seller's statutory right to cancel has expired.",
     "Confirmed in writing; deposit and escrow in order."),
    ("9. Assigned / Marketing to Buyers",
     "Equitable interest being marketed. Never the property itself.",
     "Assignment agreement executed with an end buyer."),
    ("10. Closed — Assigned", "Assignment fee collected at closing.", "Terminal."),
    ("11. Dead / Lost", "Deal did not proceed. Reason recorded.", "Terminal."),
]

BUYER_STAGES = [
    ("1. Identified",
     "Cash buyer found in public conveyance records. No contact yet.",
     "Entity resolved; duplicate LLCs merged to one buyer."),
    ("2. Contact Attempted", "Outreach attempted. Consent basis recorded.",
     "Buyer responds."),
    ("3. Qualifying", "Establishing parishes, price ceiling, rehab appetite.",
     "Buy box captured in custom fields."),
    ("4. Buy Box Confirmed", "Criteria known. Ready to receive matched deals.",
     "Buyer receives a deal matching their box."),
    ("5. Active — Deal Sent", "One or more deals under consideration.",
     "Buyer commits or passes."),
    ("6. Under Contract w/ Buyer", "Assignment agreement executed.",
     "Closing completes."),
    ("7. Closed — Repeat Buyer", "Has closed at least one deal. Priority list.",
     "Terminal (recurring)."),
    ("8. Inactive / Unqualified",
     "Not a fit, unresponsive, or opted out. Excluded from outreach.",
     "Terminal."),
]

PIPELINES = [
    (SELLER_PIPELINE, SELLER_STAGES),
    (BUYER_PIPELINE, BUYER_STAGES),
]


def existing_names(g):
    return {p.get("name"): p for p in g.pipelines()}


def create_pipeline(g, name, stages):
    body = {
        "locationId": g.location_id,
        "name": name,
        "stages": [{"name": s[0], "position": i} for i, s in enumerate(stages)],
    }
    r = g._request("POST", "/opportunities/pipelines", body=body)
    return (r or {}).get("pipeline")


def main():
    ap = argparse.ArgumentParser(description="Provision Fresh Slate GHL pipelines")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not (args.plan or args.apply):
        ap.error("choose --plan or --apply")

    require("ghl")
    g = GHL()
    print(f"Account: {g.location().get('name')}\n")

    have = existing_names(g)
    for name, stages in PIPELINES:
        if name in have:
            print(f"EXISTS  {name}  ({len(have[name].get('stages', []))} stages) — skipping")
            continue

        if args.plan:
            print(f"WOULD CREATE  {name}")
            for i, (sname, meaning, exit_rule) in enumerate(stages):
                print(f"    {i}. {sname}")
                print(f"       {meaning}")
                print(f"       exit: {exit_rule}")
            print()
        else:
            p = create_pipeline(g, name, stages)
            print(f"CREATED  {name}  id={(p or {}).get('id')}  "
                  f"{len((p or {}).get('stages', []))} stages")

    if args.plan:
        print("Run with --apply to create.")
    else:
        print("\nNote: the default 'Marketing Pipeline' is left untouched. Remove it in the "
              "GHL UI once you have migrated anything you care about.")


if __name__ == "__main__":
    main()
