#!/usr/bin/env python3
"""Build gp_mtd.json (the map's 'Total Gross Profit (MTD)' leaderboard) from real data only.

    python3 gen_gp_mtd.py --export tpro_terminal129.csv --owners tpro_hubspot_owners.csv --as-of 2026-10-17 [--out gp_mtd.json]

--export : TPRO Summary Bot "Bill To" export for the month (columns Customer, "# Loads", "Gross Profit"); account-level, no rep split.
--owners : the 'Customers' tab of the TPRO-vs-HubSpot ownership sheet saved as CSV
           (TPRO Customer, Team Steve owns in HubSpot?, HubSpot owner, ...).
Join = exact TPRO customer name. GP goes to the HubSpot owner when that owner is one of the five reps AND the sheet says
'Yes'; 'Possible match - verify' rows are counted for that owner but flagged unverified (reported separately as gp_unverified);
everything else (no match, owner not a rep e.g. Steve, customer missing from sheet) is 'Unassigned'. Nothing is estimated.
"""
import argparse, csv, json, os, re
from datetime import datetime
from zoneinfo import ZoneInfo
REP = {"Kahekili Barrozo": "Kili", "Simran Subramanian": "Simran", "Nicholas McNamara": "Nick", "Mia Medjedovic": "Mia", "Addison Parker": "Addie"}
num = lambda s: float(re.sub(r"[,$\s]", "", s or "0") or 0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True); ap.add_argument("--owners", required=True)
    ap.add_argument("--as-of", required=True); ap.add_argument("--out", default="gp_mtd.json")
    ap.add_argument("--source", default="TPRO Summary Bot Bill To export (terminal 129) x TPRO-vs-HubSpot ownership sheet")
    a = ap.parse_args()
    own = {r["TPRO Customer"].strip(): r for r in csv.DictReader(open(a.owners, encoding="utf-8"))}
    # Repo-tracked overrides (exact TPRO customer name) win over the ownership sheet, so rebuilds keep confirmed owners.
    ov = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gp_owner_overrides.csv")
    if os.path.exists(ov):
        for r in csv.DictReader(open(ov, encoding="utf-8")):
            own[r["TPRO Customer"].strip()] = {**own.get(r["TPRO Customer"].strip(), {}), **r}
    gp = {k: {"gp": 0.0, "gp_verified": 0.0, "gp_unverified": 0.0, "customers": []} for k in list(REP.values()) + ["Unassigned"]}
    loads = 0; total = 0.0
    for r in csv.DictReader(open(a.export, encoding="utf-8-sig")):
        name = r["Customer"].strip(); v = num(r["Gross Profit"]); loads += int(num(r["# Loads"])); total += v
        o = own.get(name); rep = REP.get(((o or {}).get("HubSpot owner") or "").strip()); flag = (o or {}).get("Team Steve owns in HubSpot?") or ""
        status = "verified" if flag == "Yes" else "possible match - unverified" if flag.startswith("Possible") else "unmatched"
        key = rep if rep and status != "unmatched" else "Unassigned"
        g = gp[key]; g["gp"] += v
        g["gp_unverified" if status.startswith("possible") and key != "Unassigned" else "gp_verified"] += v
        g["customers"].append({"customer": name, "gp": round(v, 2), "match": status if key != "Unassigned" else (status + (" / owner not a rep: " + (o or {}).get("HubSpot owner", "") if o and o.get("HubSpot owner") else ""))})
    reps = [{"rep": k, **{x: (round(y, 2) if x != "customers" else y) for x, y in g.items()}} for k, g in gp.items()]
    out = {"month": a.as_of[:7], "as_of": a.as_of, "source": a.source, "loads": loads, "total_gp": round(total, 2),
           "note": "Account-level GP assigned to reps via HubSpot ownership; 'possible match' rows are unverified (gp_unverified). Unassigned = no/unclear owner.",
           "generated_at": datetime.now(ZoneInfo("America/Chicago")).isoformat(timespec="seconds"), "reps": reps}
    json.dump(out, open(a.out, "w"), indent=1, ensure_ascii=False); open(a.out, "a").write("\n")
    try:
        import rank_history; rank_history.update(os.path.dirname(os.path.abspath(a.out)))
    except Exception as e:
        print("rank_history skipped:", e)
    print(f"{a.out}: total ${total:,.2f}, {loads} loads"); [print(f"  {r['rep']:11s} ${r['gp']:>12,.2f}  (unverified ${r['gp_unverified']:,.2f})") for r in reps]
if __name__ == "__main__":
    main()
