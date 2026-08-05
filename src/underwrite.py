#!/usr/bin/env python3
"""
Underwriting calculator.

Parses the operator's cost table and computes MAO deterministically.

Why this is not the model's job: an LLM doing arithmetic across 30 line items will
occasionally get it wrong, and the error is invisible because the output still looks
like a number. Module 13 requires showing every step of the math. Here the model
produces the SCOPE (what is broken, from photos) and this computes the MONEY.

Usage:
    python3 src/underwrite.py --check-costs
    python3 src/underwrite.py --scope scope.json --arv 185000
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COSTS_PATH = os.path.join(ROOT, "deals", "_config", "costs-la.md")


class CostTable:
    """Parsed operator cost table, with approval state."""

    def __init__(self, path=COSTS_PATH):
        self.path = path
        self.items = {}
        self.params = {}
        self.approved = False
        self.approval_line = ""
        self.mao_multiplier = None
        self._parse()

    def _parse(self):
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Cost table not found: {self.path}")

        with open(self.path) as f:
            text = f.read()

        # Approval state. Anything other than an explicit APPROVED is treated as
        # unapproved -- fail closed, not open.
        m = re.search(r"^\*\*Status:.*$", text, re.MULTILINE)
        self.approval_line = m.group(0) if m else "(no status line)"
        self.approved = bool(m and "APPROVED" in m.group(0).upper()
                             and "NOT OPERATOR-APPROVED" not in m.group(0).upper())

        # Table rows: | Item | Unit | $Cost | Notes |
        for row in re.finditer(
            r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*\$?([\d,]+(?:\.\d+)?)\s*%?\s*\|", text, re.MULTILINE
        ):
            name, unit, cost = row.group(1).strip(), row.group(2).strip(), row.group(3)
            if name.lower() in ("item", "parameter") or set(name) <= set("-: "):
                continue
            try:
                self.items[name.lower()] = {
                    "name": name,
                    "unit": unit,
                    "cost": float(cost.replace(",", "")),
                }
            except ValueError:
                continue

        # Deal parameters
        for key, pat in [
            ("contingency_pct", r"Contingency %\s*\|\s*(\d+(?:\.\d+)?)\s*%"),
            ("assignment_fee", r"Target assignment fee\s*\|\s*\$?([\d,]+)"),
            ("holding_cost_month", r"Holding cost / month\s*\|\s*\$?([\d,]+)"),
        ]:
            m = re.search(pat, text)
            if m:
                self.params[key] = float(m.group(1).replace(",", ""))

        m = re.search(r"ARV\s*×\s*(0?\.\d+)", text)
        if m:
            self.mao_multiplier = float(m.group(1))

    def lookup(self, item_name):
        """Exact match, then substring. Returns None rather than guessing a price."""
        key = item_name.lower().strip()
        if key in self.items:
            return self.items[key]
        matches = [v for k, v in self.items.items() if key in k or k in key]
        return matches[0] if len(matches) == 1 else None

    def warning_banner(self):
        if self.approved:
            return None
        return (
            "⚠️ **PRELIMINARY — NOT OPERATOR-APPROVED COSTS.** This estimate uses placeholder "
            "figures from `deals/_config/costs-la.md`, which has not been reviewed or approved "
            "by the operator. Do not use it to make an offer. "
            f"Current status: {self.approval_line}"
        )


def compute(scope_lines, arv, costs, assignment_fee=None, contingency_pct=None):
    """
    Compute repair total and MAO. Every step is recorded for display.

    scope_lines: [{"item","quantity","unit_cost"(optional),"confidence"}]
    Returns a dict including three MAO scenarios.
    """
    priced, unpriced = [], []
    subtotal = 0.0

    for line in scope_lines:
        qty = float(line.get("quantity", 0) or 0)
        unit_cost = line.get("unit_cost")

        if unit_cost is None:
            found = costs.lookup(line["item"])
            if found:
                unit_cost = found["cost"]
                source = f"cost table: {found['name']} ({found['unit']})"
            else:
                # No price and no table match. Never invent one.
                unpriced.append({
                    "item": line["item"],
                    "quantity": qty,
                    "reason": "no matching entry in cost table",
                })
                continue
        else:
            unit_cost = float(unit_cost)
            source = "explicit in scope"

        extended = qty * unit_cost
        subtotal += extended
        priced.append({
            "item": line["item"],
            "quantity": qty,
            "unit_cost": unit_cost,
            "extended": extended,
            "confidence": line.get("confidence", "unknown"),
            "cost_source": source,
        })

    cpct = contingency_pct if contingency_pct is not None else costs.params.get("contingency_pct", 15.0)
    fee = assignment_fee if assignment_fee is not None else costs.params.get("assignment_fee", 12500.0)
    mult = costs.mao_multiplier or 0.70

    contingency = subtotal * (cpct / 100.0)
    repair_total = subtotal + contingency

    # Three scenarios differ ONLY in the repair assumption. Stating the single
    # varying assumption is what makes the range meaningful rather than decorative.
    scenarios = {}
    for label, factor, assumption in [
        ("conservative", 1.25, "repairs run 25% over scope (hidden damage found)"),
        ("base", 1.00, "repairs land at scope + contingency"),
        ("aggressive", 0.85, "repairs come in 15% under scope (best case)"),
    ]:
        rt = repair_total * factor
        scenarios[label] = {
            "repair_total": round(rt, 2),
            "mao": round((arv * mult) - rt - fee, 2),
            "assumption": assumption,
        }

    # Confidence: how much of the priced dollar value rests on low-confidence lines.
    low = sum(l["extended"] for l in priced if str(l.get("confidence", "")).lower() == "low")
    low_pct = round(low / subtotal * 100, 1) if subtotal else 0.0

    # Thin-evidence guard. A rehab scope built from a handful of exterior shots is
    # arithmetic, not an estimate -- and the danger is that it still LOOKS like a
    # number. Flag it so the figures cannot travel on their own.
    reasons = []
    if len(priced) < 5:
        reasons.append(f"only {len(priced)} priced line item(s)")
    if low_pct >= 60:
        reasons.append(f"{low_pct}% of value on LOW-confidence lines")
    thin = None
    if reasons:
        thin = ("Scope is too thin to support a repair estimate: "
                + "; ".join(reasons) + ".")

    return {
        "arv": arv,
        "mao_multiplier": mult,
        "line_items": priced,
        "unpriced_items": unpriced,
        "subtotal": round(subtotal, 2),
        "contingency_pct": cpct,
        "contingency": round(contingency, 2),
        "repair_total": round(repair_total, 2),
        "assignment_fee": fee,
        "scenarios": scenarios,
        "low_confidence_pct": low_pct,
        "thin_evidence": thin,
        "costs_approved": costs.approved,
        "warning": costs.warning_banner(),
    }


def render(result):
    """Markdown output showing every step of the math."""
    L = []
    if result["warning"]:
        L += [result["warning"], ""]

    L += ["## Line-item scope", "",
          "| Item | Qty | Unit cost | Extended | Confidence | Source |",
          "|---|---:|---:|---:|---|---|"]
    for l in result["line_items"]:
        L.append(f"| {l['item']} | {l['quantity']:g} | ${l['unit_cost']:,.2f} | "
                 f"${l['extended']:,.2f} | {l['confidence']} | {l['cost_source']} |")

    if result["unpriced_items"]:
        L += ["", "### ⚠️ Could not price", "",
              "No matching entry in the cost table. **Not included in the total** — "
              "a missing price is reported, never guessed.", ""]
        for u in result["unpriced_items"]:
            L.append(f"- **{u['item']}** (qty {u['quantity']:g}) — {u['reason']}")

    L += ["", "## Math", "",
          f"- Subtotal: **${result['subtotal']:,.2f}**",
          f"- Contingency ({result['contingency_pct']:g}%): **${result['contingency']:,.2f}**",
          f"- **Repair total: ${result['repair_total']:,.2f}**",
          "",
          f"- ARV: ${result['arv']:,.2f}",
          f"- MAO multiplier: {result['mao_multiplier']}",
          f"- Assignment fee: ${result['assignment_fee']:,.2f}",
          "",
          "## MAO — three scenarios", "",
          "| Scenario | Repair total | MAO | Varying assumption |",
          "|---|---:|---:|---|"]
    for name in ("conservative", "base", "aggressive"):
        s = result["scenarios"][name]
        L.append(f"| {name.title()} | ${s['repair_total']:,.2f} | "
                 f"**${s['mao']:,.2f}** | {s['assumption']} |")

    L += ["", f"_{result['low_confidence_pct']}% of priced value rests on LOW-confidence lines._"]

    if result.get("thin_evidence"):
        L += ["", "> ### ⚠️ THIN EVIDENCE — TREAT THESE NUMBERS AS A PLACEHOLDER",
              ">",
              f"> {result['thin_evidence']}",
              ">",
              "> The figures above are arithmetic on a scope that the photographs do not "
              "support. They are not an estimate of this property's repair cost. Obtain "
              "interior and systems photographs, or an inspection, before relying on any "
              "number here."]

    L += ["",
          "---",
          "",
          "**This is a decision-support estimate produced from photographs, not an inspection.** "
          "No point estimate is presented without a range. Verify before making any offer."]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-costs", action="store_true", help="Validate the cost table and exit")
    ap.add_argument("--scope", help="JSON file with scope line items")
    ap.add_argument("--arv", type=float, help="After-repair value")
    ap.add_argument("--fee", type=float, help="Override assignment fee")
    args = ap.parse_args()

    costs = CostTable()

    if args.check_costs:
        print(f"Cost table: {costs.path}")
        print(f"Status line: {costs.approval_line}")
        print(f"Approved: {costs.approved}")
        print(f"Line items parsed: {len(costs.items)}")
        print(f"MAO multiplier: {costs.mao_multiplier}")
        print(f"Parameters: {costs.params}")
        if not costs.approved:
            print("\n" + costs.warning_banner())
        return 0

    if not args.scope or args.arv is None:
        ap.error("--scope and --arv are required (or use --check-costs)")

    with open(args.scope) as f:
        scope = json.load(f)
    if isinstance(scope, dict):
        scope = scope.get("line_items", [])

    print(render(compute(scope, args.arv, costs, assignment_fee=args.fee)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
