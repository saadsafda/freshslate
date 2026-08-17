#!/usr/bin/env python3
"""
dnc — Do-Not-Call scrub. Fails closed.

Gate 2 of the operator's readiness plan: "DNC access active with scrub step
built into the pipeline, internal DNC list + written policy, call-time
restrictions configured."

This module is the scrub step. Nothing in this repo may dial a number that has
not passed `check_number()`, and `check_number()` refuses by default — an
unknown answer is a block, never a pass. That is the whole design:

    A missing DNC registry file does NOT mean "no matches found."
    It means "we cannot know," which means "do not call."

Three lists, three different provenances:

  1. INTERNAL  — ours. Permanent, append-only, legally required. Fully working
                 in this module today; no external dependency.
  2. NATIONAL  — FTC National DNC Registry. Requires the operator to register
                 an organization at telemarketing.donotcall.gov, obtain a
                 Subscription Account Number (SAN), and download the area-code
                 files. Not something this code can self-provision.
  3. LOUISIANA — LA Public Service Commission state list. Separate
                 registration, separate download.

Until (2) and (3) are downloaded to `deals/_config/dnc/`, every live-call check
returns blocked with `REGISTRY_NOT_LOADED`. That is correct behavior, not a bug.

Usage:
    python3 src/dnc.py --check +12255550100
    python3 src/dnc.py --add +12255550100 --reason "asked to be removed on call"
    python3 src/dnc.py --status
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DNC_DIR = REPO_ROOT / "deals" / "_config" / "dnc"
INTERNAL_LIST = DNC_DIR / "internal-dnc.jsonl"
NATIONAL_DIR = DNC_DIR / "national"
STATE_LA_DIR = DNC_DIR / "louisiana"
SELF_TEST_LIST = DNC_DIR / "self-test-numbers.jsonl"

# Federal TCPA: no telemarketing before 8am or after 9pm in the RECIPIENT's
# local time. Louisiana's own rules are not assumed to match — see
# "Unverified" in the status output.
CALL_WINDOW_START_HOUR = 8
CALL_WINDOW_END_HOUR = 21

# Area code -> (label, UTC offset in standard time, observes US DST).
#
# Deliberately NOT comprehensive: an area code absent from this table produces
# TIMEZONE_UNKNOWN, which blocks. Guessing a timezone means guessing whether
# it is legal to dial right now, and a wrong guess is a per-call statutory
# violation.
#
# Entries are added only for states lying wholly within one timezone, or for
# individual codes verified separately. Arizona is the reason the third field
# exists: it does not observe DST, so applying the US DST rule there would put
# the computed local hour an hour off for eight months of the year.
_EASTERN = ("US/Eastern", -5, True)
_CENTRAL = ("US/Central", -6, True)
_MOUNTAIN = ("US/Mountain", -7, True)
_PACIFIC = ("US/Pacific", -8, True)
_ARIZONA = ("US/Arizona (no DST)", -7, False)

AREA_CODE_TZ = {
    # Louisiana (wholly Central)
    "225": _CENTRAL, "318": _CENTRAL, "337": _CENTRAL, "504": _CENTRAL, "985": _CENTRAL,
    # Mississippi (wholly Central)
    "228": _CENTRAL, "601": _CENTRAL, "662": _CENTRAL, "769": _CENTRAL,
    # Arkansas (wholly Central)
    "479": _CENTRAL, "501": _CENTRAL, "870": _CENTRAL,
    # Alabama (wholly Central)
    "205": _CENTRAL, "251": _CENTRAL, "256": _CENTRAL, "334": _CENTRAL, "938": _CENTRAL,
    # Texas — Central except El Paso (915), which is Mountain
    "210": _CENTRAL, "214": _CENTRAL, "254": _CENTRAL, "281": _CENTRAL, "325": _CENTRAL,
    "346": _CENTRAL, "361": _CENTRAL, "409": _CENTRAL, "430": _CENTRAL, "432": _CENTRAL,
    "469": _CENTRAL, "512": _CENTRAL, "682": _CENTRAL, "713": _CENTRAL, "737": _CENTRAL,
    "806": _CENTRAL, "817": _CENTRAL, "830": _CENTRAL, "832": _CENTRAL, "903": _CENTRAL,
    "936": _CENTRAL, "940": _CENTRAL, "956": _CENTRAL, "972": _CENTRAL,
    "915": _MOUNTAIN,
    # Florida — panhandle Central, peninsula Eastern
    "850": _CENTRAL,
    "305": _EASTERN, "321": _EASTERN, "352": _EASTERN, "386": _EASTERN, "407": _EASTERN,
    "561": _EASTERN, "727": _EASTERN, "754": _EASTERN, "772": _EASTERN, "786": _EASTERN,
    "813": _EASTERN, "863": _EASTERN, "904": _EASTERN, "941": _EASTERN, "954": _EASTERN,
    # New Jersey (wholly Eastern)
    "201": _EASTERN, "551": _EASTERN, "609": _EASTERN, "640": _EASTERN, "732": _EASTERN,
    "848": _EASTERN, "856": _EASTERN, "862": _EASTERN, "908": _EASTERN, "973": _EASTERN,
    # New York (wholly Eastern)
    "212": _EASTERN, "315": _EASTERN, "332": _EASTERN, "347": _EASTERN, "516": _EASTERN,
    "518": _EASTERN, "585": _EASTERN, "607": _EASTERN, "631": _EASTERN, "646": _EASTERN,
    "680": _EASTERN, "716": _EASTERN, "718": _EASTERN, "838": _EASTERN, "845": _EASTERN,
    "914": _EASTERN, "917": _EASTERN, "929": _EASTERN, "934": _EASTERN,
    # Illinois (wholly Central)
    "217": _CENTRAL, "224": _CENTRAL, "309": _CENTRAL, "312": _CENTRAL, "331": _CENTRAL,
    "618": _CENTRAL, "630": _CENTRAL, "708": _CENTRAL, "773": _CENTRAL, "779": _CENTRAL,
    "815": _CENTRAL, "847": _CENTRAL, "872": _CENTRAL,
    # Georgia (wholly Eastern)
    "229": _EASTERN, "404": _EASTERN, "470": _EASTERN, "478": _EASTERN, "678": _EASTERN,
    "706": _EASTERN, "762": _EASTERN, "770": _EASTERN, "912": _EASTERN, "943": _EASTERN,
    # Ohio (wholly Eastern)
    "216": _EASTERN, "220": _EASTERN, "234": _EASTERN, "326": _EASTERN, "330": _EASTERN,
    "380": _EASTERN, "419": _EASTERN, "440": _EASTERN, "513": _EASTERN, "567": _EASTERN,
    "614": _EASTERN, "740": _EASTERN, "937": _EASTERN,
    # Pennsylvania (wholly Eastern)
    "215": _EASTERN, "223": _EASTERN, "267": _EASTERN, "272": _EASTERN, "412": _EASTERN,
    "445": _EASTERN, "484": _EASTERN, "570": _EASTERN, "610": _EASTERN, "717": _EASTERN,
    "724": _EASTERN, "814": _EASTERN, "878": _EASTERN,
    # Massachusetts / Connecticut / Maryland / Virginia / the Carolinas (all wholly Eastern)
    "339": _EASTERN, "351": _EASTERN, "413": _EASTERN, "508": _EASTERN, "617": _EASTERN,
    "774": _EASTERN, "781": _EASTERN, "857": _EASTERN, "978": _EASTERN,
    "203": _EASTERN, "475": _EASTERN, "860": _EASTERN, "959": _EASTERN,
    "240": _EASTERN, "301": _EASTERN, "410": _EASTERN, "443": _EASTERN, "667": _EASTERN,
    "276": _EASTERN, "434": _EASTERN, "540": _EASTERN, "571": _EASTERN, "703": _EASTERN,
    "757": _EASTERN, "804": _EASTERN,
    "252": _EASTERN, "336": _EASTERN, "704": _EASTERN, "743": _EASTERN, "828": _EASTERN,
    "910": _EASTERN, "919": _EASTERN, "980": _EASTERN, "984": _EASTERN,
    "803": _EASTERN, "843": _EASTERN, "854": _EASTERN, "864": _EASTERN,
    # California (wholly Pacific)
    "209": _PACIFIC, "213": _PACIFIC, "279": _PACIFIC, "310": _PACIFIC, "323": _PACIFIC,
    "408": _PACIFIC, "415": _PACIFIC, "424": _PACIFIC, "442": _PACIFIC, "510": _PACIFIC,
    "530": _PACIFIC, "559": _PACIFIC, "562": _PACIFIC, "619": _PACIFIC, "626": _PACIFIC,
    "628": _PACIFIC, "650": _PACIFIC, "657": _PACIFIC, "661": _PACIFIC, "669": _PACIFIC,
    "707": _PACIFIC, "714": _PACIFIC, "747": _PACIFIC, "760": _PACIFIC, "805": _PACIFIC,
    "818": _PACIFIC, "831": _PACIFIC, "858": _PACIFIC, "909": _PACIFIC, "916": _PACIFIC,
    "925": _PACIFIC, "949": _PACIFIC, "951": _PACIFIC,
    # Washington (wholly Pacific)
    "206": _PACIFIC, "253": _PACIFIC, "360": _PACIFIC, "425": _PACIFIC, "509": _PACIFIC,
    "564": _PACIFIC,
    # Colorado (wholly Mountain)
    "303": _MOUNTAIN, "719": _MOUNTAIN, "720": _MOUNTAIN, "970": _MOUNTAIN,
    # Arizona — Mountain standard time year-round, no DST. The Navajo Nation
    # DOES observe DST, so 928 in particular can be wrong; it is omitted
    # rather than guessed.
    "480": _ARIZONA, "602": _ARIZONA, "623": _ARIZONA, "520": _ARIZONA,
}

# Toll-free and non-geographic prefixes have no recipient locality, so the
# recipient-local-time rule cannot be evaluated for them.
NON_GEOGRAPHIC = {"800", "833", "844", "855", "866", "877", "888", "900"}


def normalize(number: str):
    """To bare 10-digit NANP. Returns None if it is not a valid US number."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    if digits[0] in "01" or digits[3] in "01":
        return None  # invalid NPA/NXX
    return digits


def _ensure_dirs():
    DNC_DIR.mkdir(parents=True, exist_ok=True)
    NATIONAL_DIR.mkdir(parents=True, exist_ok=True)
    STATE_LA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- internal

def load_internal():
    """Internal DNC. Append-only JSONL; every entry keeps who/when/why."""
    if not INTERNAL_LIST.exists():
        return {}
    out = {}
    with open(INTERNAL_LIST) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            n = e.get("number")
            if n:
                out[n] = e
    return out


def add_internal(number: str, reason: str, source: str = "manual"):
    """Add to the permanent internal DNC list. Never removes — a suppression
    request is permanent, and rewriting history here would destroy the audit
    trail that proves it was honored."""
    n = normalize(number)
    if not n:
        raise ValueError(f"not a valid US number: {number!r}")
    _ensure_dirs()
    entry = {
        "number": n,
        "reason": reason,
        "source": source,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(INTERNAL_LIST, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


# ------------------------------------------------------------------ self-test

def load_self_test():
    """Numbers the operator has attested they own and consent to be called on.

    Calling a number you control, with your own consent, to test a system is
    not telemarketing — the DNC registries do not govern it. This list is what
    keeps that carve-out narrow: `--self-test` works ONLY for numbers
    registered here, so the flag cannot become a general bypass. Registering a
    number is a separate, deliberate act with a recorded attestation.
    """
    if not SELF_TEST_LIST.exists():
        return {}
    out = {}
    with open(SELF_TEST_LIST) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("number"):
                out[e["number"]] = e
    return out


VALID_RELATIONSHIPS = ("self", "consenting-party")


def add_self_test(number: str, attestation: str, label: str = "",
                  relationship: str = "self", person: str = ""):
    """Register a number for live test calls.

    `relationship` must be accurate, because it is the whole basis for the
    carve-out:
      self             - the operator's own line
      consenting-party - someone else who has agreed to receive a test call
                         (the readiness plan permits "your own phone and
                         consenting friends"). `person` names who consented.

    Recording a third party's line as "self" would make the attestation false,
    which is worse than having no record at all.
    """
    n = normalize(number)
    if not n:
        raise ValueError(f"not a valid US number: {number!r}")
    if relationship not in VALID_RELATIONSHIPS:
        raise ValueError(f"relationship must be one of {VALID_RELATIONSHIPS}")
    if not attestation or len(attestation.strip()) < 10:
        raise ValueError(
            "an explicit attestation is required, e.g. "
            "--attest \"I own and control this number and consent to test calls\""
        )
    if relationship == "consenting-party" and not person.strip():
        raise ValueError(
            "--person is required for a consenting-party registration: record WHO consented"
        )
    _ensure_dirs()
    entry = {
        "number": n,
        "label": label,
        "relationship": relationship,
        "person": person.strip(),
        "attestation": attestation.strip(),
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(SELF_TEST_LIST, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


# ---------------------------------------------------- registry (national/state)

def _load_registry_dir(path: Path):
    """Load FTC/state DNC downloads. Accepts one 10-digit number per line, or
    CSV whose first column is the number. Returns (set_of_numbers, [filenames])."""
    numbers, files = set(), []
    if not path.exists():
        return numbers, files
    for p in sorted(path.iterdir()):
        if p.is_dir() or p.name.startswith("."):
            continue
        if p.suffix.lower() not in (".txt", ".csv", ".dat"):
            continue
        files.append(p.name)
        with open(p, newline="", errors="replace") as f:
            if p.suffix.lower() == ".csv":
                for row in csv.reader(f):
                    if row:
                        n = normalize(row[0])
                        if n:
                            numbers.add(n)
            else:
                for line in f:
                    n = normalize(line)
                    if n:
                        numbers.add(n)
    return numbers, files


_REGISTRY_CACHE = {}


def load_registries(refresh=False):
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE and not refresh:
        return _REGISTRY_CACHE
    nat, nat_files = _load_registry_dir(NATIONAL_DIR)
    la, la_files = _load_registry_dir(STATE_LA_DIR)
    _REGISTRY_CACHE = {
        "national": {"numbers": nat, "files": nat_files, "loaded": bool(nat_files)},
        "louisiana": {"numbers": la, "files": la_files, "loaded": bool(la_files)},
    }
    return _REGISTRY_CACHE


# ------------------------------------------------------------ calling hours

def local_hour(area_code, now_utc=None):
    """Recipient-local hour, or None if we cannot determine it."""
    tz = AREA_CODE_TZ.get(area_code)
    if not tz:
        return None, None
    name, std_offset, observes_dst = tz
    now_utc = now_utc or datetime.now(timezone.utc)
    # US DST: second Sunday March -> first Sunday November. Computed rather
    # than assumed so this stays correct without a tz database.
    year = now_utc.year
    march = datetime(year, 3, 8, tzinfo=timezone.utc)
    dst_start = march + timedelta(days=(6 - march.weekday()) % 7)
    nov = datetime(year, 11, 1, tzinfo=timezone.utc)
    dst_end = nov + timedelta(days=(6 - nov.weekday()) % 7)
    in_dst = observes_dst and dst_start <= now_utc < dst_end
    offset = std_offset + (1 if in_dst else 0)
    return (now_utc + timedelta(hours=offset)).hour, name


# ------------------------------------------------------------------- check

def check_number(number: str, now_utc=None, allow_unloaded_registries=False,
                 self_test=False):
    """The scrub. Returns a dict; `allowed` is True only if every check passes.

    allow_unloaded_registries is for DRY RUNS ONLY. It must never be set on a
    live-call path — it exists so a dry run can show the rest of the checks
    instead of stopping at REGISTRY_NOT_LOADED.

    self_test permits a LIVE call without the registries, but only to a number
    already registered via add_self_test(). Everything else still applies:
    an internal-DNC hit still blocks (absolutely — if you asked to be
    suppressed, that holds even for your own test line), as do calling hours
    and number validity.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    result = {
        "input": number,
        "number": None,
        "allowed": False,
        "blocks": [],
        "warnings": [],
        "checked_at": now_utc.isoformat(),
    }

    n = normalize(number)
    if not n:
        result["blocks"].append({
            "code": "INVALID_NUMBER",
            "reason": f"{number!r} is not a valid 10-digit US number",
            "source": "format check",
        })
        return result
    result["number"] = n
    npa = n[:3]

    internal = load_internal()
    if n in internal:
        e = internal[n]
        result["blocks"].append({
            "code": "INTERNAL_DNC",
            "reason": f"on internal DNC list since {e.get('added_at','?')}: {e.get('reason','no reason recorded')}",
            "source": str(INTERNAL_LIST.relative_to(REPO_ROOT)),
        })

    if self_test:
        st = load_self_test()
        if n not in st:
            result["blocks"].append({
                "code": "SELF_TEST_NOT_REGISTERED",
                "reason": (f"--self-test was used, but {n} is not on the self-test list. "
                           f"Register it first with:  python3 src/dnc.py --add-self-test "
                           f"\"{number}\" --attest \"...\"  . This flag only ever applies to "
                           f"numbers you have attested you own."),
                "source": str(SELF_TEST_LIST.relative_to(REPO_ROOT)),
            })
        else:
            e = st[n]
            rel = e.get("relationship", "self")
            who = (f"operator-owned line" if rel == "self"
                   else f"consenting party: {e.get('person') or 'UNNAMED'}")
            result["warnings"].append({
                "code": "SELF_TEST_MODE",
                "reason": (f"TEST CALL to a {who}. DNC registries are not consulted. "
                           f"Attested: {e.get('attestation','')!r} on {e.get('added_at','?')}. "
                           f"This carve-out covers testing only — it is not a basis for "
                           f"calling anyone else."),
                "source": str(SELF_TEST_LIST.relative_to(REPO_ROOT)),
            })

    reg = load_registries()
    for key, code, label in (
        ("national", "NATIONAL_DNC", "FTC National DNC Registry"),
        ("louisiana", "STATE_DNC_LA", "Louisiana PSC DNC list"),
    ):
        r = reg[key]
        if not r["loaded"]:
            if not allow_unloaded_registries and not self_test:
                result["blocks"].append({
                    "code": "REGISTRY_NOT_LOADED",
                    "reason": (f"{label} is not downloaded. Cannot confirm this number is "
                               f"absent from it, so the call is refused. This is the scrub "
                               f"failing closed, not an error."),
                    "source": f"{key} registry",
                })
            else:
                result["warnings"].append({
                    "code": "REGISTRY_NOT_LOADED",
                    "reason": f"{label} not downloaded — NOT actually scrubbed against it",
                    "source": f"{key} registry",
                })
        elif n in r["numbers"]:
            result["blocks"].append({
                "code": code,
                "reason": f"listed on the {label}",
                "source": f"{key} registry ({len(r['files'])} file(s))",
            })

    if npa in NON_GEOGRAPHIC:
        result["warnings"].append({
            "code": "NON_GEOGRAPHIC",
            "reason": f"area code {npa} is toll-free/non-geographic; recipient local time is undefined",
            "source": "area code table",
        })
    else:
        hour, tzname = local_hour(npa, now_utc)
        if hour is None:
            result["blocks"].append({
                "code": "TIMEZONE_UNKNOWN",
                "reason": (f"area code {npa} is not in the timezone table, so recipient "
                           f"local time cannot be determined. Add it to AREA_CODE_TZ in "
                           f"src/dnc.py rather than guessing."),
                "source": "area code table",
            })
        elif not (CALL_WINDOW_START_HOUR <= hour < CALL_WINDOW_END_HOUR):
            result["blocks"].append({
                "code": "CALLING_HOURS",
                "reason": (f"recipient local time is {hour:02d}:xx ({tzname}); federal window "
                           f"is {CALL_WINDOW_START_HOUR:02d}:00-{CALL_WINDOW_END_HOUR:02d}:00"),
                "source": "TCPA calling-hours rule",
            })
        else:
            result["recipient_local_hour"] = hour
            result["recipient_timezone"] = tzname

    result["allowed"] = not result["blocks"]
    return result


def assert_callable(number: str, self_test=False):
    """Raise PermissionError unless the number passes every check.
    This is the function a live-call path must use."""
    r = check_number(number, self_test=self_test)
    if not r["allowed"]:
        lines = [f"{b['code']}: {b['reason']}" for b in r["blocks"]]
        raise PermissionError("DNC scrub refused this number:\n  - " + "\n  - ".join(lines))
    return r


# -------------------------------------------------------------------- CLI

def cmd_status():
    reg = load_registries(refresh=True)
    internal = load_internal()
    print("# DNC Scrub Status\n")
    print(f"Internal DNC list: {len(internal)} number(s)")
    print(f"  file: {INTERNAL_LIST.relative_to(REPO_ROOT)}"
          f"{'' if INTERNAL_LIST.exists() else '  (not created yet)'}\n")

    for key, label, howto in (
        ("national", "FTC National DNC Registry",
         "Register the organization at telemarketing.donotcall.gov, obtain a "
         "Subscription Account Number (SAN), download the area-code files, and "
         f"place them in {NATIONAL_DIR.relative_to(REPO_ROOT)}/"),
        ("louisiana", "Louisiana PSC DNC list",
         "Register with the Louisiana Public Service Commission, download the "
         f"state list, and place it in {STATE_LA_DIR.relative_to(REPO_ROOT)}/"),
    ):
        r = reg[key]
        state = f"🟢 LOADED — {len(r['numbers'])} numbers from {len(r['files'])} file(s)" \
            if r["loaded"] else "🔴 NOT LOADED — all live calls blocked"
        print(f"{label}: {state}")
        if not r["loaded"]:
            print(f"  To load: {howto}")
        print()

    gate = "🟢 OPEN" if all(reg[k]["loaded"] for k in ("national", "louisiana")) else "🔴 CLOSED"
    print(f"**Scrub gate: {gate}**")
    if gate.startswith("🔴"):
        print("\nNo live call can pass `assert_callable()` until both registries are")
        print("downloaded. This is intentional — an unscrubbed dial is the single")
        print("highest per-incident exposure in this system (TCPA statutory damages,")
        print("per call). See docs/planning/2026-08-10-operational-readiness-plan.md.")
    print("\n## Not verified by this module\n")
    print("- Whether Louisiana's own call-window rules differ from the federal")
    print("  08:00-21:00 window. The federal window is what is enforced here.")
    print("- Whether an entity on the buyer list is 'business-to-business' in a")
    print("  way that changes DNC applicability. That is a counsel question;")
    print("  this module scrubs every number the same way regardless.")


def main():
    ap = argparse.ArgumentParser(description="DNC scrub — fails closed")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", metavar="NUMBER", help="Check one number")
    g.add_argument("--add", metavar="NUMBER", help="Add a number to the internal DNC list")
    g.add_argument("--status", action="store_true", help="Show registry/gate status")
    g.add_argument("--add-self-test", metavar="NUMBER",
                   help="Register a number you OWN for self-test calls (requires --attest)")
    ap.add_argument("--reason", help="Required with --add")
    ap.add_argument("--source", default="manual", help="Provenance for --add")
    ap.add_argument("--attest", help="Required with --add-self-test: the ownership/consent attestation")
    ap.add_argument("--label", default="", help="Optional label for --add-self-test")
    ap.add_argument("--relationship", default="self", choices=list(VALID_RELATIONSHIPS),
                    help="'self' = your own line; 'consenting-party' = someone who agreed "
                         "to a test call (requires --person)")
    ap.add_argument("--person", default="", help="Who consented (required for consenting-party)")
    ap.add_argument("--self-test", action="store_true",
                    help="With --check: evaluate as a self-test call")
    ap.add_argument("--json", action="store_true", help="JSON output for --check")
    args = ap.parse_args()

    if args.status:
        cmd_status()
        return 0

    if args.add:
        if not args.reason:
            print("FATAL: --reason is required with --add.", file=sys.stderr)
            return 1
        try:
            e = add_internal(args.add, args.reason, args.source)
        except ValueError as ex:
            print(f"FATAL: {ex}", file=sys.stderr)
            return 1
        print(f"✅ Added {e['number']} to internal DNC list.")
        print(f"   reason: {e['reason']}   source: {e['source']}")
        return 0

    if args.add_self_test:
        try:
            e = add_self_test(args.add_self_test, args.attest or "", args.label,
                              args.relationship, args.person)
        except ValueError as ex:
            print(f"FATAL: {ex}", file=sys.stderr)
            return 1
        who = "your own line" if e["relationship"] == "self" else f"consenting party: {e['person']}"
        print(f"✅ Registered {e['number']} as a test number ({who}).")
        print(f"   attestation: {e['attestation']!r}")
        print("   This permits LIVE test calls to this number without the DNC")
        print("   registries. It does not authorize calling anyone else.")
        return 0

    r = check_number(args.check, self_test=args.self_test)
    if args.json:
        print(json.dumps(r, indent=2))
        return 0 if r["allowed"] else 1

    print(f"Number: {r['number'] or r['input']}")
    print(f"Result: {'🟢 CLEAR TO CALL' if r['allowed'] else '⛔ DO NOT CALL'}")
    for b in r["blocks"]:
        print(f"  ⛔ {b['code']}: {b['reason']}")
    for w in r["warnings"]:
        print(f"  ⚠️  {w['code']}: {w['reason']}")
    return 0 if r["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
