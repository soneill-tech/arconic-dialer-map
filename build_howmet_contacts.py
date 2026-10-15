#!/usr/bin/env python3
"""Turn the Howmet rows of Kahekili's dialer CSV into howmet_contacts.json (read by apply_site_overrides.py).

    python3 build_howmet_contacts.py /path/to/kili_contacts.csv

Columns used: Company, Contact Name, Role, Job Title, Phone, Mobile, Email, HubSpot Company URL, HubSpot Contact URL, Notes.
Contact id = last path segment of the Contact URL. Rows whose name field is an email get a display name derived from it.
Contacts already on the map (by HubSpot id, e.g. Arconic ones that share the Howmet company in the CSV) are skipped by
apply_site_overrides.py, not here. Stdlib only. Never touches HubSpot.
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def display_name(name, email):
    if "@" in (name or "") or not (name or "").strip():
        local = (email or name or "").split("@")[0]
        return " ".join(p.capitalize() for p in re.split(r"[._\\-]+", local) if p)
    return name.strip()


def norm_phone(p):
    p = (p or "").strip()
    if not p:
        return ""
    base, ext = re.split(r"(?i)\s*(?:ext\.?|x)\s*", p, maxsplit=1)[0], (re.split(r"(?i)\s*(?:ext\.?|x)\s*", p, maxsplit=1) + [""])[1]
    d = re.sub(r"\D", "", base)
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    if len(d) == 10:
        return f"{d[:3]}-{d[3:6]}-{d[6:]}" + (f" ext. {ext.strip()}" if ext.strip() else "")
    return p


def area_code(p):
    d = re.sub(r"\D", "", re.split(r"(?i)ext|x", p or "")[0])
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return d[:3] if len(d) == 10 else ""


def main():
    rows = [r for r in csv.DictReader(open(sys.argv[1])) if "howmet" in r["Company"].lower()]
    out, seen = [], set()
    for r in rows:
        cid = r["HubSpot Contact URL"].rstrip("/").split("/")[-1]
        if not cid.isdigit() or cid in seen:
            continue
        seen.add(cid)
        phone, mobile = norm_phone(r["Phone"]), norm_phone(r["Mobile"])
        out.append({"hubspot_contact_id": cid, "name": display_name(r["Contact Name"], r["Email"]), "title": r["Job Title"].strip(),
                    "phone": phone, "mobile": mobile, "email": r["Email"].strip(), "is_dm": r["Role"].strip().lower() == "decision maker",
                    "notes": r["Notes"].strip(), "area_code": area_code(phone) or area_code(mobile) or None})
    out.sort(key=lambda c: (not c["is_dm"], not (c["phone"] or c["mobile"]), c["name"].lower()))
    json.dump(out, open(os.path.join(HERE, "howmet_contacts.json"), "w"), indent=1, ensure_ascii=False)
    print(len(out), "contacts;", sum(1 for c in out if c["phone"] or c["mobile"]), "with phone")


if __name__ == "__main__":
    main()
