#!/usr/bin/env python3
"""
Credential loading from secrets/*.env.

One place that knows where keys live, so no other module hardcodes a path or
prints a value. Keys are read into the process environment and never logged.

Files (all optional -- a missing file disables that integration rather than
crashing the run):
    secrets/anthropic.env   ANTHROPIC_API_KEY
    secrets/retell.env      RETELL_API_KEY, RETELL_WEBHOOK_SECRET,
                            RETELL_AGENT_ID, RETELL_FROM_NUMBER
    secrets/ghl.env         GHL_API_KEY, GHL_LOCATION_ID

Never commit secrets/. It is gitignored and should be chmod 700 with 600 files.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_DIR = os.path.join(ROOT, "secrets")

FILES = {
    "anthropic": "anthropic.env",
    "retell": "retell.env",
    "ghl": "ghl.env",
}

REQUIRED = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "retell": ["RETELL_API_KEY", "RETELL_AGENT_ID", "RETELL_FROM_NUMBER"],
    "ghl": ["GHL_API_KEY", "GHL_LOCATION_ID"],
}


def _parse_env(path):
    """Minimal .env parser. No shell expansion -- values are literal."""
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip()
            # Strip matched surrounding quotes only.
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[k.strip()] = v
    return out


def load(*groups, strict=False):
    """
    Load the named credential groups into os.environ.

    Existing environment variables win -- so a VPS using real env injection or a
    secret manager is never overwritten by a stale file.

    Returns {group: bool_available}.
    """
    groups = groups or tuple(FILES)
    status = {}

    for g in groups:
        fname = FILES.get(g)
        if not fname:
            raise KeyError(f"unknown credential group: {g}")
        path = os.path.join(SECRETS_DIR, fname)

        if os.path.exists(path):
            mode = os.stat(path).st_mode & 0o777
            if mode & 0o077:
                print(
                    f"warning: {path} is mode {mode:o} -- readable beyond owner. "
                    f"Run: chmod 600 {path}",
                    file=sys.stderr,
                )
            for k, v in _parse_env(path).items():
                if not os.environ.get(k) and v:
                    os.environ[k] = v

        missing = [k for k in REQUIRED[g] if not os.environ.get(k)]
        status[g] = not missing
        if missing and strict:
            raise RuntimeError(
                f"{g}: missing {', '.join(missing)}. Expected in {path} "
                f"or the process environment."
            )

    return status


def require(group):
    """Load one group or exit with an actionable message."""
    if not load(group).get(group):
        keys = ", ".join(REQUIRED[group])
        sys.exit(
            f"error: {group} credentials unavailable.\n"
            f"  Expected {keys}\n"
            f"  in {os.path.join(SECRETS_DIR, FILES[group])}"
        )


def redact(value, keep=6):
    """Safe-to-print form of a credential. Used in status output only."""
    if not value:
        return "(unset)"
    return f"{value[:keep]}...({len(value)} chars)"


if __name__ == "__main__":
    st = load()
    print("Credential status\n")
    for g, ok in st.items():
        print(f"  {g:10} {'READY' if ok else 'INCOMPLETE'}")
        for k in REQUIRED[g]:
            print(f"      {k:24} {redact(os.environ.get(k))}")
