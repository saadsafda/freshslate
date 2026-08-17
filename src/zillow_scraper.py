"""Legacy Zillow response parser — network collection is disabled.

The source-recon decision recorded in ``config/sources.json`` prohibits
automated Zillow access. The parsing helpers remain available for previously
saved, lawfully obtained test fixtures, but every network-client construction
passes through the same hard source-policy gate as the parish sweep.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

try:
    from curl_cffi import requests as crequests
except ImportError:
    crequests = None


SEARCH_URL = "https://www.zillow.com/async-create-search-page-state"

# Jefferson Parish, LA. regionType 8 == county/parish.
JEFFERSON_PARISH = {"regionId": 2743, "regionType": 8}

# Approximate bounding box for Jefferson Parish. Widen if you see edge
# listings missing; the parish is an awkward shape running down to the coast.
JEFFERSON_BOUNDS = {
    "north": 30.10,
    "south": 29.20,
    "east": -89.95,
    "west": -90.45,
}

MAX_PAGES = 20  # Zillow's hard ceiling
PAGE_SIZE = 41

log = logging.getLogger("zillow")


class Blocked(Exception):
    """Raised when Zillow serves a bot-detection response."""


def enforce_source_policy() -> None:
    """Fail before constructing a session or making any Zillow request."""
    from parish_sweep import assert_host_permitted, load_config

    assert_host_permitted(load_config(), "www.zillow.com")


@dataclass
class Listing:
    zpid: str | None = None
    status: str | None = None
    price: int | None = None
    price_raw: str | None = None
    beds: float | None = None
    baths: float | None = None
    sqft: int | None = None
    lot_sqft: int | None = None
    year_built: int | None = None
    home_type: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    days_on_zillow: int | None = None
    zestimate: int | None = None
    rent_zestimate: int | None = None
    broker: str | None = None
    url: str | None = None
    photo: str | None = None


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_listing(raw: dict) -> Listing:
    """Flatten one entry from cat1.searchResults.listResults."""
    hi = raw.get("hdpData", {}).get("homeInfo", {}) or {}
    addr = raw.get("addressStreet") or hi.get("streetAddress")

    url = raw.get("detailUrl") or ""
    if url.startswith("/"):
        url = "https://www.zillow.com" + url

    return Listing(
        zpid=str(raw.get("zpid")) if raw.get("zpid") else None,
        status=raw.get("statusText") or hi.get("homeStatus"),
        price=_int(hi.get("price")) or _int(raw.get("unformattedPrice")),
        price_raw=raw.get("price"),
        beds=_float(raw.get("beds") or hi.get("bedrooms")),
        baths=_float(raw.get("baths") or hi.get("bathrooms")),
        sqft=_int(raw.get("area") or hi.get("livingArea")),
        lot_sqft=_int(hi.get("lotAreaValue")),
        year_built=_int(hi.get("yearBuilt")),
        home_type=hi.get("homeType"),
        street=addr,
        city=raw.get("addressCity") or hi.get("city"),
        state=raw.get("addressState") or hi.get("state"),
        zipcode=raw.get("addressZipcode") or hi.get("zipcode"),
        latitude=_float(raw.get("latLong", {}).get("latitude") or hi.get("latitude")),
        longitude=_float(raw.get("latLong", {}).get("longitude") or hi.get("longitude")),
        days_on_zillow=_int(hi.get("daysOnZillow")),
        zestimate=_int(hi.get("zestimate")),
        rent_zestimate=_int(hi.get("rentZestimate")),
        broker=raw.get("brokerName"),
        url=url or None,
        photo=raw.get("imgSrc"),
    )


class ZillowScraper:
    def __init__(
        self,
        proxy: str | None = None,
        delay: float = 6.0,
        jitter: float = 3.0,
        timeout: int = 30,
        max_retries: int = 3,
        impersonate: str = "chrome124",
    ):
        enforce_source_policy()
        if crequests is None:
            raise RuntimeError("curl_cffi is required to construct the legacy client")

        self.delay = delay
        self.jitter = jitter
        self.timeout = timeout
        self.max_retries = max_retries
        self.impersonate = impersonate

        self.session = crequests.Session(impersonate=impersonate)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        self.session.headers.update({
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://www.zillow.com",
            "referer": "https://www.zillow.com/homes/for_sale/2743_rid/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })

    def warm_up(self) -> None:
        """Fetch the HTML page first so the session picks up cookies.

        Hitting the JSON endpoint cold, with no prior page view, is itself a
        strong bot signal. This mirrors what a browser actually does.
        """
        try:
            r = self.session.get(
                "https://www.zillow.com/homes/for_sale/2743_rid/",
                timeout=self.timeout,
            )
            log.info("Warm-up request: HTTP %s (%d cookies)", r.status_code, len(self.session.cookies))
        except Exception as exc:
            log.warning("Warm-up failed: %s", exc)

    def _sleep(self) -> None:
        time.sleep(self.delay + random.uniform(0, self.jitter))

    def _build_payload(self, page: int, bounds: dict, use_region: bool) -> dict:
        query_state: dict[str, Any] = {
            "isMapVisible": True,
            "isListVisible": True,
            "mapBounds": bounds,
            "filterState": {
                "sortSelection": {"value": "days"},   # newest first, stable ordering
                "isForSaleByAgent": {"value": True},
                "isForSaleByOwner": {"value": True},
                "isNewConstruction": {"value": True},
                "isForSaleForeclosure": {"value": True},
                "isAuction": {"value": False},
                "isComingSoon": {"value": True},
                "isAllHomes": {"value": True},
            },
            "pagination": {"currentPage": page},
        }
        # When tiling, drop the region filter — the bounding box defines the
        # area, and keeping both makes Zillow intersect them unpredictably.
        if use_region:
            query_state["regionSelection"] = [JEFFERSON_PARISH]

        return {
            "searchQueryState": query_state,
            "wants": {"cat1": ["listResults", "mapResults"], "cat2": ["total"]},
            "requestId": random.randint(2, 12),
            "isDebugRequest": False,
        }

    def fetch_page(self, page: int, bounds: dict, use_region: bool = True) -> dict:
        payload = self._build_payload(page, bounds, use_region)

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(SEARCH_URL, json=payload, timeout=self.timeout)
            except Exception as exc:
                log.warning("Request error (attempt %d/%d): %s", attempt, self.max_retries, exc)
                time.sleep(2 ** attempt)
                continue

            if resp.status_code in (403, 429):
                raise Blocked(f"HTTP {resp.status_code} — bot detection or rate limit")
            if resp.status_code != 200:
                log.warning("HTTP %s (attempt %d/%d)", resp.status_code, attempt, self.max_retries)
                time.sleep(2 ** attempt)
                continue

            try:
                return resp.json()
            except json.JSONDecodeError:
                body = resp.text[:300].lower()
                if "px-captcha" in body or "perimeterx" in body or "captcha" in body:
                    raise Blocked("Served a CAPTCHA challenge")
                log.warning("Non-JSON response (attempt %d/%d)", attempt, self.max_retries)
                time.sleep(2 ** attempt)

        raise Blocked(f"Failed after {self.max_retries} attempts on page {page}")

    def scrape_area(self, bounds: dict, use_region: bool = True, label: str = "area") -> Iterator[Listing]:
        """Page through a single search area, up to Zillow's 20-page ceiling."""
        total_reported = None

        for page in range(1, MAX_PAGES + 1):
            data = self.fetch_page(page, bounds, use_region)
            cat1 = data.get("cat1", {})
            results = cat1.get("searchResults", {}).get("listResults", []) or []

            if total_reported is None:
                total_reported = data.get("categoryTotals", {}).get("cat1", {}).get("totalResultCount")
                if total_reported:
                    log.info("[%s] Zillow reports %s total results", label, total_reported)
                    if total_reported > MAX_PAGES * PAGE_SIZE:
                        log.warning(
                            "[%s] %s results exceeds the ~%d cap — use --tile to subdivide",
                            label, total_reported, MAX_PAGES * PAGE_SIZE,
                        )

            if not results:
                log.info("[%s] Page %d empty — done", label, page)
                break

            log.info("[%s] Page %d: %d listings", label, page, len(results))
            for raw in results:
                yield parse_listing(raw)

            total_pages = cat1.get("searchList", {}).get("totalPages", MAX_PAGES)
            if page >= total_pages:
                break

            self._sleep()


def tile_bounds(bounds: dict, n: int) -> list[dict]:
    """Split a bounding box into an n x n grid to get past the result cap."""
    lat_step = (bounds["north"] - bounds["south"]) / n
    lng_step = (bounds["east"] - bounds["west"]) / n
    tiles = []
    for i in range(n):
        for j in range(n):
            tiles.append({
                "south": bounds["south"] + i * lat_step,
                "north": bounds["south"] + (i + 1) * lat_step,
                "west": bounds["west"] + j * lng_step,
                "east": bounds["west"] + (j + 1) * lng_step,
            })
    return tiles


def save(listings: list[Listing], out: Path) -> None:
    rows = [asdict(x) for x in listings]

    if out.suffix.lower() == ".json":
        out.write_text(json.dumps(rows, indent=2))
    else:
        try:
            import pandas as pd
            pd.DataFrame(rows).to_csv(out, index=False)
        except ImportError:
            import csv
            with out.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(Listing().__dict__))
                writer.writeheader()
                writer.writerows(rows)

    log.info("Wrote %d listings -> %s", len(rows), out)


def main() -> int:
    try:
        enforce_source_policy()
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        print(
            "Use an approved government API, licensed data provider, or the "
            "Jefferson public-records request workflow instead.",
            file=sys.stderr,
        )
        return 2

    ap = argparse.ArgumentParser(description="Scrape Zillow listings for Jefferson Parish, LA")
    ap.add_argument("--out", type=Path, default=Path("jefferson_parish.csv"))
    ap.add_argument("--proxy", help="Residential proxy, e.g. http://user:pass@host:port")
    ap.add_argument("--delay", type=float, default=6.0, help="Base seconds between requests")
    ap.add_argument("--jitter", type=float, default=3.0, help="Random extra delay, 0..N seconds")
    ap.add_argument("--tile", type=int, default=0, metavar="N",
                    help="Subdivide into an NxN grid to beat the ~820 result cap")
    ap.add_argument("--impersonate", default="chrome124", help="curl_cffi browser profile")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.proxy:
        log.warning("No --proxy set. Datacenter and bare residential IPs are usually "
                    "blocked immediately. Expect this to fail without one.")

    scraper = ZillowScraper(
        proxy=args.proxy,
        delay=args.delay,
        jitter=args.jitter,
        impersonate=args.impersonate,
    )
    scraper.warm_up()
    time.sleep(2)

    seen: dict[str, Listing] = {}

    if args.tile:
        tiles = tile_bounds(JEFFERSON_BOUNDS, args.tile)
        log.info("Tiling into %d cells", len(tiles))
        for idx, box in enumerate(tiles, 1):
            label = f"tile {idx}/{len(tiles)}"
            try:
                for listing in scraper.scrape_area(box, use_region=False, label=label):
                    if listing.zpid:
                        seen[listing.zpid] = listing
            except Blocked as exc:
                log.error("[%s] Blocked: %s", label, exc)
                log.error("Stopping early. Partial results will still be saved.")
                break
            scraper._sleep()
    else:
        try:
            for listing in scraper.scrape_area(JEFFERSON_BOUNDS, use_region=True, label="jefferson"):
                if listing.zpid:
                    seen[listing.zpid] = listing
        except Blocked as exc:
            log.error("Blocked: %s", exc)
            log.error("Fixes, in order of effectiveness: (1) use a residential proxy, "
                      "(2) raise --delay, (3) try --impersonate chrome131 or safari17_0.")

    listings = list(seen.values())
    if not listings:
        log.error("No listings collected.")
        return 1

    save(listings, args.out)

    priced = [x.price for x in listings if x.price]
    if priced:
        priced.sort()
        log.info("Median price: $%s | Range: $%s - $%s",
                 f"{priced[len(priced)//2]:,}", f"{priced[0]:,}", f"{priced[-1]:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
