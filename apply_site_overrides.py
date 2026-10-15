#!/usr/bin/env python3
"""Add real Arconic plant pins that area-code inference can't find, plus explicit contact->plant overrides.

    python3 apply_site_overrides.py [--check]

Idempotent; edits data.json + data.js in place (build_data.py can't be rerun once data is v2, so site additions
live here). Re-run after anything that regenerates plant assignments. Stdlib only. Never touches HubSpot.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SITES = [dict(id="arc:Chandler", name="Chandler", label="Chandler, AZ", city="Chandler",
              region="Chandler, Maricopa County, Arizona, USA", lat=33.3062031, lon=-111.8411850,
              hint="Chandler, AZ \u2014 manual override (Steve, 2026-10-15), not inferred from area code")]
OVERRIDES = {"37695051": "arc:Chandler"}   # Kevin West (602 = Phoenix AC, assigned to Chandler by request)
JS = "window.__DIALER_DATA__ = "

def apply(d):
    locs, cs = d["locations"], d["contacts"]
    arc = next(l for l in locs if l["id"] == "arc:all")
    for s in SITES:
        if not any(l["id"] == s["id"] for l in locs):
            l = dict(s, am=arc["am"], company=arc["company"], company_id=arc["company_id"], company_url=arc["company_url"],
                     filter=s["id"], pin=True, source="nominatim", contact_count=0, with_phone=0, dm_count=0)
            i = max(i for i, x in enumerate(locs) if x["company"] == "Arconic" and x.get("pin") and x.get("kind") != "supplier")
            locs.insert(i + 1, l)
    for c in cs:
        pid = OVERRIDES.get(str(c.get("hubspot_contact_id")))
        if pid:
            c["plant_id"] = pid; c["plant"] = pid.split(":", 1)[1]; c["plant_override"] = True
    for l in locs:
        if l["id"] in {s["id"] for s in SITES} or l["id"] == "arc:unassigned":
            m = [c for c in cs if c["company"] == "Arconic" and (c["plant_id"] == l["id"] if l["id"] != "arc:unassigned" else not c["plant"])]
            l.update(contact_count=len(m), with_phone=sum(c["has_phone"] for c in m), dm_count=sum(c["is_dm"] for c in m))
    st = d["stats"]
    st["plant_assigned"] = sum(1 for c in cs if c["plant"])
    st["pins"] = sum(1 for l in locs if l.get("pin"))
    st["by_company"]["Arconic"]["pins"] = sum(1 for l in locs if l.get("pin") and l["company"] == "Arconic")
    return d

if __name__ == "__main__":
    p = os.path.join(HERE, "data.json")
    d = apply(json.load(open(p)))
    s = json.dumps(d, indent=2, ensure_ascii=False)
    if "--check" in sys.argv:
        sys.exit(0 if s + "\n" == open(p).read() else 1)
    open(p, "w").write(s + "\n"); open(os.path.join(HERE, "data.js"), "w").write(JS + s + ";\n")
    print("ok", d["stats"]["pins"], "pins")
