#!/usr/bin/env python3
"""
Act 807 compliance gate.

Deterministic policy check that runs OUTSIDE the language model. RAE's requirement:
"These must be counsel-owned, versioned transaction gates -- not merely warnings in
an agent prompt."

A model can be argued out of an instruction. It cannot be argued out of an if statement.

Design: FAIL CLOSED. If the control profile is not counsel-approved, every contract
fails the gate with an explanation. There is no flag, env var, or argument that
overrides this -- an override would defeat the entire purpose, and the person most
likely to reach for one is a person under deadline pressure.

Usage:
    python3 src/act807.py --check
    python3 src/act807.py --audit contract.txt
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, "deals", "_config", "act-807-controls.md")


class ControlProfile:
    def __init__(self, path=PROFILE):
        self.path = path
        self.approved = False
        self.status_line = "(missing)"
        self.params = {}
        self.conflicts = []
        self._parse()

    def _parse(self):
        if not os.path.exists(self.path):
            self.status_line = f"MISSING: {self.path}"
            return

        text = open(self.path).read()

        m = re.search(r"^\*\*Status:.*$", text, re.MULTILINE)
        self.status_line = m.group(0) if m else "(no status line)"
        upper = self.status_line.upper()

        # Approval requires an explicit APPROVED BY with a named person. "UNVERIFIED",
        # "NOT COUNSEL-APPROVED", or a bare "APPROVED" with no name all fail.
        self.approved = bool(
            re.search(r"APPROVED BY\s+\S+", upper)
            and "NOT COUNSEL-APPROVED" not in upper
            and "UNVERIFIED" not in upper
        )

        for row in re.finditer(r"^\|\s*`([a-z_0-9]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
                               text, re.MULTILINE):
            key, value, status = row.group(1), row.group(2).strip(), row.group(3).strip()
            self.params[key] = {"value": value, "status": status}
            if "CONFLICT" in value.upper():
                self.conflicts.append(key)

    def unresolved(self):
        """Parameters that are TBD, conflicting, or flagged unverified."""
        out = []
        for k, v in self.params.items():
            val, st = v["value"].upper(), v["status"].upper()
            if "TBD" in val or "CONFLICT" in val or "⛔" in st or "UNVERIFIED" in st:
                out.append(k)
        return out


def gate(profile):
    """
    Returns (passed: bool, findings: list[str]).

    Fails closed. There is deliberately no bypass parameter.
    """
    findings = []

    if not os.path.exists(profile.path):
        return False, [
            f"Act 807 control profile not found at {profile.path}. "
            "No contract may be passed without a counsel-approved control profile."
        ]

    if not profile.approved:
        findings.append(
            "⛔ **GATE CLOSED — control profile is not counsel-approved.**\n"
            f"   Status: {profile.status_line}\n"
            "   Act 807 (La. R.S. 37:1448.5) took effect 2026-08-01. Its requirements must be "
            "verified against the enrolled statutory text by a Louisiana attorney before any "
            "contract can be checked against them."
        )

    if profile.conflicts:
        for key in profile.conflicts:
            findings.append(
                f"⛔ **UNRESOLVED CONFLICT in `{key}`**: {profile.params[key]['value']}\n"
                "   Secondary sources disagree. This must be resolved against primary source "
                "by counsel. Guessing wrong makes the contract voidable at the seller's sole "
                "discretion until title transfers."
            )

    unresolved = [k for k in profile.unresolved() if k not in profile.conflicts]
    if unresolved:
        findings.append(
            "⛔ **UNVERIFIED PARAMETERS** (" + str(len(unresolved)) + "): "
            + ", ".join(f"`{k}`" for k in unresolved)
            + "\n   Each must be filled in by counsel with a statutory citation."
        )

    return (not findings), findings


def audit_contract(text, profile):
    """
    Screen contract text for Act 807 elements.

    Runs ONLY when the gate is open. Presence checks are not a legal opinion --
    they tell the operator what to hand the attorney, nothing more.
    """
    checks = []

    patterns = {
        "cancellation_notice": r"NOTICE REQUIRED BY LOUISIANA LAW",
        "wholesaling_intent": r"(assign|transfer|market).{0,80}(financial gain|profit|fee)",
        "legal_advice_advisory": r"seek (legal advice|the advice of|counsel)",
        "cancellation_right": r"right to cancel",
        "escrow": r"(escrow|neutral third party|title company|closing attorney)",
        "parish_not_county": r"\bcounty\b",
    }

    for name, pat in patterns.items():
        found = re.search(pat, text, re.IGNORECASE)
        if name == "parish_not_county":
            checks.append({
                "item": "Uses 'Parish' not 'County'",
                "result": "DEFECTIVE" if found else "PRESENT",
                "detail": f"found '{found.group(0)}'" if found else "no 'county' found",
            })
        else:
            checks.append({
                "item": name.replace("_", " ").title(),
                "result": "PRESENT" if found else "ABSENT",
                "detail": found.group(0)[:100] if found else "not found",
            })

    return checks


def main():
    ap = argparse.ArgumentParser(description="Act 807 compliance gate")
    ap.add_argument("--check", action="store_true", help="Report gate status and exit")
    ap.add_argument("--audit", metavar="FILE", help="Audit a contract file")
    args = ap.parse_args()

    profile = ControlProfile()
    passed, findings = gate(profile)

    print("# Act 807 Compliance Gate\n")
    print(f"**Profile:** `{profile.path}`")
    print(f"**Status:** {profile.status_line}")
    print(f"**Gate:** {'🟢 OPEN' if passed else '🔴 CLOSED'}\n")

    if findings:
        print("## Blocking findings\n")
        for f in findings:
            print(f"- {f}\n")

    if args.check:
        if not passed:
            print("---\n")
            print("**No contract can be audited against Act 807 until counsel completes and "
                  "approves `deals/_config/act-807-controls.md`.** This is intentional: the "
                  "gate fails closed rather than checking contracts against unverified rules.\n")
            print("This is not a bug to work around. It is the control working.")
        return 0 if passed else 1

    if args.audit:
        if not passed:
            print("---\n")
            print(f"⛔ **Refusing to audit `{args.audit}`.** The control profile is not "
                  "counsel-approved, so there is nothing trustworthy to audit against. "
                  "Resolve the findings above first.")
            return 1

        text = open(args.audit).read()
        print(f"## Contract audit: `{args.audit}`\n")
        print("| Item | Result | Detail |")
        print("|---|---|---|")
        for c in audit_contract(text, profile):
            print(f"| {c['item']} | **{c['result']}** | {c['detail']} |")
        print("\n---\n")
        print("**This is an automated checklist review, not legal advice and not a substitute "
              "for attorney review.** Every contract must be reviewed and approved by a "
              "licensed Louisiana real estate attorney before signature.")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
