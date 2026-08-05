# Gulf South Repair Cost Table

**Status: TESTING — placeholder costs, cleared for development only. NOT FOR REAL OFFERS.**

**Owner:** [Operator name]
**Last updated:** 2026-08-05 — status set to TESTING to unblock skill development
**Approved by:** _nobody — these are Claude-generated placeholder figures, never reviewed by an operator_

---

## Read this first

Every number below is a **placeholder**. They are order-of-magnitude figures for South
Louisiana, included so the `underwrite` skill can be built and tested before the operator's
real numbers arrive.

Module 13 is explicit: **"Apply the Gulf South cost table. Do NOT use national averages."**

Until the operator replaces these and changes the status line at the top of this file to
`APPROVED`, the `underwrite` skill must stamp every output:

> ⚠️ PRELIMINARY — built on placeholder costs, not operator-approved figures.

**How to approve:** replace the numbers, set `Status: APPROVED BY [name] ON [date]`, and
`underwrite` will drop the warning automatically.

---

## Roofing

| Item | Unit | Placeholder | Notes |
|---|---|---|---|
| Architectural shingle, tear-off + replace | per square (100 sf) | $450 | Gulf wind rating |
| 3-tab shingle | per square | $350 | |
| Metal roof | per square | $900 | |
| Decking replacement | per sheet | $95 | common after storm damage |
| Ridge vent | per lf | $12 | |
| Flashing / boot replacement | each | $150 | |

## Exterior

| Item | Unit | Placeholder | Notes |
|---|---|---|---|
| Hardie / fiber cement siding | per sf | $9 | |
| Vinyl siding | per sf | $5 | |
| Wood siding repair | per sf | $12 | common on shotguns/doubles |
| Exterior paint | per sf wall | $2.50 | |
| Soffit / fascia | per lf | $18 | |
| Window, vinyl replacement | each | $550 | |
| Exterior door | each | $850 | |

## Foundation (critical in South Louisiana)

| Item | Unit | Placeholder | Notes |
|---|---|---|---|
| Pier leveling / shimming | per pier | $350 | |
| Pier replacement | per pier | $650 | |
| Sill plate repair | per lf | $85 | termite/rot common |
| Slab crack repair | per lf | $95 | |
| Full re-level, raised pier home | lump | $12,000 | typical 1,200 sf |

## Systems

| Item | Unit | Placeholder | Notes |
|---|---|---|---|
| Full rewire | per sf | $7 | knob-and-tube / cloth wiring |
| Panel replacement, 200A | each | $2,800 | |
| HVAC, 3-ton split system | each | $8,500 | |
| Ductwork replacement | per sf | $4 | |
| Water heater, 40gal | each | $1,600 | |
| Full repipe (PEX) | per fixture | $850 | |
| Sewer line replacement | per lf | $150 | |

## Interior

| Item | Unit | Placeholder | Notes |
|---|---|---|---|
| Sheetrock, hang + finish | per sf | $3.25 | |
| Interior paint | per sf floor | $2.75 | |
| LVP flooring | per sf | $5.50 | |
| Tile flooring | per sf | $9 | |
| Refinish hardwood | per sf | $4.50 | |
| Interior door | each | $350 | |
| Trim / baseboard | per lf | $7 | |

## Kitchens & baths

| Item | Unit | Placeholder | Notes |
|---|---|---|---|
| Full kitchen, builder grade | each | $14,000 | |
| Full kitchen, mid grade | each | $24,000 | |
| Full bath gut + rebuild | each | $9,500 | |
| Half bath | each | $4,500 | |

## Other

| Item | Unit | Placeholder | Notes |
|---|---|---|---|
| Mold remediation | per sf | $18 | post-flood, very common |
| Debris removal / haul | per load | $650 | |
| Termite treatment | lump | $1,800 | |
| Permits | lump | $1,200 | varies by parish |

---

## Deal parameters

| Parameter | Placeholder | Notes |
|---|---|---|
| Contingency % | 15% | applied to subtotal |
| Target assignment fee | $12,500 | Module 13 range: $10k–15k |
| Holding cost / month | $850 | |
| Closing costs (buy side) | 2% of purchase | |

## MAO formula

**Placeholder:**

```
MAO = (ARV × 0.70) − repair_total − assignment_fee
```

**Operator must confirm:**
- Is 0.70 the right multiplier?
- Does it change by parish, price band, or property type?
- Are holding and closing costs inside the multiplier or subtracted separately?

---

## South Louisiana risk checklist

Applied by `underwrite` on every property. Not priced here — flagged for operator review.

- Flood zone designation and current elevation certificate status
- Pier vs slab, and evidence of differential settlement
- Wind/hail deductible exposure (often a separate, higher deductible)
- Post-storm deferred maintenance patterns (blue-tarp roofs, patched decking)
- Termite / Formosan termite damage — endemic, frequently hidden
- Knob-and-tube or cloth wiring in pre-1950 stock
- Asbestos siding / lead paint in pre-1978 stock
