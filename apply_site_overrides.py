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
# Kaiser Richmond (Bellwood), VA pin (Simran). Contacts are attached ONLY when their phone/mobile area code is 804 and they
# have no plant yet; none exist today, so the pin starts empty. No contacts are invented.
SITES.append(dict(id="kai:Richmond", name="Richmond (Bellwood)", label="Richmond (Bellwood), VA", city="Richmond",
                  region="Richmond, Virginia, USA", lat=37.5385087, lon=-77.4342800, company="Kaiser Aluminum",
                  hint="Richmond (Bellwood), VA \u2014 added by request (Steve, 2026-10-15); contacts only by 804 area code"))
AC_OVERRIDES = {("Kaiser Aluminum", "804"): "kai:Richmond"}

# ---- Reliable Silver (Kahekili): HubSpot company "Reliable" 7228584362 (domain reliablesilver.com, 203-574 = Naugatuck, CT).
# Names derived from the email where the CSV name field was an email. Notes are kept as flags (shared mailbox / Circle internal).
RELIABLE_ID = "7228584362"
COMPANIES.append(dict(name="Reliable Silver", id=RELIABLE_ID, am="Kahekili Barrozo",
                      url="https://app.hubspot.com/contacts/6029765/record/0-2/" + RELIABLE_ID, industry="Mining & Metals"))
SITES.append(dict(id="rel:Naugatuck", name="Naugatuck", label="Naugatuck, CT (Reliable Silver)", city="Naugatuck",
                  region="Naugatuck, New Haven County, Connecticut, USA", lat=41.4907561, lon=-73.0556562, company="Reliable Silver",
                  hint="Reliable Silver, Naugatuck, CT (203) \u2014 added by request (Steve, 2026-10-15)"))
ANCHOR = {"Reliable Silver": "how:unassigned"}   # place the new group after Howmet in the list
RELIABLE_CONTACTS = [
    ("Aidan Lewis", "162400325533", "", "203-574-7732 ext. 171", "aidan@reliablesilver.com", "Title not scraped"),
    ("Leah Askue", "9449901", "", "203-574-7732 ext. 108", "leah@reliablesilver.com", "Title not scraped"),
    ("Alex Oliveira", "8856951", "", "203-574-7732 ext. 113", "alex@reliablesilver.com", "Title not scraped"),
    ("Arnold Seapan", "18690551", "", "", "arnold@reliablesilver.com", "Title not scraped"),
    ("Sean Newcomb", "18690401", "", "", "sean@reliablesilver.com", "Title not scraped"),
    ("Sales", "33324551", "", "", "sales@reliablesilver.com", "Shared/generic mailbox"),
    ("Kathryn Raponi", "25869101", "", "260-264-6592", "kathryn.raponi@circledelivers.com", "Circle internal user - exclude from dialing"),
]

# ---- Howmet Aerospace (Kahekili). Contacts come from howmet_contacts.json (build_howmet_contacts.py); plants are ONLY
# area codes that actually appear >= 6 times in that data (city-level pins for the area code, not confirmed facilities);
# 412/724 -> Pittsburgh HQ pin; everything else stays Unassigned.
HOWMET_ID = "32027566669"
COMPANIES.append(dict(name="Howmet Aerospace", id=HOWMET_ID, am="Kahekili Barrozo",
                      url="https://app.hubspot.com/contacts/6029765/record/0-2/" + HOWMET_ID, industry="Aerospace"))
HOWMET_SITES = [  # key, label, city, region, lat, lon, area codes, hint
    ("HQ Pittsburgh", "Pittsburgh (HQ)", "Pittsburgh", "Pittsburgh, Pennsylvania, USA", 40.4469, -80.0090, ["412", "724"],
     "Corporate / W PA (412, 724) \u2014 inferred from phone area code"),
    ("Cleveland", "Cleveland, OH area (216)", "Cleveland", "Cleveland, Ohio, USA", 41.4996574, -81.6936772, ["216"],
     "Cleveland, OH area (216) \u2014 inferred from phone area code, not a confirmed plant"),
    ("Hammond", "NW Indiana (219)", "Hammond", "Hammond, Lake County, Indiana, USA", 41.6173959, -87.5220108, ["219"],
     "NW Indiana (219) \u2014 inferred from phone area code, not a confirmed plant"),
    ("Rochester", "Rochester, NY area (585)", "Rochester", "Rochester, Monroe County, New York, USA", 43.1572850, -77.6152140, ["585"],
     "Rochester, NY area (585) \u2014 inferred from phone area code, not a confirmed plant"),
    ("Muskegon", "Muskegon, MI area (231)", "Muskegon", "Muskegon, Muskegon County, Michigan, USA", 43.2341813, -86.2483921, ["231"],
     "W Michigan (231) \u2014 inferred from phone area code, not a confirmed plant"),
    # Tucson: added by request (Steve 2026-10-15); no area-code rule (acs empty), contacts attached only via OVERRIDES below.
    ("Tucson", "Tucson, AZ", "Tucson", "Tucson, Pima County, Arizona, United States", 32.2228765, -110.9748470, [],
     "Tucson, AZ \u2014 plant added by request; contacts assigned explicitly"),
]
OVERRIDES = {"37695051": "arc:Chandler",
             "3192251": "how:Tucson",   # John Fox (Howmet, 520)
             "4526951": "how:Tucson",   # Miguel Angulo (Howmet, no phone AC)
             "6825251": "kai:Richmond"}   # Pilar Alvarez (Kaiser, 949 AC) belongs to Richmond (Bellwood), VA per Steve 2026-10-15   # Kevin West (602 = Phoenix AC, assigned to Chandler by request)
JS = "window.__DIALER_DATA__ = "

# ---- Kawneer (Simran): HubSpot company 8178764938, 21 contacts from kili_contacts.csv (kawneer_contacts.json via build_howmet_contacts.py <csv> kawneer).
# Pins only where justified: area code 770 appears on 11 of 21 contacts (770-449-5555, Kawneer's Norcross, GA HQ main line).
# Everything else (other ACs, <=3 contacts each) stays Unassigned. Notes (e.g. Circle internal users) are kept as-is.
KAWNEER_ID = "8178764938"
COMPANIES.append(dict(name="Kawneer", id=KAWNEER_ID, am="Simran Subramanian",
                      url="https://app.hubspot.com/contacts/6029765/record/0-2/" + KAWNEER_ID, industry="Building Products"))
KAWNEER_SITES = [("Norcross", "Norcross, GA (HQ area, 770)", "Norcross", "Norcross, Gwinnett County, Georgia, United States", 33.9412127, -84.2135309,
                  ["770"], "Norcross, GA (770-449-5555 main line) \u2014 inferred from phone area code")]


def apply_kawneer(d):
    locs, cs = d["locations"], d["contacts"]
    co = next(c for c in COMPANIES if c["name"] == "Kawneer")
    base = dict(am=co["am"], company=co["name"], company_id=co["id"], company_url=co["url"], show_company_link=True)
    try:
        kc = json.load(open(os.path.join(HERE, "kawneer_contacts.json")))
    except OSError:
        kc = []
    ac2 = {ac: "kaw:" + k for k, _l, _c, _r, _a, _o, acs, _h in KAWNEER_SITES for ac in acs}
    have = {str(c.get("hubspot_contact_id")) for c in cs}
    for h in kc:
        if h["hubspot_contact_id"] in have:
            continue
        pid = ac2.get(h.get("area_code") or "")
        cs.append({"name": h["name"], "role": "Decision Maker" if h["is_dm"] else "Other", "title": h["title"], "phone": h["phone"],
                   "mobile": h["mobile"], "email": h["email"], "hubspot_url": "https://app.hubspot.com/contacts/6029765/record/0-1/" + h["hubspot_contact_id"],
                   "company_url": co["url"], "last_activity": "", "notes": h["notes"], "am": co["am"], "company": co["name"],
                   "plant": pid.split(":", 1)[1] if pid else None, "area_code": h.get("area_code"), "has_phone": bool(h["phone"] or h["mobile"]),
                   "is_dm": h["is_dm"], "company_id": co["id"], "plant_id": pid, "hubspot_contact_id": h["hubspot_contact_id"],
                   "hubspot_link_type": "record", "times_contacted": 0, "sales_activities": 0, "last_contacted": None})
    want = [dict(id="kaw:all", name="All Kawneer", label="All Kawneer (full list)", city=None, region=None, lat=None, lon=None, filter="all", pin=False,
                 hint="Full dialer list \u2014 not plant-filtered", **base)]
    for k, label, city, region, lat, lon, _acs, hint in KAWNEER_SITES:
        want.append(dict(id="kaw:" + k, name=k, label=label, city=city, region=region, lat=lat, lon=lon, filter="kaw:" + k, pin=True,
                         source="nominatim", hint=hint, **base))
    # Kawneer corporate office, Newnan GA (added by request). Paul Laslou is an ARCONIC decision maker (Kili): he is NOT moved; the pin
    # cross-references him by HubSpot id (contact_ids + cross_company), like supplier pins do, so he shows at Newnan and stays in Arconic.
    want.append(dict(id="kaw:Newnan", name="Newnan", label="Kawneer corporate office", city="Newnan",
                     region="Newnan, Coweta County, Georgia, United States", lat=33.3806716, lon=-84.7996573, filter="kaw:Newnan", pin=True,
                     source="nominatim",
                     hint="Kawneer corporate office, Newnan, GA \u2014 added by request", **base))
    want.append(dict(id="kaw:unassigned", name="Unassigned / other", label="Kawneer \u00b7 Unassigned / other ACs", city=None, region=None,
                     lat=None, lon=None, filter="unassigned", pin=False, hint="No phone or area code not mapped to a pin", **base))
    existing = {l["id"]: l for l in locs}
    for w in want:   # Newnan was first a cross-reference pin; now a normal pin (replace in place)
        if w["id"] == "kaw:Newnan" and w["id"] in existing:
            locs[locs.index(existing[w["id"]])] = w; existing[w["id"]] = w
    new = [w for w in want if w["id"] not in existing]
    if new:
        un = next((i for i, x in enumerate(locs) if x["id"] == "kaw:unassigned"), None)
        if un is not None:
            pins_new = [w for w in new if w.get("pin")]
            locs[un:un] = pins_new; new = [w for w in new if w not in pins_new]
        at = max(i for i, x in enumerate(locs) if x["id"].startswith("brt:")) + 1
        locs[at:at] = new
    for l in locs:
        if l["company"] == "Kawneer" and l.get("cross_company"):
            m = [c for c in cs if str(c["hubspot_contact_id"]) in l["contact_ids"]]
            l.update(company_id=co["id"], company_url=co["url"], show_company_link=True,
                     contact_count=len(m), with_phone=sum(1 for c in m if c["has_phone"]), dm_count=sum(1 for c in m if c["is_dm"]))
        elif l["company"] == "Kawneer":
            m = [c for c in cs if c["company"] == "Kawneer" and (True if l["id"] == "kaw:all" else (not c["plant"]) if l["id"].endswith(":unassigned") else c["plant_id"] == l["id"])]
            l.update(company_id=co["id"], company_url=co["url"], show_company_link=True,
                     contact_count=len(m), with_phone=sum(1 for c in m if c["has_phone"]), dm_count=sum(1 for c in m if c["is_dm"]))
    cmeta = next((c for c in d["companies"] if c["name"] == "Kawneer"), None)
    if cmeta is None:
        d["companies"].append(dict(co))
    d["stats"]["by_company"].setdefault("Kawneer", {"contacts": 0, "with_phone": 0, "pins": 0, "supplier_pins": 0})


def apply_howmet(d):
    locs, cs = d["locations"], d["contacts"]
    co = next(c for c in COMPANIES if c["name"] == "Howmet Aerospace")
    base = dict(am=co["am"], company=co["name"], company_id=co["id"], company_url=co["url"], show_company_link=True)
    try:
        hm = json.load(open(os.path.join(HERE, "howmet_contacts.json")))
    except OSError:
        hm = []
    ac2site = {ac: "how:" + k for k, _l, _c, _r, _a, _o, acs, _h in HOWMET_SITES for ac in acs}
    have = {str(c.get("hubspot_contact_id")) for c in cs}
    for h in hm:
        if h["hubspot_contact_id"] in have:   # already on the map (e.g. under Arconic): never duplicate / move
            continue
        pid = ac2site.get(h.get("area_code") or "")
        cs.append({"name": h["name"], "role": "Decision Maker" if h["is_dm"] else "Other", "title": h["title"], "phone": h["phone"],
                   "mobile": h["mobile"], "email": h["email"], "hubspot_url": "https://app.hubspot.com/contacts/6029765/record/0-1/" + h["hubspot_contact_id"],
                   "company_url": co["url"], "last_activity": "", "notes": h["notes"], "am": co["am"], "company": co["name"],
                   "plant": pid.split(":", 1)[1] if pid else None, "area_code": h.get("area_code"), "has_phone": bool(h["phone"] or h["mobile"]),
                   "is_dm": h["is_dm"], "company_id": co["id"], "plant_id": pid, "hubspot_contact_id": h["hubspot_contact_id"],
                   "hubspot_link_type": "record", "times_contacted": 0, "sales_activities": 0, "last_contacted": None})
    want = [dict(id="how:all", name="All Howmet", label="All Howmet (full list)", city="Pittsburgh", region="Pittsburgh, Pennsylvania, USA",
                 lat=None, lon=None, filter="all", pin=False, hint="Full dialer list \u2014 not plant-filtered", **base)]
    for k, label, city, region, lat, lon, _acs, hint in HOWMET_SITES:
        want.append(dict(id="how:" + k, name=k, label=label, city=city, region=region, lat=lat, lon=lon, filter="how:" + k, pin=True,
                         source="nominatim", hint=hint, **base))
    want.append(dict(id="how:unassigned", name="Unassigned / other", label="Howmet \u00b7 Unassigned / other ACs", city=None, region=None,
                     lat=None, lon=None, filter="unassigned", pin=False, hint="No phone or area code not mapped to a pin", **base))
    existing = {l["id"]: l for l in locs}
    new = [w for w in want if w["id"] not in existing]
    if new:
        at = max(i for i, x in enumerate(locs) if x["id"] == "arc:unassigned") + 1
        un = next((i for i, x in enumerate(locs) if x["id"] == "how:unassigned"), None)
        pins_new = [w for w in new if w.get("pin")] if un is not None else []
        if pins_new:
            locs[un:un] = pins_new; new = [w for w in new if w not in pins_new]
        locs[at:at] = new
    for l in locs:
        if l["company"] != "Howmet Aerospace":
            continue
        m = [c for c in cs if c["company"] == l["company"] and (l["filter"] == "all" or (not c["plant"] if l["filter"] == "unassigned" else c["plant_id"] == l["id"]))]
        l.update(contact_count=len(m), with_phone=sum(1 for c in m if c["has_phone"]), dm_count=sum(1 for c in m if c["is_dm"]), **{k: base[k] for k in ("company_id", "company_url", "show_company_link")})
    d["stats"]["by_company"].setdefault(co["name"], {"contacts": 0, "with_phone": 0, "pins": 0, "supplier_pins": 0})


# Howmet SUPPLIER-style pins (square marker, like the Arconic supplier pins). Not Howmet facilities. They hold NO contacts of
# their own: contact_ids reference existing Howmet contacts whose phone area code is in `acs` (explicit rule, Steve 2026-10-15).
# Laredo (956) has no matching contacts today, so it stays empty. Nothing is invented.
HOWMET_SUPPLIERS = [
    dict(id="how:sup:Mogadore", name="Mogadore, OH (supplier)", label="Mogadore, OH \u00b7 Supplier (Howmet-managed)", city="Mogadore",
         region="Mogadore, Summit County, Ohio, USA", lat=41.0507750, lon=-81.3939460, acs=["330", "234"],
         hint="Supplier (Howmet-managed), not a Howmet facility \u00b7 contacts with 330/234 phone area codes"),
    dict(id="how:sup:Laredo", name="Laredo, TX (supplier)", label="Laredo, TX \u00b7 Supplier (Howmet-managed)", city="Laredo",
         region="Laredo, Webb County, Texas, United States", lat=27.5079211, lon=-99.5069834, acs=["956"],
         hint="Supplier (Howmet-managed), not a Howmet facility \u00b7 contacts with 956 phone area codes (none yet)"),
]


def apply_howmet_suppliers(d):
    locs, cs = d["locations"], d["contacts"]
    how = next(l for l in locs if l["id"] == "how:all")
    base = {k: how[k] for k in ("am", "company", "company_id", "company_url", "show_company_link")}
    for sp in HOWMET_SUPPLIERS:
        ids = [str(c["hubspot_contact_id"]) for c in cs if c["company"] == base["company"] and c.get("area_code") in sp["acs"]]
        m = [c for c in cs if str(c["hubspot_contact_id"]) in ids]
        loc = dict(id=sp["id"], name=sp["name"], label=sp["label"], city=sp["city"], region=sp["region"], lat=sp["lat"], lon=sp["lon"], **base,
                   contact_count=len(m), with_phone=sum(1 for c in m if c["has_phone"]), dm_count=sum(1 for c in m if c["is_dm"]),
                   filter=sp["id"], hint=sp["hint"], pin=True, source="nominatim", kind="supplier", supplier_tag="Supplier (Howmet-managed)",
                   managed_by="Howmet", is_company_facility=False, contacts_from=[], contact_ids=ids)
        cur = next((i for i, l in enumerate(locs) if l["id"] == sp["id"]), None)
        if cur is not None:
            locs[cur] = loc
        else:
            at = next(i for i, l in enumerate(locs) if l["id"] == "how:unassigned")
            locs.insert(at, loc)


def move_paul(d):
    """Paul Laslou (21373851): FULL move Arconic/Kili -> Kawneer/Simran at the Newnan corporate-office pin (Steve, 2026-10-15), title from his
    email signature. Signature address 555 Guthridge Ct, Norcross GA matches the Norcross pin: to use it instead set PAUL_PIN = "kaw:Norcross".
    HubSpot link and decision-maker flag are kept. Runs first so Arconic counts are recomputed below."""
    co = next(c for c in COMPANIES if c["name"] == "Kawneer")
    for c in d["contacts"]:
        if str(c.get("hubspot_contact_id")) == "21373851":
            c.update(company=co["name"], am=co["am"], company_id=co["id"], company_url=co["url"], plant=PAUL_PIN.split(":", 1)[1], plant_id=PAUL_PIN,
                     title="Logistics / Supply Chain Analyst", title_source="from email signature", plant_override=True)


PAUL_PIN = "kaw:Newnan"


def apply(d):
    locs, cs = d["locations"], d["contacts"]
    move_paul(d)
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
        anchor = [i for i, x in enumerate(locs) if x["id"] == ANCHOR.get(co)]
        locs.insert(idx[-1] + 1 if idx else (anchor[0] + 1 if anchor else len(locs)), l)
    for c in cs:
        pid = OVERRIDES.get(str(c.get("hubspot_contact_id")))
        if pid:
            c["plant_id"] = pid; c["plant"] = pid.split(":", 1)[1]; c["plant_override"] = True
    import re
    def _ac(p):
        x = re.sub(r"\D", "", re.split(r"(?i)ext|x", p or "")[0])
        x = x[1:] if len(x) == 11 and x[0] == "1" else x
        return x[:3] if len(x) == 10 else ""
    for c in cs:
        for (co, ac), pid in AC_OVERRIDES.items():
            if c["company"] == co and not c.get("plant") and ac in (_ac(c.get("phone")), _ac(c.get("mobile"))):
                c["plant_id"] = pid; c["plant"] = pid.split(":", 1)[1]; c["plant_override"] = True
    sids = {s["id"] for s in SITES}
    for l in locs:
        if l["id"] in sids or l["id"] in ("arc:unassigned", "kai:unassigned") or (l.get("pin") and l.get("kind") != "supplier" and l.get("filter") == l["id"] and l["company"] in ("Arconic", "Kaiser Aluminum")):
            m = [c for c in cs if c["company"] == l["company"] and (c["plant_id"] == l["id"] if not l["id"].endswith(":unassigned") else not c["plant"])]
            l.update(contact_count=len(m), with_phone=sum(c["has_phone"] for c in m), dm_count=sum(c["is_dm"] for c in m))
    for l in locs:   # (again, after new pins were inserted) so a first run converges immediately
        if l["company"] in {c["name"] for c in COMPANIES}:
            l.update(company_id=cmeta[l["company"]]["id"], company_url=cmeta[l["company"]]["url"], show_company_link=True)
    rm = cmeta["Reliable Silver"]
    for name, hid, title, phone, email, note in RELIABLE_CONTACTS:
        if hid in have:
            continue
        cs.append({"name": name, "role": "Other", "title": title, "phone": phone, "mobile": "", "email": email,
                   "hubspot_url": "https://app.hubspot.com/contacts/6029765/record/0-1/" + hid, "company_url": rm["url"],
                   "last_activity": "", "notes": note, "am": rm["am"], "company": "Reliable Silver", "plant": "Naugatuck",
                   "area_code": ("".join(ch for ch in phone if ch.isdigit())[:3] or None), "has_phone": bool(phone), "is_dm": False,
                   "company_id": rm["id"], "plant_id": "rel:Naugatuck", "hubspot_contact_id": hid, "hubspot_link_type": "record",
                   "times_contacted": 0, "sales_activities": 0, "last_contacted": None})
    sids2 = {"rel:Naugatuck"}
    for l in locs:
        if l["id"] in sids2:
            m = [c for c in cs if c["plant_id"] == l["id"]]
            l.update(contact_count=len(m), with_phone=sum(1 for c in m if c["has_phone"]), dm_count=0)
    apply_howmet(d)
    apply_howmet_suppliers(d)
    apply_kawneer(d)
    st = d["stats"]
    st["contacts"] = len(cs); st["with_phone"] = sum(1 for c in cs if c["has_phone"])
    st["decision_makers"] = sum(1 for c in cs if c["is_dm"])
    st["hubspot_links"]["record"] = sum(1 for c in cs if c.get("hubspot_link_type") == "record")
    for name, v in st["by_company"].items():
        m = [c for c in cs if c["company"] == name]; v["contacts"] = len(m); v["with_phone"] = sum(1 for c in m if c["has_phone"])
    st["plant_assigned"] = sum(1 for c in cs if c["plant"])
    st["pins"] = sum(1 for l in locs if l.get("pin"))
    st["supplier_pins"] = sum(1 for l in locs if l.get("kind") == "supplier")
    for name, v in st["by_company"].items():
        v["pins"] = sum(1 for l in locs if l.get("pin") and l["company"] == name)
        v["supplier_pins"] = sum(1 for l in locs if l.get("kind") == "supplier" and l.get("company") == name)
    for l in locs:   # "All <company>" entries follow the (possibly moved) contacts
        if l.get("filter") == "all" and l.get("company"):
            m = [c for c in cs if c["company"] == l["company"]]
            l.update(contact_count=len(m), with_phone=sum(1 for c in m if c["has_phone"]), dm_count=sum(1 for c in m if c["is_dm"]))
    return d

if __name__ == "__main__":
    p = os.path.join(HERE, "data.json")
    d = apply(json.load(open(p)))
    s = json.dumps(d, indent=2, ensure_ascii=False)
    if "--check" in sys.argv:
        sys.exit(0 if s + "\n" == open(p).read() else 1)
    open(p, "w").write(s + "\n"); open(os.path.join(HERE, "data.js"), "w").write(JS + s + ";\n")
    print("ok", d["stats"]["pins"], "pins")
