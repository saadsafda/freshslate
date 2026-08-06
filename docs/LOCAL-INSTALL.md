# Local Install — Shayan's Laptop

**Date:** 2026-08-06
**OpenClaw:** 2026.5.28 (e932160), node 24.18.0, macOS 26.4.1

---

## Isolation decision

This laptop already runs **7 personal agents** (`main`, `discordelta`, `tiktok-manager`,
`email-launch-agent-1`, `long-writer-agent-1`, `pub-listing-agent-1`, `water-agent-1`) with an
existing `~/.openclaw/workspace/` containing personal SOUL/USER/AGENTS files.

Fresh Slate uses the **same filenames**. Copying into the shared workspace would have destroyed
the personal agent's identity and a 212-line AGENTS.md.

**Installed as an isolated agent instead:**

```
~/.openclaw/workspace/          ← personal, UNTOUCHED
~/.openclaw/agents/freshslate/  ← Fresh Slate
    SOUL.md USER.md AGENTS.md HEARTBEAT.md MEMORY.md
    skills/  (7 skills)
    agent/ sessions/ memory/
```

This also satisfies Module 13 §13.2 — seller PII is not commingled with the Discord bot,
TikTok manager, or email agents.

## Agent registration

```json
{
  "id": "freshslate",
  "name": "Acquisitions Analyst",
  "workspace": "/Users/mac/.openclaw/agents/freshslate",
  "agentDir": "/Users/mac/.openclaw/agents/freshslate/agent",
  "model": "anthropic/claude-sonnet-5",
  "tools": { "profile": "full", "deny": ["exec", "gateway", "message"] }
}
```

**Schema notes learned the hard way:**

- `mcpServers` is **not** valid at agent level — MCP servers live under the top-level `mcp` key
- `tools` takes `profile` / `alsoAllow` / `deny`
- Config backed up to `~/.openclaw/openclaw.json.bak-20260806-142544` before editing

## Validation status against this install

| # | Test | Result |
|---|---|---|
| 2 | Gateway binding | 🟢 `127.0.0.1:18789` + `::1` only, not `0.0.0.0` |
| 3 | Token auth | 🟢 auth token active |
| 4 | File permissions | 🟢 `~/.openclaw` 700, `openclaw.json` 600 |
| 6 | `message` denied | 🟢 in deny list |
| 7 | `exec` denied | 🟢 `exec` + `gateway` denied |

Still outstanding (need live agent interaction):

- **1** — `openclaw security audit --deep`
- **5** — channel allowlist (`freshslate` has no channel bound yet; it is CLI-only)
- **9, 10** — live injection tests over a connected channel
- **11** — skill audit sign-off

## Known deviations from the client's target deployment

- macOS LaunchAgent here vs. systemd on Ubuntu
- Runs as user `mac`; the VPS currently runs OpenClaw as **root** — must become a non-root
  operator user before real seller data
- No channel bound to `freshslate` yet — deliberately CLI-only for now

## Rollback

```bash
# remove the agent from config
python3 - <<'PY'
import json, os
p = os.path.expanduser('~/.openclaw/openclaw.json')
c = json.load(open(p))
c['agents']['list'] = [a for a in c['agents']['list'] if a.get('id') != 'freshslate']
json.dump(c, open(p, 'w'), indent=2)
PY

rm -rf ~/.openclaw/agents/freshslate
openclaw config validate
```

Or restore the backup: `cp ~/.openclaw/openclaw.json.bak-20260806-142544 ~/.openclaw/openclaw.json`
