# Do-Not-Call Policy — Fresh Slate

**Status: 📝 DRAFT — NOT COUNSEL-REVIEWED.**

A written DNC policy is legally required of any entity making telemarketing
calls, and must be made available on request. This draft exists so the
requirement is visible and mostly satisfied before counsel review, not so it
can be relied on as-is.

**Take this document to the TCPA attorney alongside `call-script.md` and
`docs/planning/2026-08-10-operational-readiness-plan.md`.** It is a structured
starting point, not legal advice, and this repo's authors are not lawyers.

Technical enforcement of everything below lives in `src/dnc.py`. Where this
document and that code disagree, the code is what actually runs — fix both.

---

## 1. Scope

This policy covers every outbound voice call placed by or on behalf of Fresh
Slate, including AI-assisted calls placed through Retell by
`src/buyer_outreach.py`.

It does **not** cover: inbound calls, direct mail, or email (CAN-SPAM governs
email — see the `compliance-gate` skill).

## 2. Lists maintained

| List | Source | Where | Refresh |
|---|---|---|---|
| Internal DNC | Our own suppression requests | `deals/_config/dnc/internal-dnc.jsonl` | Continuous, append-only |
| National DNC | FTC Registry (requires SAN) | `deals/_config/dnc/national/` | **Every 31 days** — see §6 |
| Louisiana DNC | LA Public Service Commission | `deals/_config/dnc/louisiana/` | Per LPSC terms |

## 3. Scrub before dial — mandatory

No number is dialed without passing `dnc.assert_callable()`. That function
**fails closed**: if a registry file is missing, the number is refused rather
than assumed clear. "Not checked" is never treated as "not listed."

Blocks currently enforced in code:

- `INTERNAL_DNC` — number is on our permanent suppression list
- `NATIONAL_DNC` / `STATE_DNC_LA` — number appears on a downloaded registry
- `REGISTRY_NOT_LOADED` — a registry is missing, so no dial is permitted
- `CALLING_HOURS` — outside 08:00–21:00 in the recipient's local time
- `TIMEZONE_UNKNOWN` — recipient's timezone can't be derived from the area
  code, so calling hours can't be verified
- `INVALID_NUMBER` — not a valid 10-digit NANP number

## 4. Honoring a suppression request

A request to stop calling is honored **immediately, on the call, without
argument or a retention attempt.** The Marigny script does this verbatim
("Got it — I'll take you off the list. Sorry to bother you.") and ends the call.

The request is then recorded automatically: `src/webhook_server.py` writes it
to the internal DNC list when Retell reports `dnc_requested` /
`do_not_call_requested`. This happens **before** the CRM write, so a CRM
outage cannot cause a suppression request to be lost.

**Suppression is permanent and the list is append-only.** Entries are never
removed. A removal would destroy the record proving the request was honored.

A request received by any other channel (email, mail, in person, relayed by a
colleague) must be added manually and promptly:

```bash
python3 src/dnc.py --add "+12255550100" --reason "emailed request 2026-08-12" --source email
```

## 4a. Self-test calls — a narrow, deliberate carve-out

Calling a number the operator owns, with the operator's own consent, in order
to test the system is **not telemarketing**, and the DNC registries do not
govern it. `src/dnc.py` supports this narrowly:

- The number must first be registered via `--add-self-test` with a recorded
  ownership attestation. `--self-test` on an unregistered number is refused
  (`SELF_TEST_NOT_REGISTERED`), so the flag cannot become a general bypass.
- **The internal DNC list still blocks absolutely**, even in self-test mode.
  Verified in code: a self-test number added to the internal list is refused.
- Calling hours and number validity still apply.
- Every self-test call is logged with a `SELF_TEST_MODE` warning naming the
  attestation and its date.

Self-test also proceeds when `call-script.md` is unapproved. That is
deliberate and not a weakening: the script gate exists to keep an unapproved
script away from *third parties*, and a self-test reaches none. Requiring
script approval before the operator can hear the script would be circular.

**This carve-out covers testing only. It is not a basis for calling anyone
else, ever, under any framing.**

## 5. Records

Every call attempt — placed, dry-run, or refused — is logged to
`deals/_inbox/YYYY-MM-DD-buyer-outreach.jsonl`, including the reason for any
DNC refusal. Every internal DNC entry records the number, reason, source, and
timestamp.

**Retention: keep indefinitely.** These records are the evidence that the
policy was followed.

## 6. Open items — must be resolved before any live call

- [ ] **Register with the FTC** at `telemarketing.donotcall.gov`, obtain a
      Subscription Account Number, download the relevant area-code files into
      `deals/_config/dnc/national/`.
- [ ] **Register with the Louisiana Public Service Commission** and download
      the state list into `deals/_config/dnc/louisiana/`.
- [ ] **Confirm the registry refresh interval with counsel.** This draft says
      31 days based on the commonly-cited federal requirement. *Verify it* —
      the interval has changed before, and a stale list is treated as no list.
- [ ] **Confirm Louisiana's calling-hours rule.** `src/dnc.py` enforces the
      federal 08:00–21:00 window. If Louisiana's window is narrower, the code
      constant must be tightened to match.
- [ ] **Get counsel's read on B2B applicability.** These calls target licensed
      agents and investment entities. DNC rules apply differently to business
      lines than to consumer lines, but a skip-traced mobile number attached
      to an LLC member is not obviously a business line. `src/dnc.py`
      deliberately scrubs every number identically pending that answer.
- [ ] **Name a responsible person** for maintaining this policy and the lists.
- [ ] **Counsel review and sign-off**, recorded below.

## Approval record

_(none yet — this document has not been reviewed by an attorney)_
