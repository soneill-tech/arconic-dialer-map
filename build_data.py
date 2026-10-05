#!/usr/bin/env python3
"""Rebuild data.json / data.js: Arconic (Kahekili, existing pins kept) + Kaiser Aluminum (Simran)."""
import csv, json, re, os
from collections import OrderedDict
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
old = json.load(open(os.path.join(HERE, "data.json")))
geo = json.load(open(os.path.join(HERE, "geocodes.json")))

ARC = {"name": "Arconic", "id": "2359249037", "am": "Kahekili Barrozo",
       "url": "https://app.hubspot.com/contacts/6029765/record/0-2/2359249037"}
KAI = {"name": "Kaiser Aluminum", "id": "5360206404", "am": "Simran Subramanian",
       "url": "https://app.hubspot.com/contacts/6029765/record/0-2/5360206404"}

# ---- Arconic: reuse already-built contacts & locations (pins unchanged), but namespace ids
if old.get("version") == 2:
    raise SystemExit("data.json already v2; rebuild from git history instead")
arc_contacts, arc_locs = [], []
for c in old["contacts"]:
    c = dict(c); c["company"] = "Arconic"; c["company_id"] = ARC["id"]
    c["plant_id"] = ("arc:" + c["plant"]) if c["plant"] else None
    arc_contacts.append(c)
for l in old["locations"]:
    l = dict(l)
    if l["id"] == "all":
        l.update(id="arc:all", filter="all", label="All Arconic (full list)", name="All Arconic")
    elif l["id"] == "unassigned":
        l.update(id="arc:unassigned", filter="unassigned", label="Arconic · Unassigned / other ACs")
    else:
        l["filter"] = l["id"] = "arc:" + l["id"]
    l["company"] = "Arconic"; l["company_id"] = ARC["id"]; l["am"] = ARC["am"]
    arc_locs.append(l)

# ---- Kaiser: area code -> known Kaiser Aluminum site (best effort)
KSITES = OrderedDict([
    ("Trentwood Works", dict(acs=["509"], city="Spokane Valley", region="Spokane Valley, Washington, USA", label="Trentwood Works (Spokane Valley, WA)", hint="Spokane, WA (509) — inferred from phone area code")),
    ("Warrick", dict(acs=["812"], city="Newburgh", region="Newburgh, Indiana, USA", label="Warrick (Newburgh / Evansville, IN)", hint="Evansville/Newburgh, IN (812) — inferred from phone area code")),
    ("Knoxville", dict(acs=["865"], city="Knoxville", region="Knoxville, Tennessee, USA", label="Knoxville, TN", hint="Knoxville, TN (865) — inferred from phone area code")),
    ("Franklin HQ", dict(acs=["615"], city="Franklin", region="Franklin, Tennessee, USA", label="Franklin, TN HQ (Nashville area)", hint="Corporate HQ / Nashville area (615) — inferred from phone area code")),
    ("Tucson", dict(acs=["520"], city="Tucson", region="Tucson, Arizona, USA", label="Tucson, AZ", hint="Southern AZ (520) — inferred from phone area code")),
    ("Newark Works", dict(acs=["740"], city="Heath", region="Heath, Ohio, USA", label="Newark Works (Heath, OH)", hint="Newark/Heath, OH (740) — inferred from phone area code")),
    ("Jackson", dict(acs=["731"], city="Jackson", region="Jackson, Tennessee, USA", label="Jackson, TN", hint="Jackson, TN (731) — inferred from phone area code")),
    ("Foothill Ranch", dict(acs=["949"], city="Foothill Ranch", region="Foothill Ranch, California, USA", label="Foothill Ranch, CA (former HQ)", hint="Orange County, CA (949) — inferred from phone area code")),
    ("Kalamazoo", dict(acs=["269"], city="Kalamazoo", region="Kalamazoo, Michigan, USA", label="Kalamazoo, MI", hint="Kalamazoo, MI (269) — inferred from phone area code")),
])
KGEO = {  # Nominatim city-level results (fetched 2026-10-05)
    "Trentwood Works": (47.6571104, -117.2613936), "Warrick": (37.9456824, -87.4046571),
    "Knoxville": (35.9603948, -83.9210261), "Franklin HQ": (35.9252060, -86.8689419),
    "Tucson": (32.2228765, -110.9748470), "Newark Works": (40.0228421, -82.4445991),
    "Jackson": (35.6144446, -88.8177418), "Foothill Ranch": (33.6849918, -117.6590428),
    "Kalamazoo": (42.2917070, -85.5872286),
}
ac2site = {ac: k for k, v in KSITES.items() for ac in v["acs"]}

def area_code(p):
    d = re.sub(r"\D", "", (p or "").split("ext")[0])
    if len(d) == 11 and d[0] == "1": d = d[1:]
    return d[:3] if len(d) == 10 else ""

kai_contacts = []
for r in csv.DictReader(open(os.path.join(ROOT, "Simran_Subramanian_dialer.csv"))):
    if r["Company"] != "Kaiser Aluminum": continue
    phone, mobile = r["Phone"].strip(), r["Mobile"].strip()
    ac = area_code(phone) or area_code(mobile)
    site = ac2site.get(ac)
    kai_contacts.append({
        "name": r["Contact Name"], "role": r["Role"], "title": r["Job Title"],
        "phone": phone, "mobile": mobile, "email": r["Email"],
        "hubspot_url": r["HubSpot Contact URL"], "company_url": r["HubSpot Company URL"],
        "last_activity": r["Last Activity"], "notes": r["Notes"],
        "am": KAI["am"], "company": KAI["name"], "company_id": KAI["id"],
        "plant": site, "plant_id": ("kai:" + site) if site else None,
        "area_code": ac or None, "has_phone": bool(phone or mobile),
        "is_dm": r["Role"].strip().lower() == "decision maker",
    })
kai_contacts.sort(key=lambda c: (not c["is_dm"], not c["has_phone"], c["name"].lower()))

def stats(cs):
    return dict(contact_count=len(cs), with_phone=sum(c["has_phone"] for c in cs), dm_count=sum(c["is_dm"] for c in cs))

base = dict(am=KAI["am"], company=KAI["name"], company_id=KAI["id"], company_url=KAI["url"])
kai_locs = [dict(id="kai:all", name="All Kaiser Aluminum", label="All Kaiser Aluminum (full list)", city="Franklin",
                 region="Franklin, Tennessee, USA", lat=None, lon=None, filter="all", pin=False,
                 hint="Full dialer list — not plant-filtered", **base, **stats(kai_contacts))]
for k, v in KSITES.items():
    cs = [c for c in kai_contacts if c["plant"] == k]
    if not cs: continue
    lat, lon = KGEO[k]
    geo["Kaiser · " + k] = dict(city=v["city"], region=v["region"], lat=lat, lon=lon, source="nominatim")
    kai_locs.append(dict(id="kai:" + k, name=k, label=v["label"], city=v["city"], region=v["region"], lat=lat, lon=lon,
                         filter="kai:" + k, pin=True, source="nominatim", hint=v["hint"], **base, **stats(cs)))
un = [c for c in kai_contacts if not c["plant"]]
kai_locs.append(dict(id="kai:unassigned", name="Unassigned", label="Kaiser · Unassigned / other ACs", city=None, region=None,
                     lat=None, lon=None, filter="unassigned", pin=False,
                     hint="No phone, toll-free/invalid, or area code not mapped to a known Kaiser site", **base, **stats(un)))

contacts = arc_contacts + kai_contacts
data = {
    "version": 2,
    "title": "Team Steve — Closed Won Dialer Map",
    "scope": "Arconic (HubSpot 2359249037, Kahekili Barrozo) + Kaiser Aluminum (HubSpot 5360206404, Simran Subramanian)",
    "generated": "2026-10-05",
    "companies": [dict(ARC, industry="Mining & Metals"), KAI],
    "notes": [
        "Plant pins are city-level (Nominatim). Contacts are assigned to a plant only when the phone area code matches a known site for that company; otherwise Unassigned.",
        "Sort order: Decision Maker first, then contacts with phone, then name.",
        "No HubSpot writes. Read-only dialer export.",
    ],
    "locations": arc_locs + kai_locs,
    "contacts": contacts,
    "stats": {
        "contacts": len(contacts), "with_phone": sum(c["has_phone"] for c in contacts),
        "decision_makers": sum(c["is_dm"] for c in contacts),
        "plant_assigned": sum(1 for c in contacts if c["plant"]),
        "pins": sum(1 for l in arc_locs + kai_locs if l["pin"]),
        "by_company": {
            "Arconic": {"contacts": len(arc_contacts), "with_phone": sum(c["has_phone"] for c in arc_contacts), "pins": sum(l["pin"] for l in arc_locs)},
            "Kaiser Aluminum": {"contacts": len(kai_contacts), "with_phone": sum(c["has_phone"] for c in kai_contacts), "pins": sum(l["pin"] for l in kai_locs)},
        },
    },
}
s = json.dumps(data, indent=2, ensure_ascii=False)
open(os.path.join(HERE, "data.json"), "w").write(s + "\n")
open(os.path.join(HERE, "data.js"), "w").write("window.__DIALER_DATA__ = " + s + ";\n")
json.dump(geo, open(os.path.join(HERE, "geocodes.json"), "w"), indent=2, ensure_ascii=False)
for l in kai_locs: print(l["id"], l["contact_count"], l["with_phone"])
print(data["stats"])
