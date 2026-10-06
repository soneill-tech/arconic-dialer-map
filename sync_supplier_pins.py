#!/usr/bin/env python3
"""Add / refresh the Arconic-managed SUPPLIER pins in data.json + data.js.

Supplier pins are sites that Arconic manages but that are NOT Arconic facilities. They carry no contact
records of their own; each one REFERENCES existing contacts by hubspot_contact_id, copied from one or
more existing plant pins ("contacts_from"). There are no duplicate contact records, so touch counts,
Open in HubSpot links, sorting and the called-today pulse stay consistent, and account/AM totals
(which count DATA.contacts) never double count.

    python3 sync_supplier_pins.py            # insert/refresh supplier locations, recompute ids + stats, write
    python3 sync_supplier_pins.py --check    # verify only (exit 1 if data.json is stale / inconsistent)

Rerun it whenever plant assignments change (e.g. after rebuilding data). update_touch_counts.py and
update_called_today.py don't change pin membership, so they don't need it. Stdlib only, Python 3.9+.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JS_PREFIX = "window.__DIALER_DATA__ = "
SUPPLIER_TAG = "Supplier (Arconic-managed)"
BETTENDORF = "arc:Davenport Works"   # Davenport Works = 4879 State St, Bettendorf (Riverdale), IA 52722
LANCASTER = "arc:Lancaster"          # Lancaster Operations, Lancaster, PA (717)

# Nominatim city-level geocodes (fetched 2026-10-06)
SUPPLIERS = [
    dict(id="arc:sup:Middlebury", name="Middlebury, IN (supplier)", label="Middlebury, IN · Supplier (Arconic-managed)",
         city="Middlebury", region="Middlebury, Elkhart County, Indiana, USA", lat=41.6750714, lon=-85.7060263,
         contacts_from=[BETTENDORF],
         hint="Supplier (Arconic-managed), not an Arconic facility · same contacts as Davenport Works (Bettendorf, IA)"),
    dict(id="arc:sup:Minster", name="Minster, OH (supplier)", label="Minster, OH · Supplier (Arconic-managed)",
         city="Minster", region="Minster, Auglaize County, Ohio, USA", lat=40.3931033, lon=-84.3760612,
         contacts_from=[LANCASTER, BETTENDORF],
         hint="Supplier (Arconic-managed), not an Arconic facility · contacts of Lancaster, PA + Davenport Works (Bettendorf, IA)"),
]


def cid_of(c):
    return str(c.get("hubspot_contact_id") or "")


def build(data):
    """Return a new data dict with supplier locations inserted/refreshed. Raises SystemExit on bad input."""
    data = json.loads(json.dumps(data))
    locs, contacts = data["locations"], data["contacts"]
    by_loc = {l["id"]: l for l in locs}
    arc = next(l for l in locs if l["id"] == "arc:all")
    base = {k: arc[k] for k in ("am", "company", "company_id", "company_url")}
    # supplier membership must reference real, unique contact IDs
    ids = [cid_of(c) for c in contacts]
    if any(not i for i in ids):
        raise SystemExit("some contacts lack hubspot_contact_id; supplier pins reference contacts by ID")
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate hubspot_contact_id in contacts; refusing (supplier pins would be ambiguous)")
    by_id = {cid_of(c): c for c in contacts}

    report = []
    for s in SUPPLIERS:
        member, seen, per_src = [], set(), {}
        for src in s["contacts_from"]:
            if src not in by_loc or not by_loc[src].get("pin"):
                raise SystemExit(f"source pin {src!r} for {s['id']} not found")
            src_ids = [cid_of(c) for c in contacts if c.get("plant_id") == src and c.get("company") == base["company"]]
            per_src[src] = src_ids
            for i in src_ids:
                if i not in seen:
                    seen.add(i); member.append(i)
        overlap = len(set.intersection(*map(set, per_src.values()))) if len(per_src) > 1 else 0
        cs = [by_id[i] for i in member]
        loc = dict(id=s["id"], name=s["name"], label=s["label"], city=s["city"], region=s["region"],
                   lat=s["lat"], lon=s["lon"], **base,
                   contact_count=len(cs), with_phone=sum(bool(c.get("has_phone")) for c in cs),
                   dm_count=sum(bool(c.get("is_dm")) for c in cs),
                   filter=s["id"], hint=s["hint"], pin=True, source="nominatim",
                   kind="supplier", supplier_tag=SUPPLIER_TAG, managed_by="Arconic", is_company_facility=False,
                   contacts_from=s["contacts_from"], contact_ids=member)
        if s["id"] in by_loc:
            locs[locs.index(by_loc[s["id"]])] = loc
        else:  # insert after the last Arconic pin, before "arc:unassigned"
            pos = next(i for i, l in enumerate(locs) if l["id"] == "arc:unassigned")
            locs.insert(pos, loc)
        by_loc[s["id"]] = loc
        report.append((s, per_src, overlap, loc))

    st = data["stats"]
    st["pins"] = sum(1 for l in locs if l.get("pin"))
    st["supplier_pins"] = sum(1 for l in locs if l.get("kind") == "supplier")
    for co, b in st["by_company"].items():
        b["pins"] = sum(1 for l in locs if l.get("pin") and l.get("company") == co)
        b["supplier_pins"] = sum(1 for l in locs if l.get("kind") == "supplier" and l.get("company") == co)
        b["contacts"] = sum(1 for c in contacts if c.get("company") == co)   # unique contacts, never pin sums
    st["contacts"] = len(contacts)
    note = ("Supplier pins (Arconic-managed, not Arconic facilities) reference existing contacts by HubSpot ID "
            "(contact_ids, copied from contacts_from pins); they add no contacts, so totals are unique contacts.")
    data["notes"] = [n for n in data.get("notes", []) if not str(n).startswith("Supplier pins")] + [note]
    return data, report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(HERE, "data.json"))
    ap.add_argument("--js", default=os.path.join(HERE, "data.js"))
    ap.add_argument("--geocodes", default=os.path.join(HERE, "geocodes.json"))
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 if stale or inconsistent")
    a = ap.parse_args()

    with open(a.data, encoding="utf-8") as f:
        data = json.load(f)
    new, report = build(data)
    for s, per_src, overlap, loc in report:
        srcs = " + ".join(f"{k} ({len(v)})" for k, v in per_src.items())
        print(f"{loc['id']}: {loc['contact_count']} contacts ({loc['with_phone']} w/ phone, {loc['dm_count']} DM) "
              f"from {srcs}; overlap {overlap}")
    st = new["stats"]
    print(f"pins={st['pins']} (supplier {st['supplier_pins']}) contacts={st['contacts']} "
          + " ".join(f"{k}:{v['contacts']}c/{v['pins']}p" for k, v in st["by_company"].items()))

    with open(a.js, encoding="utf-8") as f:
        js = f.read().strip()
    js_ok = js.startswith(JS_PREFIX) and js.endswith(";") and json.loads(js[len(JS_PREFIX):-1]) == data
    if a.check:
        problems = []
        if new != data:
            problems.append("data.json supplier pins/stats are stale (run sync_supplier_pins.py)")
        if not js_ok:
            problems.append("data.js is out of sync with data.json")
        for p in problems:
            print("FAIL:", p)
        if problems:
            sys.exit(1)
        print("OK: supplier pins up to date; data.js == data.json")
        return

    text = json.dumps(new, indent=2, ensure_ascii=False)
    with open(a.data, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    with open(a.js, "w", encoding="utf-8") as f:
        f.write(JS_PREFIX + text + ";\n")
    if os.path.exists(a.geocodes):
        with open(a.geocodes, encoding="utf-8") as f:
            geo = json.load(f)
        for s in SUPPLIERS:
            geo["Supplier · " + s["city"]] = dict(city=s["city"], region=s["region"], lat=s["lat"], lon=s["lon"], source="nominatim")
        with open(a.geocodes, "w", encoding="utf-8") as f:
            json.dump(geo, f, indent=2, ensure_ascii=False)
    print(f"Wrote {a.data} + {a.js}" + (" (+ geocodes.json)" if os.path.exists(a.geocodes) else ""))


if __name__ == "__main__":
    main()
