#!/usr/bin/env python3
"""GoHighLevel CRM client - upsert contact, add note. API v2.

Loads secrets/ghl.env the same way buyer_outreach.py loads retell.env - fails
closed if not configured, never prints values.
"""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / "secrets" / "ghl.env"
BASE_URL = "https://services.leadconnectorhq.com"
API_VERSION = "2021-07-28"


def load_env():
    if not ENV_FILE.exists():
        print(f"FATAL: {ENV_FILE} not found.", file=sys.stderr)
        sys.exit(1)
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    for required in ("GHL_API_KEY", "GHL_LOCATION_ID"):
        if not env.get(required):
            print(f"FATAL: {required} not set in secrets/ghl.env.", file=sys.stderr)
            sys.exit(1)
    return env


def _request(env, method, path, body):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {env['GHL_API_KEY']}",
            "Version": API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Default urllib UA ("Python-urllib/3.x") is blocked outright by
            # GHL's Cloudflare front door (error 1010) - any normal UA clears it.
            "User-Agent": "freshslate-webhook-receiver/1.0",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"ok": True, "response": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:500]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def upsert_contact(env, phone: str, name: str = "", tags=None, source: str = "freshslate-buyer-outreach"):
    """Create or update a contact by phone number. Returns the _request() result dict."""
    first_name, _, last_name = (name or "").partition(" ")
    body = {
        "locationId": env["GHL_LOCATION_ID"],
        "phone": phone,
        "firstName": first_name or None,
        "lastName": last_name or None,
        "tags": tags or [],
        "source": source,
    }
    body = {k: v for k, v in body.items() if v not in (None, "")}
    return _request(env, "POST", "/contacts/upsert", body)


def add_note(env, contact_id: str, note_text: str):
    return _request(env, "POST", f"/contacts/{contact_id}/notes", {"body": note_text})


def add_tags(env, contact_id: str, tags):
    """Add tags WITHOUT replacing the existing set.

    /contacts/upsert treats `tags` as the complete set and overwrites what is
    already on the contact. Two events arrive per call (log_call_outcome
    during the call, then call_analyzed about a second later), so passing tags
    on the upsert meant the second event silently erased the outcome tag the
    first had just written - observed live on
    call_eddb1e2ec59ca9269f2ee80c034, where 'freshslate-reschedule' vanished
    within a second of being set. This endpoint appends instead.
    """
    if not tags:
        return {"ok": True, "response": {"skipped": "no tags"}}
    return _request(env, "POST", f"/contacts/{contact_id}/tags", {"tags": list(tags)})
