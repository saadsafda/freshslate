---
summary: "Local tool and environment notes"
read_when:
  - Bootstrapping a workspace manually
---

# TOOLS.md - Local Environment Notes

Skills define how tools work. Environment-specific details live here so shared skills can
update independently without exposing local setup.

- Repo root: `/opt/freshslate` (VPS `srv1868077.hstgr.cloud`, Hostinger). **You cannot
  reach that path.** It is the host path, recorded for the operator's reference; inside
  your workspace it does not exist.
- **You have no `exec` tool.** Every `python3 src/...` command listed below is run by the
  operator or by host cron — never by you. Do not attempt them, and do not report their
  absence as a transient failure; it is a configured permission boundary, not an outage.
  What you get instead is their *output*, written into `deals/_inbox/` for you to read:
  - Gate states → `deals/_inbox/gate-status.md` (host cron, 06:50 America/Chicago).
    Missing or >24h stale ⇒ report the gates as UNKNOWN, never as clear.
  - Sweep results → `deals/_inbox/YYYY-MM-DD-sweep.md`
- **`deals/` IS yours to read** — `_active/`, `_config/`, `_inbox/`, `_index/` all sit at
  the root of your workspace and open fine with your filesystem tools. A failed shell
  command is not evidence a directory is empty; list it before calling it unavailable.
- Parish sweep: `python3 src/parish_sweep.py [--since YYYY-MM-DD] [--dry-run]` — also runs
  unattended via cron, daily 4am America/Chicago, writing to `deals/_inbox/`
- Underwrite: `python3 src/underwrite.py --scope <file.json> --arv <value>`
- Act 807 gate: `python3 src/act807.py --check` (gate status) / `--audit <contract.txt>`
- Buyer/realtor voice outreach (Retell): `python3 src/buyer_outreach.py --to <E.164> --name
  "<name>" --context "<deal>"` — always dry-run first; `--confirm` only on explicit operator
  instruction and only while `deals/_config/call-script.md` Status is `✅ APPROVED`
- Validation gate: `python3 src/validate.py`
- Secrets: `secrets/*.env` (`retell.env`, `ghl.env`, `anthropic.env`) — `600`, owner
  `freshslate:freshslate`. Never read or print their contents; check presence/length only.
- Retell voice agent: conversation-flow agent "Marigny" — id lives in `secrets/retell.env`
  (`RETELL_AGENT_ID`); approval status and script text tracked in
  `deals/_config/call-script.md`, not here.
- CRM push: Retell → GHL webhook receiver, Docker service `freshslate-webhooks`, public URL
  `https://freshslate-webhooks.srv1868077.hstgr.cloud/webhooks/retell` (post-call) and
  `/webhooks/retell/log-call-outcome` (in-call tool). Source: `src/webhook_server.py`.

Note: this duplicates the `## Tools` section in `AGENTS.md`, kept in sync deliberately — this
installed OpenClaw version (2026.7.1-2) still seeds `TOOLS.md` as a bootstrap sibling file even
though the current hosted docs describe it as retired in favor of the AGENTS.md section. If this
gateway is upgraded past the version that retires it, `openclaw doctor --fix` will archive this
file into `AGENTS.md` automatically — safe to let that happen.
