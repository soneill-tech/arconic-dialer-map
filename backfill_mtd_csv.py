#!/usr/bin/env python3
"""Backfill called_mtd.json from a HubSpot calls export (columns date,owner,contact,company[,call_id]).

Scoring rule (Steve, 2026-10-18): one point per distinct (rep, day, NAMED contact). Contacts that resolve to a pin contact
in data.json within the call owner's own book are stored by HubSpot id (so live called_today/Log Call entries for the same
person dedupe); every other named contact is stored as "n:<normalized name>". Inbound / no-answer calls count. Rows whose
contact is a placeholder ('--', 'N records', 'unknown contact', blank) or a bare record ID are NOT scored (never invented).
Existing entries are unioned, never removed. Idempotent.
    python3 backfill_mtd_csv.py hs_calls_oct_2026.csv [--dry-run]
"""
import csv, json, os, re, sys, collections
from datetime import datetime
from zoneinfo import ZoneInfo
import update_called_today as u

HERE = os.path.dirname(os.path.abspath(__file__))
PH = lambda k: k.strip().lower() in ("--", "unknown contact", "") or re.fullmatch(r"\d+ records?", k.strip().lower())


def main():
    path = sys.argv[1]; dry = "--dry-run" in sys.argv
    data = json.load(open(os.path.join(HERE, "data.json")))
    by_id, _, by_name = u.build_index(data)
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    seen_row = set(); dupes = 0
    st = collections.defaultdict(lambda: collections.Counter())
    cd, mm = collections.defaultdict(set), collections.defaultdict(set)
    for r in rows:
        key = tuple(r.values())
        if key in seen_row: dupes += 1   # exact duplicate row (scrape overlap); only affects raw count
        seen_row.add(key)
        am = u.norm_am(r["owner"]); rep = u.short_am(am); day = r["date"].split()[0]; k = r["contact"].strip()
        st[rep]["raw"] += 1
        if PH(k): st[rep]["placeholder_rows"] += 1; continue
        if k.isdigit(): st[rep]["bare_id_rows"] += 1; continue
        cd[rep].add((day, u.norm_name(k)))
        hits = by_name.get(u.norm_name(k), [])
        own = [h for h in hits if h[1].get("am") == am]
        if len(own) > 1:
            co = [h for h in own if u.norm_name(h[1].get("company")) == u.norm_name(r["company"])]
            own = co or own
        if own:
            mm[rep].add((day, min(h[0] for h in own)))
        else:
            st[rep]["other_rep_book_rows" if hits else "not_on_map_rows"] += 1
            mm[rep].add((day, "n:" + u.norm_name(k)))   # named contact not in the owner's map book: keyed by name
    month = "2026-10"
    now = datetime.now(ZoneInfo("America/Chicago"))
    mtd = u.load_mtd(os.path.join(HERE, "called_mtd.json"), month)
    before = {r: sum(len(v) for v in d.values()) for r, d in mtd["entries"].items()}
    for rep, s in mm.items():
        for day, cid in s: u.mtd_add(mtd, rep, day, [cid])
    print(f"{'rep':8} {'raw':>5} {'placeholder':>11} {'bareID':>6} {'distinct':>8} {'map':>4} {'before':>6} {'after':>5}")
    for rep in ["Addie", "Mia", "Simran", "Kahekili", "Nick", "Nathan"]:
        after = sum(len(v) for v in mtd["entries"].get(rep, {}).values())
        print(f"{rep:8} {st[rep]['raw']:>5} {st[rep]['placeholder_rows']:>11} {st[rep]['bare_id_rows']:>6} {len(cd[rep]):>8} {len(mm[rep]):>4} {before.get(rep,0):>6} {after:>5}  other_book={st[rep]['other_rep_book_rows']} not_on_map={st[rep]['not_on_map_rows']}")
    print("rows", len(rows), "exact duplicate rows", dupes)
    if dry: return
    mtd["backfill"] = {"file": os.path.basename(path), "rows": len(rows), "range": "2026-10-01..2026-10-16 (CSV ends 10/16 9:49 AM CT per time-sorted rows; sync-run data covers later)",
        "rule": "distinct (rep, day, named contact); map contacts by id, others by n:<name>; no placeholders/bare IDs", "at": now.isoformat(timespec="seconds"),
        "per_rep": {r: {"raw_calls": st[r]["raw"], "distinct_contact_days": len(cd[r]), "map_matched_contact_days": len(mm[r])} for r in st}}
    u.mtd_write(os.path.join(HERE, "called_mtd.json"), mtd, now)
    mtd["source"] = "backfill from HubSpot calls CSV (backfill_mtd_csv.py) + called_today.json syncs + Log Call queue"
    json.dump(mtd, open(os.path.join(HERE, "called_mtd.json"), "w"), indent=1, ensure_ascii=False); open(os.path.join(HERE, "called_mtd.json"), "a").write("\n")

main()
