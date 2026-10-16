#!/usr/bin/env python3
"""Apply per-contact "touches since Jan 1, 2026" counts to data.json + data.js (field `touches_ytd`).

HubSpot's "Number of times contacted" (times_contacted) is ALL-TIME and has no per-activity dates, so a year-to-date
count cannot be derived from the touch-count CSV, called_today.json or last_calls.json. It needs a HubSpot activity
export filtered to 2026 (calls + emails + meetings, counted per contact). See README "Touches this year".

    python3 apply_touches_ytd.py ytd.csv [--as-of 2026-10-15T19:00] [--source "HubSpot activities 2026-01-01..."] [--dry-run]

CSV columns: contact_id,touches_ytd   (extra columns ignored; rows for contacts not on the map are skipped).
Contacts with no row get touches_ytd = null (shown as "not loaded"). Manual (mc-…) contacts use their id too.
Also sets DATA.touches_ytd_updated / touches_ytd_source. Stdlib only. Never touches HubSpot.
"""
import argparse, csv, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
JS = "window.__DIALER_DATA__ = "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("--as-of"); ap.add_argument("--source", default="HubSpot activities since 2026-01-01")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = json.load(open(os.path.join(HERE, "data.json")))
    rows = {}
    for r in csv.DictReader(open(a.csv)):
        try:
            rows[str(r["contact_id"]).strip()] = int(float(r["touches_ytd"]))
        except (KeyError, ValueError):
            continue
    hit = 0
    for c in d["contacts"]:
        v = rows.get(str(c.get("hubspot_contact_id")))
        c["touches_ytd"] = v
        hit += v is not None
    d["touches_ytd_updated"] = a.as_of or datetime.now().strftime("%Y-%m-%dT%H:%M:00")
    d["touches_ytd_source"] = a.source
    print(f"{hit}/{len(d['contacts'])} map contacts matched; {len(rows) - hit} CSV rows skipped (not on map)")
    if a.dry_run:
        return
    s = json.dumps(d, indent=2, ensure_ascii=False)
    open(os.path.join(HERE, "data.json"), "w").write(s + "\n")
    open(os.path.join(HERE, "data.js"), "w").write(JS + s + ";\n")


if __name__ == "__main__":
    main()
