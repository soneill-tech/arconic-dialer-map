#!/usr/bin/env python3
"""rank_history.json: one snapshot per day of both leaderboards' ranks, so the page can show rank-change arrows.

    python3 rank_history.py                 # write/refresh TODAY's snapshot from called_mtd.json, gp_mtd.json, quotas.json
    python3 rank_history.py --seed-calls    # also derive calls snapshots for earlier days of the month from called_mtd.json entries (real data, cumulative through that day)

Called automatically by update_called_today.py (every run) and gen_gp_mtd.py (after writing gp_mtd.json).
Format: {"snapshots": {"YYYY-MM-DD": {"calls": {"Kili": {"rank":1,"score":47}}, "gp": {"Kili": {"rank":1,"pct":54.3}}, "gp_as_of": "2026-10-17", "derived": false}}}
The page compares the live ranking with the latest snapshot dated BEFORE today (CT) and shows an arrow only for reps present in it.
Calls rank = distinct (rep, day, contact key) count in called_mtd.json; ties share a rank. GP rank = rep GP / gp_quota.
GP snapshots are never derived/backfilled (gp_mtd.json holds only the latest as-of), so GP arrows begin once two days exist.
"""
import argparse, json, os
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["Kili", "Simran", "Nick", "Mia", "Addie", "Nathan"]
GP_KEY = {"kahekili": "Kili", "kili": "Kili", "simran": "Simran", "nicholas": "Nick", "nick": "Nick", "mia": "Mia", "addison": "Addie", "addie": "Addie", "nathan": "Nathan"}
KEEP_DAYS = 45


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def rank(scores):
    """scores {rep: value} -> {rep: {rank, ...}} ties share rank; ORDER breaks display order only."""
    items = sorted(scores.items(), key=lambda kv: (-kv[1], ORDER.index(kv[0]) if kv[0] in ORDER else 99))
    out, r, prev = {}, 0, None
    for i, (k, v) in enumerate(items):
        if v != prev:
            r, prev = i + 1, v
        out[k] = r
    return out


def rep_key(name):
    t = str(name).lower()
    for part, k in GP_KEY.items():
        if part in t:
            return k
    return str(name)


def calls_snapshot(mtd, upto=None):
    sc = {}
    for rep, days in (mtd.get("entries") or {}).items():
        sc[rep_key(rep)] = sum(len(set(map(str, ids))) for d, ids in days.items() if upto is None or d <= upto)
    rk = rank(sc)
    return {k: {"rank": rk[k], "score": sc[k]} for k in sc}


def gp_snapshot(gp, quotas):
    if not gp or not quotas:
        return None
    by = {}
    for x in gp.get("reps", []):
        if str(x.get("rep", "")).lower() == "unassigned":
            continue
        by[x["rep"]] = float(x.get("gp") or 0)
    pct = {}
    for q in quotas.get("quotas", []):
        first = q["rep"].split()[0].lower()
        k = GP_KEY.get(first)
        if not k or not q.get("gp_quota"):
            continue
        g = next((v for rn, v in by.items() if GP_KEY.get(rn.lower()) == k), 0.0)
        pct[k] = round(g / float(q["gp_quota"]) * 100, 4)
    rk = rank(pct)
    return {k: {"rank": rk[k], "pct": round(pct[k], 1)} for k in pct}


def update(here=HERE, seed_calls=False, today=None):
    now = datetime.now(ZoneInfo("America/Chicago"))
    today = today or now.date().isoformat()
    path = os.path.join(here, "rank_history.json")
    hist = _load(path) or {"snapshots": {}}
    snaps = hist.setdefault("snapshots", {})
    mtd = _load(os.path.join(here, "called_mtd.json"))
    gp = _load(os.path.join(here, "gp_mtd.json"))
    quotas = _load(os.path.join(here, "quotas.json"))
    if mtd and seed_calls:
        for d in sorted({d for days in mtd.get("entries", {}).values() for d in days}):
            if d < today and d not in snaps:
                snaps[d] = {"calls": calls_snapshot(mtd, d), "derived": True}
    snap = snaps.get(today, {})
    if mtd and mtd.get("month") == today[:7]:
        snap["calls"] = calls_snapshot(mtd)
    if gp and gp.get("month") == today[:7]:
        g = gp_snapshot(gp, quotas)
        if g:
            snap["gp"] = g
            snap["gp_as_of"] = gp.get("as_of")
    snap["derived"] = False
    snap["written_at"] = now.isoformat(timespec="seconds")
    snaps[today] = snap
    for d in sorted(snaps)[:-KEEP_DAYS]:
        del snaps[d]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-calls", action="store_true")
    a = ap.parse_args()
    print("wrote", update(seed_calls=a.seed_calls))
