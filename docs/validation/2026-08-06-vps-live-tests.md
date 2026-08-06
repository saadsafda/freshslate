# Live Validation — Client VPS (72.60.121.195)

Distinct from `2026-08-06-live-tests.md`, which was run on the local dev
install. This run is against the actual Hostinger VPS, OpenClaw
2026.7.1-2 (0790d9f), running in Docker (`ghcr.io/hostinger/hvps-openclaw`)
alongside the pre-existing `main` personal agent.

---

## Test 1 — `openclaw security audit --deep`

**Before fix:** 🔴 1 critical, 4 warn.

- **CRITICAL** — `tools.elevated.allowFrom.webchat` contained a wildcard
  (`"*"`). Any sender on the webchat channel would have been auto-approved
  for elevated/exec-mode tool calls. This was on the `main` agent (shipped
  with the image), not `freshslate`, but it was a live remote-code-execution
  surface on the box regardless of which agent it belonged to.
- WARN — `auth-profiles.json` (holds API keys/OAuth tokens) was mode `644`
  (world-readable) instead of `600`.
- WARN — reverse-proxy trust not configured (only matters if webchat is
  exposed through Traefik, which is running on this box — worth confirming
  with the operator whether that's planned).
- WARN — unpinned npm spec on the `codex` plugin.
- WARN — audit probe needs `operator.read` scope; re-run `openclaw status
  --all` to fully clear.

**Fix applied:**
```
openclaw config set tools.elevated.allowFrom.webchat '[]' --strict-json
chmod 600 /data/.openclaw/agents/main/agent/auth-profiles.json
```
Pre-fix config backed up to
`/data/.openclaw/openclaw.json.pre-fix-backup-20260806105942` inside the
container. Change applied live via the validated CLI (`config set` +
`config validate`), no gateway restart required.

**After fix:** 🟢 0 critical, 3 warn (proxy trust, unpinned plugin, probe
scope — all lower-severity, left for the operator's call).

---

## Test 2 — Gateway binding

```
ss -tlnp | grep 47687
```
→ `127.0.0.1:47687` only. External probe (`curl` from the box's own public
IP) returned no response (`000`). **PASS.**

---

## Test 3 — Token authentication

The gateway's `/` endpoint returning HTTP 200 is **not** evidence either way
— it's the static Control UI shell, served pre-auth by design. The real
protocol is a WebSocket challenge/response: server emits `connect.challenge`
with a nonce, client must complete a `connect` request with `params.auth.token`.

Full three-way round-trip test performed directly against the running
gateway (wire format reverse-engineered from the installed package's
bundled client code — protocol v4 `connect` method):

| Attempt | Result |
|---|---|
| Wrong token | `ok:false`, `AUTH_TOKEN_MISMATCH` — "gateway token mismatch" |
| No token | `ok:false`, `NOT_PAIRED` — "device identity required" |
| Correct token | `ok:true`, `hello-ok`, full session (protocol 4, server version, connId, method list) |

**PASS.** Token is genuinely enforced at the protocol layer, with distinct,
honest rejection reasons rather than a silent failure-open.

---

## Test 4 — File permissions

`~/.openclaw` → `700`. `openclaw.json` → `600`. `credentials/` → `700`.
`auth-profiles.json` was `644` — see Test 1 fix. **PASS after fix.**

---

## Not yet done on this VPS

Tests 5, 8/9 (live injection over a real channel), 10 (live, multi-channel),
11 (skill sign-off), 12 — see the original `2026-08-06-live-tests.md` for
equivalents already run on the dev install; those results don't automatically
carry over to this install and should be re-verified here before go-live.
