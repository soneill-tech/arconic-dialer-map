#!/usr/bin/env python3
"""Load Closed Won companies / contacts / locations for the newer reps (Nick, Mia, Addie) into data.json.

Called from apply_site_overrides.apply(); also runnable alone:

    python3 rep_loader.py [--data-dir /workspace] [--no-geocode] [--retry-misses] [--check]

Inputs (HubSpot exports done by the browser agent; never written back, the map is map-only):
    <data-dir>/{nick,mia,addie}-closed-won/companies.csv
        record_id,name,domain,industry,city,state,country,street,postal_code,phone,lead_status,owner
    <data-dir>/{nick,mia,addie}-closed-won/contacts.csv   (may be missing or still growing)
        company_id,company_name,record_id,first_name,last_name,job_title,phone,mobile,email,city,state,note

Re-runnable / idempotent: every run REBUILDS all records owned by these three reps from the CSVs (companies, pins,
contacts) and leaves Kili/Simran records untouched. Per-contact touch counts already in data.json are preserved.
Geocodes are cached in rep_geocodes.json (Nominatim, 1 req/s, address -> city/state fallback); only new queries hit
the network. Bad HubSpot addresses are corrected by MANUAL below; every correction/anomaly is surfaced as a "flag"
on the pin and written to rep_load_report.json. Stdlib only.
"""
import csv, json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = "/workspace"
GEO_FILE = os.path.join(HERE, "rep_geocodes.json")
REPORT_FILE = os.path.join(HERE, "rep_load_report.json")
UA = "arconic-dialer-map/1.0 (soneill-tech; dialer map geocoder)"
HS = "https://app.hubspot.com/contacts/6029765/record/"

REPS = [  # dir, HubSpot owner (= AM), short key used by the UI / call log, id prefix, ring colour
    dict(dir="nick", am="Nicholas McNamara", short="Nick", pfx="nk", color="#22d3ee"),
    dict(dir="mia", am="Mia Medjedovic", short="Mia", pfx="mi", color="#f472b6"),
    dict(dir="addie", am="Addison Parker", short="Addie", pfx="ad", color="#a78bfa"),
]
REP_AMS = {r["am"] for r in REPS}

US = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
      "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
      "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
      "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
      "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
      "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
      "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
      "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
US_BY_NAME = {v.lower(): k for k, v in US.items()}

# ---- manual fixes for bad HubSpot addresses (keyed by HubSpot company record_id) -------------------------------
# city/state/country/street replace the CSV address for geocoding; flag is shown on the pin + report.
MANUAL = {
    "3407485758": dict(street="3560 Lenox Rd NE, Suite 2000", city="Atlanta", state="GA", country="United States", multi=True,
                       flag="HubSpot address is wrong (Kingston GA PO Box 2000, postal 600101, +91 phone). Pinned at Novelis North America HQ, Atlanta GA; contacts' own cities get separate pins."),
    "44533717843": dict(street="515 Broadhollow Road", city="Melville", state="NY", country="United States",
                        flag="HubSpot state was North Carolina (postal 28036); corrected to Melville, NY (HQ)."),
    "39256431450": dict(street="1595 Georgetown Road", city="Hudson", state="OH", country="United States",
                        flag="HubSpot address (60 Gray Rd, Falmouth AL) looks wrong; pinned at Leaf Home HQ, Hudson OH. Verify."),
    "17749711743": dict(street="1360 Post Oak Blvd, Suite 400", city="Houston", state="TX", country="United States", multi=True,
                        flag="HubSpot address is Engie France HQ (Courbevoie). Pinned at Engie North America HQ, Houston TX; US contact cities get their own pins. Verify."),
    "2359561232": dict(street="711 Kernaghan Ave", city="Winnipeg", state="Manitoba", country="Canada",
                       flag="Canadian site (Winnipeg MB) pinned as given; HubSpot phone has a US 256 area code."),
    "9427889728": dict(street="540 Frontenac Ct", city="Naperville", state="IL", country="United States",
                       flag="HubSpot state was Kentucky (postal 40507 = Lexington KY); corrected to Naperville, IL."),
    "4457033063": dict(street="3388 Pennsy Drive", city="Hyattsville", state="MD", country="United States",
                       flag="HubSpot country says Canada; Hyattsville MD (20785) is in the US. Pinned in MD. Verify."),
    "4503790566": dict(street="", city="Saint-Malo", state="Brittany", country="France",
                       flag="HubSpot address is inconsistent (city Jihlava CZ, region Brittany, postal 35400 = Saint-Malo, FR). Pinned at Saint-Malo, France."),
    "6791313242": dict(street="N Star Century Center, Chaoyang District", city="Beijing", state="", country="China", flag="International: pinned as given (Beijing, China)."),
    "18902511411": dict(street="69 Leadenhall Street", city="London", state="", country="United Kingdom", flag="International: pinned as given (London, UK)."),
    "18818235549": dict(street="", city="Gemunde, Maia", state="", country="Portugal", flag="International: pinned as given (Gemunde, Maia, Porto district, Portugal)."),
    "8975038579": dict(street="580 East Harrison Street", city="Corona", state="CA", country="United States",
                       flag="HubSpot state was Texas (postal 92879 = Corona CA); corrected to Corona, CA."),
    "30684276327": dict(street="1725 Ocean Ave", city="Raymond", state="WA", country="United States",
                        flag="HubSpot postal 98226 is Bellingham; pinned by street + city (Raymond, WA)."),
    "48493073158": dict(unassigned=True, flag="No address in HubSpot (country says France; phone is US). Unassigned."),
    "57067499058": dict(unassigned=True, flag="No address in HubSpot. Unassigned."),
    "49566176839": dict(unassigned=True, flag="No address in HubSpot. Unassigned."),
}
# Companies whose contacts get one pin per distinct contact city (in addition to the HubSpot address pin).
MULTI_CITY = {"2359245350", "57247716184", "2359254984"}   # Boart Longyear, 3M, True Manufacturing (+ Novelis/Engie via MANUAL)
MULTI_CITY_AUTO = 3                                         # ...and any company whose contacts span >= 3 distinct cities
# Extra fixed pins per company (record_id): [(key, name, geocode query, fallback lat/lon, flag)] and which contact cities feed them.
EXTRA = {
    "57247716184": dict(
        pins=[("dekalb-dkc", "3M DeKalb DC (DKC)", "1250 Macom Dr, DeKalb, IL 60115", None, "3M DeKalb Distribution Center (DKC), 1250 Macom Dr, DeKalb IL."),
              ("dekalb-dk6", "3M DeKalb DC (DK6)", "1650 Macom Dr, DeKalb, IL 60115", (41.912095, -88.73215), "3M DeKalb Distribution Center DK6, 1650 Macom Dr, DeKalb IL.")],
        cities={("dekalb", "il"): ["dekalb-dkc", "dekalb-dk6"]},
        note="Contacts whose city is DeKalb IL appear at both DC pins (HubSpot does not say which DC)."),
}
COUNTRY_CODES = {"united states": "United States", "usa": "United States", "us": "United States"}


# ---------------------------------------------------------------------------------------------------------
def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:48] or "x"


def read_csv(p):
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def state_abbr(s):
    s = (s or "").strip()
    if s.upper() in US:
        return s.upper()
    return US_BY_NAME.get(s.lower(), "")


def ncity(c):
    c = re.sub(r"[.,]", " ", (c or "").lower())
    c = re.sub(r"\bst\b", "saint", c); c = re.sub(r"\bft\b", "fort", c); c = re.sub(r"\bmt\b", "mount", c)
    return re.sub(r"\s+", " ", c).strip()


def pkey(city, state):
    return slug(f"{ncity(city)}-{state_abbr(state) or state}")


def pretty_name_from_email(e):
    local = (e or "").split("@")[0]
    parts = [p for p in re.split(r"[._\-+]+", local) if p and not p.isdigit()]
    return " ".join(p.capitalize() for p in parts) or (e or "")


# ---- geocoding (Nominatim, cached, 1 req/s) ---------------------------------------------------------------
class Geo:
    def __init__(self, enabled=True, retry_misses=False):
        self.cache = json.load(open(GEO_FILE)) if os.path.exists(GEO_FILE) else {}
        self.enabled, self.retry, self.dirty, self.last, self.errors = enabled, retry_misses, False, 0.0, 0

    def q(self, query):
        query = re.sub(r"\s+", " ", query).strip(" ,")
        hit = self.cache.get(query)
        if hit is not None and not (hit.get("miss") and self.retry and self.enabled):
            return None if hit.get("miss") else hit
        if not self.enabled:
            return None
        wait = 1.1 - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": query, "format": "json", "limit": 1, "addressdetails": 0})
        try:
            self.last = time.time()
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25))
        except Exception as e:   # network trouble is NOT cached (so a rerun retries)
            self.errors += 1
            print("  geocode error:", query, e, file=sys.stderr)
            return None
        if r:
            self.cache[query] = {"lat": round(float(r[0]["lat"]), 7), "lon": round(float(r[0]["lon"]), 7), "display": r[0].get("display_name", ""),
                                 "source": "nominatim"}
        else:
            self.cache[query] = {"miss": True}
        self.dirty = True
        return None if self.cache[query].get("miss") else self.cache[query]

    def save(self):
        if self.dirty:
            json.dump(self.cache, open(GEO_FILE, "w"), indent=1, sort_keys=True, ensure_ascii=False); open(GEO_FILE, "a").write("\n")
            self.dirty = False


def clean_street(s):
    s = re.sub(r"(?i),?\s*(ste|suite|unit|bldg|building|fl|floor|#)\.?\s*[\w-]+\s*$", "", s or "")
    return "" if re.match(r"(?i)\s*p\.?\s*o\.?\s*box", s) else s.strip(" ,")


def geocode_place(geo, street, city, state, country, postal=""):
    """Return (hit, level) trying street+city -> city only. level in address|city."""
    cn = COUNTRY_CODES.get(country.lower(), country)
    intl = cn != "United States"
    st_full = US.get(state_abbr(state), state)
    tail = ", ".join(x for x in [city, st_full, cn] if x)
    street = clean_street(street)
    tries = []
    if street:
        tries.append((", ".join(x for x in [street, city, st_full, (postal if intl else ""), cn] if x), "address"))
        tries.append((f"{street}, {tail}", "address"))
    tries.append((tail, "city"))
    seen = set()
    for qy, lvl in tries:
        if qy in seen:
            continue
        seen.add(qy)
        h = geo.q(qy)
        if h:
            return h, lvl
    return None, None


def region_str(city, state, country):
    cn = COUNTRY_CODES.get((country or "").lower(), country)
    ab = state_abbr(state)
    if cn == "United States":
        return ", ".join(x for x in [city, US.get(ab, state), "USA"] if x)
    return ", ".join(x for x in [city, cn] if x)


# ---------------------------------------------------------------------------------------------------------
def load(data_dir, geo):
    """Return (companies, locations, contacts, report) built purely from the CSVs (+ geocode cache)."""
    companies, locs, contacts = [], [], []
    report = {"generated_from": data_dir, "reps": {}, "flags": [], "contacts_skipped": [], "geocode_failures": []}
    for rep in REPS:
        base = os.path.join(data_dir, rep["dir"] + "-closed-won")
        rows = [r for r in read_csv(os.path.join(base, "companies.csv")) if r.get("record_id") and (r.get("owner") or rep["am"]) == rep["am"]]
        crows = read_csv(os.path.join(base, "contacts.csv"))
        by_id = {}
        for r in rows:
            by_id.setdefault(r["record_id"], r)       # dedupe repeated company rows
        by_name = {}
        for r in by_id.values():
            by_name.setdefault(r["name"].strip().lower(), []).append(r["record_id"])
        # --- contacts -> company
        seen_c, per_co = set(), {}
        for r in crows:
            rid = r.get("record_id", "")
            cid = r.get("company_id", "")
            if cid not in by_id:
                nm = by_name.get(r.get("company_name", "").strip().lower(), [])
                cid = nm[0] if len(nm) == 1 else ""
            if not rid or not cid:
                report["contacts_skipped"].append({"rep": rep["short"], "record_id": rid, "email": r.get("email", ""), "why": r.get("note") or "company not resolved"})
                continue
            if (cid, rid) in seen_c:   # same contact under two companies of the same rep -> one record per company
                continue
            seen_c.add((cid, rid))
            per_co.setdefault(cid, []).append(r)
        n_loc = 0
        for rid, r in sorted(by_id.items(), key=lambda kv: kv[1]["name"].lower()):
            m = MANUAL.get(rid, {})
            name = r["name"]
            pfx = f'{rep["pfx"]}-{slug(name)}'
            url = HS + "0-2/" + rid
            co = dict(name=name, id=rid, am=rep["am"], url=url, industry=r.get("industry", ""), prefix=pfx, domain=r.get("domain", "").lower(),
                      rep=rep["short"], color=rep["color"])
            if m.get("flag"):
                co["flag"] = m["flag"]
            cs = per_co.get(rid, [])
            # --- HQ / company-address pin
            street, city, state, country = (m.get("street", r["street"]) if m else r["street"], m.get("city", r["city"]) if m else r["city"],
                                            m.get("state", r["state"]) if m else r["state"], m.get("country", r["country"]) if m else r["country"])
            postal = r.get("postal_code", "")
            flags = [m["flag"]] if m.get("flag") else []
            hq = None
            if not m.get("unassigned") and city:
                hit, lvl = geocode_place(geo, street, city, state, country, postal)
                if hit:
                    hq = dict(city=city.split(",")[0].title() if city.isupper() else city.split(",")[0], state=state, country=country, hit=hit, lvl=lvl,
                              key=pkey(city.split(",")[0], state))
                else:
                    flags.append("Could not geocode the HubSpot address; contacts are Unassigned.")
                    report["geocode_failures"].append({"company": name, "city": city, "state": state, "country": country})
            elif not m.get("unassigned") and not city:
                flags.append("No address in HubSpot. Unassigned.")
            # --- contact cities
            def ckey(c):
                cc, ss = c.get("city", "").strip(), c.get("state", "").strip()
                return (ncity(cc), (state_abbr(ss) or ss).lower()) if cc else None
            cities = {}
            for c in cs:
                k = ckey(c)
                if k:
                    cities.setdefault(k, (c["city"].strip(), c.get("state", "").strip()))
            extra = EXTRA.get(rid)
            multi = bool(m.get("multi")) or rid in MULTI_CITY or len(cities) >= MULTI_CITY_AUTO
            pins = []   # dicts: key,name,lat,lon,city,region,hint
            def mkpin(key, label_loc, city_, state_, country_, hit, lvl, hint):
                return dict(key=key, loc=label_loc, city=city_, region=region_str(city_, state_, country_), lat=hit["lat"], lon=hit["lon"], lvl=lvl, hint=hint)
            if hq:
                lbl = ", ".join(x for x in [hq["city"], state_abbr(hq["state"]) or hq["state"] if hq["country"] in ("United States",) else hq["country"]] if x)
                pins.append(mkpin(hq["key"], lbl, hq["city"], hq["state"], hq["country"], hq["hit"], hq["lvl"],
                                  "HubSpot company address" + ("" if hq["lvl"] == "address" else " (city-level: street not found)")))
            hq_key = pins[0]["key"] if pins else None
            memb = {}   # contact record_id -> pin key(s)
            if extra:
                for key, pname, qy, fb, fl in extra["pins"]:
                    h = geo.q(qy) or ({"lat": fb[0], "lon": fb[1]} if fb else None)
                    if h:
                        cty = "DeKalb"; pins.append(dict(key=key, loc=pname.replace(name + " ", "") if False else pname, city=cty, region="DeKalb, Illinois, USA",
                                                         lat=h["lat"], lon=h["lon"], lvl="address", hint=fl, fixed=True))
                    else:
                        report["geocode_failures"].append({"company": name, "pin": pname})
                flags.append(extra["note"])
            if multi:
                for k, (cc, ss) in sorted(cities.items()):
                    if extra and k in extra["cities"]:
                        continue
                    if hq and k == (ncity(hq["city"]), (state_abbr(hq["state"]) or hq["state"]).lower()):
                        continue
                    ab = state_abbr(ss)
                    cn = "United States" if (ab or not ss) else ""
                    hit, lvl = geocode_place(geo, "", cc, ss, cn or "")
                    if hit:
                        pins.append(mkpin(pkey(cc, ss), f"{cc}, {ab or ss}".strip(", "), cc, ss, cn, hit, "city", "City of HubSpot contact(s) at this company"))
                    else:
                        report["geocode_failures"].append({"company": name, "contact_city": cc, "state": ss})
            if not hq and not pins:
                pass
            pin_keys = {p["key"] for p in pins}
            # --- assign contacts
            ccount = 0
            for c in cs:
                k = ckey(c)
                keys = None
                if multi and k:
                    if extra and k in extra["cities"]:
                        keys = extra["cities"][k]
                    elif hq and k == (ncity(hq["city"]), (state_abbr(hq["state"]) or hq["state"]).lower()):
                        keys = [hq_key]
                    elif pkey(c["city"], c.get("state", "")) in pin_keys:
                        keys = [pkey(c["city"], c.get("state", ""))]
                if keys is None:
                    keys = [hq_key] if hq_key else []
                keys = [x for x in keys if x in pin_keys]
                memb[c["record_id"]] = keys
            # --- location records
            def L(key, name_, label, city_, region, lat, lon, hint, pin, **kw):
                d = dict(id=f"{pfx}:{key}", name=name_, label=label, city=city_, region=region, lat=lat, lon=lon, hint=hint, am=rep["am"],
                         company=name, company_id=rid, company_url=url, filter=f"{pfx}:{key}" if pin else key, pin=pin, show_company_link=True,
                         contact_count=0, with_phone=0, dm_count=0, rep=rep["short"])
                if pin:
                    d["source"] = "nominatim"
                d.update(kw); return d
            mine = []
            for p in pins:
                hint = p["hint"] + (" · ⚠ " + " ".join(flags) if flags and p is pins[0] else "")
                lab = f"{name} · {p['loc']}"
                mine.append(L(p["key"], p["loc"], lab, p["city"], p["region"], p["lat"], p["lon"], hint, True, geo_level=p["lvl"]))
            un_ids = [c for c in cs if not memb[c["record_id"]]]
            if un_ids or not pins:
                mine.append(L("unassigned", "Unassigned", f"{name} · Unassigned", None, None, None, None,
                              ("No usable map location: " + " ".join(flags)) if flags and not pins else "Contacts without a location", False))
            if len(mine) > 1:
                mine.insert(0, L("all", f"All {name}", f"All {name} (full list)", None, None, None, None, "Full dialer list — not location-filtered", False, filter="all"))
            for x in mine:
                x.setdefault("flag", " ".join(flags)) if flags else None
            # --- contact records
            keyed = {x["id"].split(":", 1)[1]: x for x in mine}
            for c in cs:
                keys = memb[c["record_id"]]
                loc_ = keyed[keys[0]] if keys else None
                nm = " ".join(x for x in [c.get("first_name"), c.get("last_name")] if x).strip()
                note = c.get("note", "")
                if not nm:
                    nm = pretty_name_from_email(c.get("email", "")) or "(no name)"
                    note = (note + " · " if note else "") + "Name derived from email (not in HubSpot)"
                ph = c.get("phone", ""); mb = c.get("mobile", "")
                digs = re.sub(r"\D", "", re.split(r"(?i)ext|x", ph or mb or "")[0])
                digs = digs[1:] if len(digs) == 11 and digs[0] == "1" else digs
                dnc = bool(re.search(r"(?i)do\s*not\s*call|\bDNC\b", " ".join([c.get("first_name", ""), c.get("last_name", ""), c.get("job_title", ""), c.get("note", "")])))
                if dnc:
                    note = (note + " · " if note else "") + "DO NOT CALL (per HubSpot name/title/note)"
                contacts.append({"name": nm, "role": "Other", "title": c.get("job_title", ""), "phone": ph, "mobile": mb, "email": c.get("email", ""),
                                 "hubspot_url": HS + "0-1/" + c["record_id"], "company_url": url, "last_activity": "", "notes": note,
                                 "am": rep["am"], "company": name, "plant": (loc_["name"] if loc_ else None), "area_code": digs[:3] if len(digs) == 10 else None,
                                 "has_phone": bool(ph or mb), "is_dm": False, "company_id": rid, "plant_id": (loc_["id"] if loc_ else None),
                                 "hubspot_contact_id": c["record_id"], "hubspot_link_type": "record", "times_contacted": 0, "sales_activities": 0,
                                 "last_contacted": None, "loc_src": "hubspot", "rep": rep["short"], **({"do_not_call": True} if dnc else {})})
                if len(keys) > 1:   # contact shared by several pins (e.g. 3M's two DeKalb DCs)
                    for kx in keys[1:]:
                        keyed[kx].setdefault("contact_ids", []).append(c["record_id"])
                    keyed[keys[0]].setdefault("contact_ids", []).append(c["record_id"])
            for x in mine:
                if x["filter"] not in ("all", "unassigned") and "contact_ids" not in x and False:
                    pass
            companies.append(co); locs.extend(mine); n_loc += sum(1 for x in mine if x["pin"])
            if flags:
                report["flags"].append({"rep": rep["short"], "company": name, "record_id": rid, "flag": " ".join(flags)})
        report["reps"][rep["short"]] = {"companies": len(by_id), "contacts_csv_rows": len(crows), "contacts_loaded": sum(1 for c in contacts if c["rep"] == rep["short"]),
                                        "pins": n_loc, "contacts_file": os.path.exists(os.path.join(base, "contacts.csv"))}
    return companies, locs, contacts, report


def apply_reps(d, data_dir=None, geocode=True, retry=False, write_report=True):
    data_dir = data_dir or os.environ.get("REP_DATA_DIR", DEFAULT_DATA_DIR)
    if not all(os.path.exists(os.path.join(data_dir, r["dir"] + "-closed-won", "companies.csv")) for r in REPS):
        print("rep_loader: CSVs not found under", data_dir, "- keeping existing rep data as is", file=sys.stderr)
        return d
    geo = Geo(enabled=geocode, retry_misses=retry)
    cos, locs, cs, report = load(data_dir, geo)
    geo.save()
    # keep touch counts / titles already in data.json
    old = {str(c.get("hubspot_contact_id")): c for c in d["contacts"] if c.get("am") in REP_AMS}
    for c in cs:
        o = old.get(c["hubspot_contact_id"])
        if o:
            for k in ("times_contacted", "sales_activities", "last_contacted", "is_dm", "role"):
                if k in o:
                    c[k] = o[k]
            if o.get("title") and not c["title"]:
                c["title"] = o["title"]
    taken = {str(c.get("hubspot_contact_id")) for c in d["contacts"] if c.get("am") not in REP_AMS}
    clash = [c for c in cs if c["hubspot_contact_id"] in taken]
    if clash:
        report["contacts_skipped"] += [{"rep": c["rep"], "record_id": c["hubspot_contact_id"], "email": c["email"], "why": "already on the map for another rep"} for c in clash]
        cs = [c for c in cs if c["hubspot_contact_id"] not in taken]
    others = {x["name"] for x in d["companies"] if x.get("am") not in REP_AMS}
    cos = [c for c in cos if c["name"] not in others or print("rep_loader: skipping name clash", c["name"], file=sys.stderr)]
    # strip previous rep-owned records, then append the fresh ones
    d["companies"] = [x for x in d["companies"] if x.get("am") not in REP_AMS] + cos
    d["locations"] = [l for l in d["locations"] if l.get("am") not in REP_AMS] + locs
    d["contacts"] = [c for c in d["contacts"] if c.get("am") not in REP_AMS] + cs
    bc = d["stats"]["by_company"]
    for k in [k for k, v in bc.items() if k in {x["name"] for x in cos}]:
        bc.pop(k)
    for c in cos:
        bc[c["name"]] = {"contacts": 0, "with_phone": 0, "pins": 0, "supplier_pins": 0}
    ids = {}
    for c in d["contacts"]:
        ids.setdefault(str(c["hubspot_contact_id"]), c)
    # location counters (incl. shared contact_ids pins)
    for l in d["locations"]:
        if l.get("am") not in REP_AMS:
            continue
        if l.get("contact_ids"):
            l["contact_ids"] = sorted(set(l["contact_ids"]))
            m = [ids[i] for i in l["contact_ids"] if i in ids]
        elif l["filter"] == "all":
            m = [c for c in d["contacts"] if c["company"] == l["company"]]
        elif l["filter"] == "unassigned":
            m = [c for c in d["contacts"] if c["company"] == l["company"] and not c["plant"]]
        else:
            m = [c for c in d["contacts"] if c["company"] == l["company"] and c.get("plant_id") == l["id"]]
        l.update(contact_count=len(m), with_phone=sum(1 for c in m if c["has_phone"]), dm_count=sum(1 for c in m if c["is_dm"]))
    scope = d.get("scope", "")
    add = " + Closed Won accounts for Nick (Nicholas McNamara), Mia (Mia Medjedovic), Addie (Addison Parker)"
    if add not in scope:
        d["scope"] = scope + add
    report["totals"] = {r: dict(v, locations=sum(1 for l in locs if l["rep"] == r and l["pin"])) for r, v in report["reps"].items()}
    for r in REPS:
        s = r["short"]
        mine = [c for c in cs if c["rep"] == s]
        report["reps"][s].update(contacts_unassigned=sum(1 for c in mine if not c["plant"]),
                                 companies_without_contacts=sorted(c["name"] for c in cos if c["rep"] == s and not any(x["company_id"] == c["id"] for x in mine)),
                                 unassigned_companies=sorted(c["name"] for c in cos if c["rep"] == s and not any(l["company_id"] == c["id"] and l["pin"] for l in locs)))
    if write_report:
        s = json.dumps(report, indent=1, ensure_ascii=False) + "\n"
        if not os.path.exists(REPORT_FILE) or open(REPORT_FILE).read() != s:
            open(REPORT_FILE, "w").write(s)
    return d


if __name__ == "__main__":   # convenience wrapper: same as `python3 apply_site_overrides.py [flags]`
    import runpy
    sys.argv[0] = os.path.join(HERE, "apply_site_overrides.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
