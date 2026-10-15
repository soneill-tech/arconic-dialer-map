#!/usr/bin/env python3
"""Add real Arconic plant pins that area-code inference can't find, plus explicit contact->plant overrides.

    python3 apply_site_overrides.py [--check]

Idempotent; edits data.json + data.js in place (build_data.py can't be rerun once data is v2, so site additions
live here). Re-run after anything that regenerates plant assignments. Stdlib only. Never touches HubSpot.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
NILES_LAT, NILES_LON = (41.1808345, -80.7653797)
SITES = [dict(id="arc:Chandler", name="Chandler", label="Chandler, AZ", city="Chandler",
              region="Chandler, Maricopa County, Arizona, USA", lat=33.3062031, lon=-111.8411850,
              hint="Chandler, AZ \u2014 manual override (Steve, 2026-10-15), not inferred from area code")]
# Extra companies. This script never creates HubSpot records; it only mirrors records Steve/Simran supplied.
BRT_ID = "3005488807"
COMPANIES = [dict(name="BRT Extrusions", id=BRT_ID, am="Simran Subramanian", url="https://app.hubspot.com/contacts/6029765/record/0-2/" + BRT_ID, industry="Aluminum extrusion (Niles, OH)")]
SITES.append(dict(id="brt:Niles", name="Niles", label="Niles, OH (BRT Extrusions)", city="Niles",
                  region="Niles, Trumbull County, Ohio, USA", lat=NILES_LAT, lon=NILES_LON, company="BRT Extrusions",
                  hint="BRT Extrusions, 1818 N. Main St., Niles, OH \u2014 added by request (Steve, 2026-10-15)"))
POC_NOTE = "Primary POC per Simran 9/11 note; do not flood others with emails"
_N = "BRT Extrusions"
# (name, hubspot id, title, phone, email, extra note)
BRT_CONTACTS = [
    ("Amanda Zepernick", "228516628092", "Production Planner", "330-544-0244 ext. 149", "a.zepernick@brtextrusions.com", POC_NOTE),
    ("Atasha Lyons", "228516624518", "Customer Service Representative", "330-544-0244 ext. 116", "a.lyons@brtextrusions.com", ""),
    ("Rachel Hallett", "47978051", "Packing Supervisor", "(330) 544-0244", "r.hallett@brtextrusions.com", ""),
    ("Charles Weaver", "47977951", "Supervisor, Operations", "(330) 544-0244", "c.weaver@brtextrusions.com", ""),
    ("Adriana Troutman", "24394101", "", "(330) 544-0244", "a.troutman@brtextruisons.com", "Email domain looks misspelled (brtextruisons.com) in HubSpot; kept as is"),
    ("Rich Spisak", "24197701", "", "(330) 554-0244", "r.spisak@brtextrusions.com", ""),
    ("Craig Muntean", "23776501", "", "(330) 531-0903", "c.muntean@brtextrusions.com", ""),
    ("Jesse Williams", "23553551", "", "(330) 544-0244", "j.williams@brtextrusions.com", ""),
    ("Jessie Hughes", "8013351", "", "(330) 544-0244", "j.hughes@brtextrusions.com", ""),
]
OVERRIDES = {"37695051": "arc:Chandler"}   # Kevin West (602 = Phoenix AC, assigned to Chandler by request)
JS = "window.__DIALER_DATA__ = "

def apply(d):
    locs, cs = d["locations"], d["contacts"]
    arc = next(l for l in locs if l["id"] == "arc:all")
    for co in COMPANIES:
        if not any(c["name"] == co["name"] for c in d["companies"]):
            d["companies"].append(dict(co))
        d["stats"]["by_company"].setdefault(co["name"], {"contacts": 0, "with_phone": 0, "pins": 0, "supplier_pins": 0})
    for co in COMPANIES:   # keep id/url of already-present companies current
        cur = next(c for c in d["companies"] if c["name"] == co["name"]); cur.update(id=co["id"], url=co["url"])
    cmeta = {c["name"]: c for c in d["companies"]}
    for l in locs:
        if l["company"] in cmeta and l["company"] in {c["name"] for c in COMPANIES}:
            l.update(company_id=cmeta[l["company"]]["id"], company_url=cmeta[l["company"]]["url"], show_company_link=True)
    have = {str(c.get("hubspot_contact_id")) for c in cs}
    bm = cmeta[_N]
    for name, hid, title, phone, email, note in BRT_CONTACTS:
        if hid in have:
            continue
        cs.append({"name": name, "role": "Other", "title": title, "phone": phone, "mobile": "", "email": email,
                   "hubspot_url": "https://app.hubspot.com/contacts/6029765/record/0-1/" + hid, "company_url": bm["url"],
                   "last_activity": "", "notes": note, "am": bm["am"], "company": _N, "plant": "Niles",
                   "area_code": "".join(ch for ch in phone if ch.isdigit())[:3], "has_phone": True, "is_dm": False,
                   "company_id": bm["id"], "plant_id": "brt:Niles", "hubspot_contact_id": hid, "hubspot_link_type": "record",
                   "times_contacted": 0, "sales_activities": 0, "last_contacted": None,
                   **({"primary_poc": True} if note == POC_NOTE else {})})
    for s in SITES:
        if any(l["id"] == s["id"] for l in locs):
            continue
        co = s.get("company", "Arconic"); m = cmeta[co]
        l = dict({k: v for k, v in s.items()}, am=m["am"], company=co, company_id=m["id"], company_url=m.get("url", ""),
                 filter=s["id"], pin=True, source="nominatim", contact_count=0, with_phone=0, dm_count=0)
        idx = [i for i, x in enumerate(locs) if x["company"] == co and x.get("pin") and x.get("kind") != "supplier"]
        locs.insert(idx[-1] + 1 if idx else len(locs), l)
    for c in cs:
        pid = OVERRIDES.get(str(c.get("hubspot_contact_id")))
        if pid:
            c["plant_id"] = pid; c["plant"] = pid.split(":", 1)[1]; c["plant_override"] = True
    sids = {s["id"] for s in SITES}
    for l in locs:
        if l["id"] in sids or l["id"] == "arc:unassigned":
            m = [c for c in cs if c["company"] == l["company"] and (c["plant_id"] == l["id"] if l["id"] != "arc:unassigned" else not c["plant"])]
            l.update(contact_count=len(m), with_phone=sum(c["has_phone"] for c in m), dm_count=sum(c["is_dm"] for c in m))
    st = d["stats"]
    st["contacts"] = len(cs); st["with_phone"] = sum(1 for c in cs if c["has_phone"])
    st["decision_makers"] = sum(1 for c in cs if c["is_dm"])
    st["hubspot_links"]["record"] = sum(1 for c in cs if c.get("hubspot_link_type") == "record")
    for name, v in st["by_company"].items():
        m = [c for c in cs if c["company"] == name]; v["contacts"] = len(m); v["with_phone"] = sum(1 for c in m if c["has_phone"])
    st["plant_assigned"] = sum(1 for c in cs if c["plant"])
    st["pins"] = sum(1 for l in locs if l.get("pin"))
    for name, v in st["by_company"].items():
        v["pins"] = sum(1 for l in locs if l.get("pin") and l["company"] == name)
    return d

if __name__ == "__main__":
    p = os.path.join(HERE, "data.json")
    d = apply(json.load(open(p)))
    s = json.dumps(d, indent=2, ensure_ascii=False)
    if "--check" in sys.argv:
        sys.exit(0 if s + "\n" == open(p).read() else 1)
    open(p, "w").write(s + "\n"); open(os.path.join(HERE, "data.js"), "w").write(JS + s + ";\n")
    print("ok", d["stats"]["pins"], "pins")
