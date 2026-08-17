# Your Repair Numbers — Intake Form

**To:** Dr. Marigny
**From:** Shayan
**Time to fill in:** about 15 minutes

---

## Why this is the one thing I keep asking for

The repair estimator and offer calculator are **built and working**. I ran one this morning
on a sample 7-line rehab and it produced a clean scope, three offer scenarios, and correct
math on every step.

But every estimate it prints right now carries this stamp:

> 🧪 **TESTING MODE — SYNTHETIC COSTS.** The unit prices behind this estimate are placeholder
> figures generated during development. **No operator or contractor has ever reviewed them.**

That stamp is there because I invented the numbers. I had to, to build the thing — but I am
not going to let invented figures quietly become the basis of a real offer. **The moment you
send yours, the stamp disappears and the tool produces real offers.**

Here is what that stamp is protecting you from. On a typical rehab, if the unit costs are off
by 20%, the offer moves by about **$11,000**. That is roughly your entire assignment fee, on
one deal.

---

## Part 1 — The seven that matter (5 minutes)

I ranked every line item by how much it actually moves the final number. On a normal rehab,
**these seven account for the entire estimate.** The other 33 are rounding by comparison.

If you only do one thing, do this table.

| # | Item | Unit | My placeholder | **Your number** |
|---|---|---|---:|---|
| 1 | Full kitchen, builder grade | each | $14,000 | $ |
| 2 | Full bath, gut + rebuild | each | $9,500 | $ |
| 3 | HVAC, 3-ton split system | each | $8,500 | $ |
| 4 | Architectural shingle, tear-off + replace | per square (100 sf) | $450 | $ |
| 5 | LVP flooring | per sf | $5.50 | $ |
| 6 | Pier leveling / shimming | per pier | $350 | $ |
| 7 | Sheetrock, hang + finish | per sf | $3.25 | $ |

> **If a number is close enough, just write "ok."** I only need the ones I got wrong.

---

## Part 2 — Your deal formula (3 minutes)

These four change every offer the system makes. They matter as much as the costs.

| Setting | My placeholder | **Your number** | Question |
|---|---:|---|---|
| Percentage rule | **70%** | ___% | Is 70% of ARV right? Does it change by parish or price band? |
| Target assignment fee | **$12,500** | $ | Module 13 says $10k–15k. What do you actually target? |
| Contingency | **15%** | ___% | How much do you add for surprises? |
| Holding cost / month | **$850** | $ | Taxes, insurance, utilities while holding |

**On the percentage rule** — if it changes by price band or parish, tell me how and I'll build
that in. Right now it's one flat number, which I suspect is wrong for how you actually work.

---

## Part 3 — The rest (optional, 10 minutes)

Only if you have them handy. Anything left blank keeps my placeholder **and keeps the warning
stamp on lines that use it**, which is the correct behavior — you'll see exactly which lines
are still unverified.

<details>
<summary><b>Roofing</b></summary>

| Item | Unit | Placeholder | Yours |
|---|---|---:|---|
| 3-tab shingle | per square | $350 | $ |
| Metal roof | per square | $900 | $ |
| Decking replacement | per sheet | $95 | $ |
| Flashing / boot replacement | each | $150 | $ |
</details>

<details>
<summary><b>Exterior</b></summary>

| Item | Unit | Placeholder | Yours |
|---|---|---:|---|
| Hardie / fiber cement siding | per sf | $9 | $ |
| Vinyl siding | per sf | $5 | $ |
| Wood siding repair | per sf | $12 | $ |
| Exterior paint | per sf wall | $2.50 | $ |
| Soffit / fascia | per lf | $18 | $ |
| Window, vinyl replacement | each | $550 | $ |
| Exterior door | each | $850 | $ |
</details>

<details>
<summary><b>Foundation / structural</b></summary>

| Item | Unit | Placeholder | Yours |
|---|---|---:|---|
| Pier replacement | per pier | $650 | $ |
| Sill plate repair | per lf | $85 | $ |
| Slab crack repair | per lf | $95 | $ |
| Full re-level, raised pier home | lump | $12,000 | $ |
</details>

<details>
<summary><b>Systems</b></summary>

| Item | Unit | Placeholder | Yours |
|---|---|---:|---|
| Full rewire | per sf | $7 | $ |
| Panel replacement, 200A | each | $2,800 | $ |
| Ductwork replacement | per sf | $4 | $ |
| Water heater, 40gal | each | $1,600 | $ |
| Full repipe (PEX) | per fixture | $850 | $ |
| Sewer line replacement | per lf | $150 | $ |
</details>

<details>
<summary><b>Interior</b></summary>

| Item | Unit | Placeholder | Yours |
|---|---|---:|---|
| Interior paint | per sf floor | $2.75 | $ |
| Tile flooring | per sf | $9 | $ |
| Refinish hardwood | per sf | $4.50 | $ |
| Interior door | each | $350 | $ |
| Trim / baseboard | per lf | $7 | $ |
| Full kitchen, mid grade | each | $24,000 | $ |
| Half bath | each | $4,500 | $ |
</details>

<details>
<summary><b>Louisiana-specific</b></summary>

| Item | Unit | Placeholder | Yours |
|---|---|---:|---|
| Mold remediation | per sf | $18 | $ |
| Termite treatment | lump | $1,800 | $ |
| Debris removal / haul | per load | $650 | $ |
| Permits | lump | $1,200 | $ |
</details>

---

## Anything missing?

The estimator refuses to guess. If a scope line has no matching cost entry, it reports:

> **⚠️ Could not price** — no matching entry in cost table. *Not included in the total.*

It surfaced exactly that on my test run for "Custom ironwork balcony restoration" — real for
New Orleans work, absent from my table. **If there are items you hit regularly that aren't
listed above, add them.** A missing line is a silent hole in every estimate.

---

## How to send it

**Whatever is easiest.** Genuinely:

- Fill in this file and send it back
- A spreadsheet
- A photo of a handwritten list
- An old estimate or contractor invoice — I'll pull the numbers out myself
- Type them in an email
- Read them to me on a call and I'll transcribe

**No format work needed on your end.** I'd rather have messy real numbers today than clean
ones next month.

---

## What happens when it lands

1. I load your numbers into `deals/_config/costs-la.md`
2. Status line changes to `APPROVED BY [your name] ON [date]`
3. The warning stamp **drops automatically** — that's a code check, not a manual edit
4. Every estimate from then on is a real offer you can act on

I'll send you a before/after on the same property so you can see the difference your numbers
make.

---

## One question I need answered either way

**Does your percentage rule change by parish or by price band?**

Right now the system uses one flat 70% for everything. If you actually run 70% in Orleans and
something different in Jefferson, or tighter above $300k, tell me — that's a structural change
to the calculator, not just a number swap, and I'd rather build it right the first time.
