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
# Extra companies (no HubSpot company id on file: left blank, no company_url). Pins only; contacts get attached by
# OVERRIDES / sync once real HubSpot contact ids exist (this script never creates HubSpot records).
COMPANIES = [dict(name="BRT Extrusions", id="", am="Simran Subramanian", url="", industry="Aluminum extrusion (Niles, OH)")]
SITES.append(dict(id="brt:Niles", name="Niles", label="Niles, OH (BRT Extrusions)", city="Niles",
                  region="Niles, Trumbull County, Ohio, USA", lat=NILES_LAT, lon=NILES_LON, company="BRT Extrusions",
                  hint="BRT Extrusions, 1818 N. Main St., Niles, OH \u2014 added by request (Steve, 2026-10-15)"))
OVERRIDES = {"37695051": "arc:Chandler"}   # Kevin West (602 = Phoenix AC, assigned to Chandler by request)
JS = "window.__DIALER_DATA__ = "

def apply(d):
    locs, cs = d["locations"], d["contacts"]
    arc = next(l for l in locs if l["id"] == "arc:all")
    for co in COMPANIES:
        if not any(c["name"] == co["name"] for c in d["companies"]):
            d["companies"].append(dict(co))
        d["stats"]["by_company"].setdefault(co["name"], {"contacts": 0, "with_phone": 0, "pins": 0, "supplier_pins": 0})
    cmeta = {c["name"]: c for c in d["companies"]}
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
