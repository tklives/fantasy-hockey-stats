#!/usr/bin/env python3
"""
check_no_secrets.py - fail if either ESPN cookie value appears in anything about to be published.

Run in the nightly workflow after the data and page are built, before anything is committed or
deployed. It never prints a secret, only which file contained one.

    python check_no_secrets.py data site
"""
import os
import sys
from pathlib import Path

names = ("ESPN_S2", "ESPN_SWID")
secrets = {n: os.environ.get(n, "") for n in names}
missing = [n for n, v in secrets.items() if len(v) < 8]
if missing:
    sys.exit(f"Refusing to continue: {', '.join(missing)} not set (or suspiciously short).")

# SWID is a GUID in braces; also look for it without the braces, and URL-encoded forms.
needles = {}
for n, v in secrets.items():
    for form in {v, v.strip("{}"), v.replace("{", "%7B").replace("}", "%7D")}:
        needles[form.encode()] = n

leaks = []
for root in sys.argv[1:] or ["data", "site"]:
    for path in Path(root).rglob("*"):
        if path.is_file():
            blob = path.read_bytes()
            leaks += [(path, n) for needle, n in needles.items() if needle in blob]

if leaks:
    for path, n in leaks:
        print(f"LEAK: {n} value found in {path}", file=sys.stderr)
    sys.exit(1)
print("No cookie values found in the published files.")
