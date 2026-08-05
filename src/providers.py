#!/usr/bin/env python3
"""
Property-data provider layer.

Enriches parish sweep records with owner, valuation, and equity data from licensed
APIs. Parish open data tells us a property is DISTRESSED; these providers tell us
WHO owns it and WHAT it's worth.

Design rules:
  1. Every provider is optional. Missing API key => that provider is skipped and its
     fields stay null. The system degrades, it does not break.
  2. Nothing is ever inferred. A field is either sourced or null, with provenance.
  3. Every enriched value carries `_source` and `_retrieved_at` so the operator can
     answer "where did this number come from?" -- Module 13 citation discipline.
  4. Request budgets are enforced in code. Free tiers are small (RentCast: 50/mo)
     and a runaway loop is a real bill.

No provider here scrapes. All are licensed APIs used per their documented terms.
Zillow/Redfin are deliberately absent -- their terms prohibit automated access.

Env vars (all optional):
    RENTCAST_API_KEY
    ATTOM_API_KEY
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Conservative default: RentCast free tier is 50 req/month. Overrun costs money,
# so the ceiling lives in code rather than in a comment someone will miss.
DEFAULT_BUDGETS = {"rentcast": 45, "attom": 0}

BUDGET_STATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "deals", "_index", "api-budget.json",
)


class BudgetExceeded(Exception):
    """Raised when a provider's monthly request budget is spent."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load_budget():
    if not os.path.exists(BUDGET_STATE):
        return {}
    try:
        with open(BUDGET_STATE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _save_budget(state):
    os.makedirs(os.path.dirname(BUDGET_STATE), exist_ok=True)
    with open(BUDGET_STATE, "w") as f:
        json.dump(state, f, indent=2)


def _spend(provider, budget):
    """Record one request against this month's budget. Raises if exhausted."""
    month = datetime.now().strftime("%Y-%m")
    state = _load_budget()
    used = state.get(provider, {}).get(month, 0)
    if used >= budget:
        raise BudgetExceeded(
            f"{provider}: {used}/{budget} requests used for {month}. "
            f"Raise the budget in config or wait for reset."
        )
    state.setdefault(provider, {})[month] = used + 1
    _save_budget(state)
    return used + 1


def budget_report():
    """Current month's usage per provider, for the operator briefing."""
    month = datetime.now().strftime("%Y-%m")
    state = _load_budget()
    return {p: {"used": v.get(month, 0), "budget": DEFAULT_BUDGETS.get(p, 0)}
            for p, v in state.items()}


class Provider:
    """Base class. Subclasses implement lookup()."""

    name = "base"
    env_key = None

    def __init__(self, budget=None):
        self.api_key = os.environ.get(self.env_key) if self.env_key else None
        self.budget = budget if budget is not None else DEFAULT_BUDGETS.get(self.name, 0)

    @property
    def available(self):
        return bool(self.api_key)

    def _get(self, url, headers, timeout=30):
        req = urllib.request.Request(url, headers=headers)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(2 ** attempt)
                    continue
                if e.code in (401, 403):
                    raise RuntimeError(f"{self.name}: auth failed ({e.code}). Check {self.env_key}.")
                if e.code == 404:
                    return None
                raise
            except urllib.error.URLError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        return None


class RentCast(Provider):
    """
    RentCast property records. https://developers.rentcast.io

    Free tier: 50 requests/month. Good fit for demos and low-volume enrichment.
    Paid: Foundation $74/mo (1k req), Growth $199/mo (5k), Scale $449/mo (25k).

    Supplies the two fields parish open data cannot:
      - owner name + mailing address + ownerOccupied  (absentee-owner signal)
      - tax assessment values                          (equity input)
    """

    name = "rentcast"
    env_key = "RENTCAST_API_KEY"
    BASE = "https://api.rentcast.io/v1"

    def lookup(self, address):
        if not self.available:
            return None
        _spend(self.name, self.budget)

        url = f"{self.BASE}/properties?" + urllib.parse.urlencode({"address": address, "limit": 1})
        data = self._get(url, {"X-Api-Key": self.api_key, "Accept": "application/json"})
        if not data:
            return None
        rec = data[0] if isinstance(data, list) else data
        if not rec:
            return None

        owner = rec.get("owner") or {}
        names = owner.get("names") or []

        # Latest tax assessment, if present.
        assessed = assessed_year = None
        ta = rec.get("taxAssessments") or {}
        if isinstance(ta, dict) and ta:
            latest = max(ta.keys())
            assessed = (ta[latest] or {}).get("value")
            assessed_year = latest

        return {
            "owner_of_record": ", ".join(names) if names else None,
            "owner_type": owner.get("type"),
            "owner_mailing_address": owner.get("mailingAddress", {}).get("formattedAddress")
                                     if isinstance(owner.get("mailingAddress"), dict) else None,
            "owner_occupied": rec.get("ownerOccupied"),
            "property_type": rec.get("propertyType"),
            "bedrooms": rec.get("bedrooms"),
            "bathrooms": rec.get("bathrooms"),
            "square_footage": rec.get("squareFootage"),
            "year_built": rec.get("yearBuilt"),
            "lot_size": rec.get("lotSize"),
            "last_sale_date": rec.get("lastSaleDate"),
            "last_sale_price": rec.get("lastSalePrice"),
            "assessed_value": assessed,
            "assessed_year": assessed_year,
            "county": rec.get("county"),
            "_source": "rentcast:/v1/properties",
            "_retrieved_at": _now(),
        }


class ATTOM(Provider):
    """
    ATTOM property data. https://api.developer.attomdata.com

    No free tier -- requires a commercial agreement. Included so the integration
    exists the moment a key is provisioned; until then it self-skips.

    Stronger than RentCast for: mortgage/lien detail, pre-foreclosure, AVM.
    """

    name = "attom"
    env_key = "ATTOM_API_KEY"
    BASE = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

    def lookup(self, address):
        if not self.available:
            return None
        _spend(self.name, self.budget)

        url = f"{self.BASE}/property/detail?" + urllib.parse.urlencode({"address": address})
        data = self._get(url, {"apikey": self.api_key, "Accept": "application/json"})
        if not data or not data.get("property"):
            return None
        p = data["property"][0]

        return {
            "owner_of_record": (p.get("owner") or {}).get("owner1", {}).get("fullname"),
            "assessed_value": (p.get("assessment") or {}).get("assessed", {}).get("assdttlvalue"),
            "market_value": (p.get("assessment") or {}).get("market", {}).get("mktttlvalue"),
            "last_sale_price": (p.get("sale") or {}).get("amount", {}).get("saleamt"),
            "last_sale_date": (p.get("sale") or {}).get("salesearchdate"),
            "year_built": (p.get("summary") or {}).get("yearbuilt"),
            "square_footage": (p.get("building") or {}).get("size", {}).get("livingsize"),
            "_source": "attom:/property/detail",
            "_retrieved_at": _now(),
        }


PROVIDERS = {"rentcast": RentCast, "attom": ATTOM}


def enrich(record, providers=None, address_field="situs_address"):
    """
    Enrich one sweep record in place. Returns the record.

    Never overwrites a value the parish source already supplied -- government
    records outrank a commercial aggregator for owner of record.
    """
    address = record.get(address_field)
    if not address:
        record["enrichment_status"] = "skipped: no address"
        return record

    parish = record.get("parish", "")
    state_hint = "LA"
    query = address if "," in address else f"{address}, {parish.replace(' Parish','')}, {state_hint}"

    chain = providers or ["rentcast", "attom"]
    attempted = []

    for pname in chain:
        prov = PROVIDERS[pname]()
        if not prov.available:
            attempted.append(f"{pname}:no_key")
            continue
        try:
            result = prov.lookup(query)
        except BudgetExceeded as e:
            attempted.append(f"{pname}:budget_exceeded")
            record["enrichment_note"] = str(e)
            continue
        except Exception as e:
            attempted.append(f"{pname}:error")
            record["enrichment_note"] = f"{type(e).__name__}: {e}"
            continue

        if not result:
            attempted.append(f"{pname}:no_match")
            continue

        for k, v in result.items():
            if k.startswith("_"):
                continue
            if v is None:
                continue
            # Parish government data wins on owner of record.
            if k == "owner_of_record" and record.get("owner_of_record"):
                continue
            record[k] = v

        record["enrichment_source"] = result["_source"]
        record["enrichment_retrieved_at"] = result["_retrieved_at"]
        record["enrichment_status"] = f"enriched by {pname}"
        attempted.append(f"{pname}:ok")
        break
    else:
        record["enrichment_status"] = "no provider returned data"

    record["enrichment_attempts"] = attempted
    _derive_equity(record)
    _derive_absentee(record)
    return record


def _derive_equity(record):
    """
    Equity estimate from assessed value minus last sale price.

    This is DELIBERATELY crude and labeled as such. It is not an AVM, does not
    account for mortgage balance, and assessed value is not market value --
    Louisiana assesses residential at 10% of fair market value, so raw assessed
    figures are not comparable to sale prices without adjustment.

    Module 13: "If your AI estimates equity, clearly label it as an estimate."
    A wrong number presented confidently is worse than an honest null.
    """
    assessed = record.get("assessed_value")
    last_sale = record.get("last_sale_price")

    if not assessed or not last_sale:
        record["equity_estimate"] = None
        record["equity_source"] = "unavailable: needs assessed value and sale price"
        record["equity_confidence"] = None
        return

    try:
        assessed, last_sale = float(assessed), float(last_sale)
    except (TypeError, ValueError):
        record["equity_estimate"] = None
        record["equity_source"] = "unavailable: non-numeric input"
        return

    if last_sale <= 0:
        record["equity_estimate"] = None
        record["equity_source"] = "unavailable: no valid sale price"
        return

    record["equity_estimate_pct"] = round((assessed - last_sale) / last_sale * 100, 1)
    record["equity_estimate"] = round(assessed - last_sale, 2)
    record["equity_source"] = "derived: assessed_value - last_sale_price"
    record["equity_confidence"] = "LOW"
    record["equity_caveat"] = (
        "Crude estimate. Not an AVM. Ignores mortgage balance and liens. "
        "Louisiana assesses residential property at 10% of fair market value, so "
        "assessed and sale figures are not directly comparable. For triage only -- "
        "verify before relying on it."
    )


def _derive_absentee(record):
    """
    Absentee-owner flag. Uses documented fields only, never inference.

    Priority:
      1. ownerOccupied from the provider  (authoritative)
      2. mailing address != situs address (documented comparison)
      3. EBR homestead_exempt_type == NO  (set upstream by parish sweep)
    """
    occ = record.get("owner_occupied")
    if occ is not None:
        record["absentee_owner"] = not occ
        record["absentee_source"] = "provider: ownerOccupied"
        return

    mailing = record.get("owner_mailing_address")
    situs = record.get("situs_address")
    if mailing and situs:
        m = "".join(c for c in mailing.upper() if c.isalnum())
        s = "".join(c for c in situs.upper() if c.isalnum())
        record["absentee_owner"] = not (s and s[:12] in m)
        record["absentee_source"] = "derived: mailing address vs situs address"
        return

    if record.get("homestead_exempt_type") == "NO":
        record["absentee_owner"] = True
        record["absentee_source"] = "parish: no homestead exemption"
        return

    record["absentee_owner"] = None
    record["absentee_source"] = "unavailable"


if __name__ == "__main__":
    import sys

    print("Provider availability:")
    for name, cls in PROVIDERS.items():
        p = cls()
        status = "READY" if p.available else f"no key ({p.env_key})"
        print(f"  {name:12} {status:32} budget={p.budget}/mo")

    print("\nBudget usage this month:")
    rep = budget_report()
    print("  (none recorded)" if not rep else "")
    for prov, v in rep.items():
        print(f"  {prov:12} {v['used']}/{v['budget']}")

    if len(sys.argv) > 1:
        addr = " ".join(sys.argv[1:])
        print(f"\nLookup: {addr}")
        rec = enrich({"situs_address": addr, "parish": "Orleans Parish"})
        print(json.dumps(rec, indent=2))
