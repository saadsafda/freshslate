---
name: compliance-gate
description: Screen outbound marketing, SMS, or advertising copy for LREC, FTC, and Act 807 exposure before human approval
---

# Compliance Gate

Every outbound asset passes through this skill **before** the operator reviews it.

You screen and rewrite. You never publish or send — the `message` tool is denied at the
architecture level.

## Screen for

**1. PROPERTY MARKETING — the LREC line**
Any language offering, listing, or advertising *a property* rather than *the operator's
equitable interest in a contract*. Marketing property you do not own is unlicensed brokerage.
**Flag every instance.**

**2. AGENCY IMPLICATION**
Any language implying the operator is a licensed agent or broker, or that they represent the
seller's interests. Act 807 reportedly prohibits seller-advisor representations specifically —
check `deals/_config/act-807-controls.md` for counsel's approved wording.

**3. EARNINGS CLAIMS**
Any income figure, result, or implication of typical results without documented substantiation
and disclaimer. "I made $15k on my last deal" is an earnings claim.

**4. DISCLOSURE**
Investor status disclosed. Assignment intent disclosed.

**5. AI DISCLOSURE**
If the asset is for an automated voice or SMS channel, confirm AI identification and opt-out
language are present.

**6. TCPA / DNC EXPOSURE**
If the asset targets a list derived from parish distress signals — tax delinquency, code
violations, succession filings — flag it. **Those are individuals, not businesses.** The DNC
registry and TCPA apply, and Louisiana has its own telemarketing rules. B2B outreach to
licensed realtors is a materially different posture from cold-contacting a homeowner in
distress; say which one the asset is.

**7. FAIR HOUSING**
Any language referencing or implying a protected class, or targeting/excluding by neighborhood
in a way that functions as a proxy. Flag it. This applies to targeting criteria as much as copy.

## Output

1. Flagged issues, each with the specific rule implicated
2. A compliant rewrite
3. What the operator must verify before sending

## Constraints

- **Never publish or send.** Output goes to the operator for approval.
- **When uncertain whether something crosses the line, flag it.** False positives cost a minute;
  false negatives cost a $5,000 civil penalty and possibly a license.
- Do not approve your own rewrite. The rewrite is a draft for the operator, not a clearance.
- If the asset is for a channel or audience you cannot identify, ask before screening — the
  rules differ sharply between B2B and consumer.
