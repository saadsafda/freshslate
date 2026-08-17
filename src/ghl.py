#!/usr/bin/env python3
"""
GoHighLevel client (LeadConnector API v2).

Deal system of record. Call outcomes, contact state, and opt-outs land here.

Two things worth knowing before editing this file:

1. A normal User-Agent is mandatory. GHL sits behind Cloudflare, which returns
   403 "Error 1010" to Python's default urllib agent. This is not an auth
   failure and the error message does not say so -- it cost an hour to find.

2. Opt-out is enforced here, in code, not in the voice prompt. `mark_opted_out`
   sets GHL's own `dnd` flag, which suppresses contact channel-wide, and the
   dialer refuses any contact whose `dnd` is true. A prompt instruction is a
   request; a gate is a guarantee. TCPA exposure is per-call.

Env: GHL_API_KEY (Private Integration token), GHL_LOCATION_ID
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = "https://services.leadconnectorhq.com"
API_VERSION = "2021-07-28"

# Cloudflare rejects the default urllib UA with a 403 that looks like auth failure.
USER_AGENT = "FreshSlate/1.0 (+acquisition-support)"

OPT_OUT_TAG = "freshslate-do-not-call"
DNC_REQUEST_TAG = "freshslate-optout-requested"


class GHLError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


class GHL:
    def __init__(self, api_key=None, location_id=None):
        self.api_key = api_key or os.environ.get("GHL_API_KEY")
        self.location_id = location_id or os.environ.get("GHL_LOCATION_ID")

    @property
    def available(self):
        return bool(self.api_key and self.location_id)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Version": API_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

    def _request(self, method, path, body=None, params=None, timeout=30):
        if not self.available:
            raise GHLError("GHL credentials unavailable (GHL_API_KEY, GHL_LOCATION_ID)")

        url = f"{BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read().decode()
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as e:
                detail = e.read().decode()[:400]
                if e.code == 429:
                    time.sleep(2 ** attempt)
                    continue
                if e.code in (401, 403):
                    hint = ""
                    if "1010" in detail or "browser's signature" in detail:
                        hint = " (Cloudflare UA block, not an auth failure)"
                    raise GHLError(f"GHL auth failed {e.code}{hint}: {detail}")
                if e.code == 404:
                    return None
                raise GHLError(f"GHL {method} {path} -> {e.code}: {detail}")
            except urllib.error.URLError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        return None

    # ---------- read ----------

    def location(self):
        r = self._request("GET", f"/locations/{self.location_id}")
        return (r or {}).get("location")

    def custom_fields(self):
        r = self._request("GET", f"/locations/{self.location_id}/customFields")
        return (r or {}).get("customFields", [])

    def field_map(self):
        """{fieldKey: id} -- needed because writes address fields by id."""
        return {f["fieldKey"]: f["id"] for f in self.custom_fields() if f.get("fieldKey")}

    def pipelines(self):
        r = self._request("GET", "/opportunities/pipelines", params={"locationId": self.location_id})
        return (r or {}).get("pipelines", [])

    def find_contact_by_phone(self, phone):
        r = self._request(
            "GET", "/contacts/",
            params={"locationId": self.location_id, "query": phone, "limit": 20},
        )
        digits = "".join(c for c in phone if c.isdigit())[-10:]
        for c in (r or {}).get("contacts", []):
            cand = "".join(ch for ch in (c.get("phone") or "") if ch.isdigit())[-10:]
            if cand and cand == digits:
                return c
        return None

    def get_contact(self, contact_id):
        r = self._request("GET", f"/contacts/{contact_id}")
        return (r or {}).get("contact")

    # ---------- write ----------

    def upsert_contact(self, phone=None, email=None, first_name=None, last_name=None,
                       tags=None, custom=None, source="Fresh Slate"):
        """
        Create or update by phone. `custom` is {fieldKey: value}; unknown keys are
        dropped with a note rather than silently swallowed, because a typo'd field
        key is otherwise invisible -- the write succeeds and the data vanishes.
        """
        body = {"locationId": self.location_id, "source": source}
        if phone:
            body["phone"] = phone
        if email:
            body["email"] = email
        if first_name:
            body["firstName"] = first_name
        if last_name:
            body["lastName"] = last_name
        if tags:
            body["tags"] = tags

        dropped = []
        if custom:
            fmap = self.field_map()
            cf = []
            for key, val in custom.items():
                if val is None or val == "":
                    continue
                fid = fmap.get(key) or fmap.get(f"contact.{key}")
                if fid:
                    cf.append({"id": fid, "value": str(val)})
                else:
                    dropped.append(key)
            if cf:
                body["customFields"] = cf

        r = self._request("POST", "/contacts/upsert", body=body)
        contact = (r or {}).get("contact", r)
        if dropped and isinstance(contact, dict):
            contact["_dropped_fields"] = dropped
        return contact

    def add_tags(self, contact_id, tags):
        return self._request("POST", f"/contacts/{contact_id}/tags", body={"tags": tags})

    def add_note(self, contact_id, body_text):
        return self._request("POST", f"/contacts/{contact_id}/notes", body={"body": body_text})

    def mark_opted_out(self, contact_id, reason="requested on call"):
        """
        Hard opt-out. Sets GHL's dnd flag (suppresses all channels), tags, and
        writes an audit note. Called on every opt-out signal from a call.
        """
        self._request("PUT", f"/contacts/{contact_id}", body={"dnd": True})
        self.add_tags(contact_id, [OPT_OUT_TAG, DNC_REQUEST_TAG])
        self.add_note(contact_id, f"[{_now()}] DO NOT CALL recorded: {reason}. "
                                  f"dnd=true set via API. Suppressed from all Fresh Slate dialing.")
        return True

    def is_callable(self, contact):
        """
        Gate consulted before every dial. Returns (bool, reason).

        Fails closed: anything unexpected means do not call.
        """
        if not contact:
            return False, "contact not found"
        if contact.get("dnd") is True:
            return False, "dnd flag set on contact"
        tags = [t.lower() for t in (contact.get("tags") or [])]
        if OPT_OUT_TAG in tags or DNC_REQUEST_TAG in tags:
            return False, "opt-out tag present"
        for ch in (contact.get("dndSettings") or {}).values():
            if isinstance(ch, dict) and ch.get("status") == "active":
                return False, "channel-level dnd active"
        if not contact.get("phone"):
            return False, "no phone number"
        return True, "ok"

    def create_opportunity(self, contact_id, pipeline_id, stage_id, name, value=None):
        body = {
            "locationId": self.location_id,
            "contactId": contact_id,
            "pipelineId": pipeline_id,
            "pipelineStageId": stage_id,
            "name": name,
            "status": "open",
        }
        if value is not None:
            body["monetaryValue"] = value
        return self._request("POST", "/opportunities/", body=body)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from secrets_loader import require

    require("ghl")
    g = GHL()
    loc = g.location()
    print(f"Location: {loc.get('name')} — {loc.get('city')}, {loc.get('state')}")
    print(f"Timezone: {loc.get('timezone')}\n")

    flds = g.custom_fields()
    print(f"Custom fields ({len(flds)}):")
    for f in flds:
        print(f"  {f.get('fieldKey'):48} {f.get('dataType')}")

    print("\nPipelines:")
    for p in g.pipelines():
        print(f"  {p.get('name')} ({p.get('id')})")
        for s in p.get("stages", []):
            print(f"      {s.get('position')}. {s.get('name')}")
