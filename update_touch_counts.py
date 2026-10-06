#!/usr/bin/env python3
"""Apply HubSpot "Number of times contacted" counts to the dialer map data (data.json + data.js).

Input CSV columns (HubSpot contact export / scrape):
    contact_id,name,email,times_contacted,sales_activities,last_contacted,company

Join rules (map contacts only; CSV rows for contacts not on the map are skipped, never added):
    1. contact_id == hubspot_contact_id
    2. else email, case-insensitive (only if unique on the map and that contact wasn't already matched by ID)
Each map contact gets:
    times_contacted   int  (HubSpot "Number of times contacted": all logged calls, emails, meetings; blank -> 0)
    sales_activities  int  (blank -> 0)
    last_contacted    "YYYY-MM-DD" in America/Chicago when parseable, raw string if not, null if blank
Map contacts with no CSV row get 0 / 0 / null. The data also gets
    touch_counts_updated  ISO timestamp with CT offset (default: the CSV's file mtime; override with --as-of)

    python3 update_touch_counts.py contact_touch_counts.csv              # write data.json + data.js, report
    python3 update_touch_counts.py new.csv --as-of "2026-10-07T09:00"    # explicit as-of (CT if no offset)
    python3 update_touch_counts.py new.csv --publish                     # + commit/push ONLY data.json, data.js
    python3 update_touch_counts.py new.csv --dry-run                     # report only, write nothing

--publish refuses if local master has unpushed commits (so only the data files get pushed), pulls
origin/master first, commits only data.json + data.js, and pushes to master (one retry on a push race).
Stdlib only, Python 3.9+. Exit codes: 0 ok, 1 error.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
HERE = os.path.dirname(os.path.abspath(__file__))
JS_PREFIX = "window.__DIALER_DATA__ = "
SORT_NOTE = ("Sort order (UI default): HubSpot 'Number of times contacted' desc, then sales activities desc, "
             "then Decision Maker first, then name. Toggle 'Decision makers first' for DM → phone → name.")
TZ_ABBR = {"CDT": -5, "CST": -6, "CT": None, "EDT": -4, "EST": -5, "ET": None, "MDT": -6, "MST": -7,
           "PDT": -7, "PST": -8, "UTC": 0, "GMT": 0, "Z": 0}
ALIASES = {
    "contact_id": ["contact_id", "hubspot_contact_id", "record id", "record_id", "id"],
    "email": ["email", "contact_email"],
    "name": ["name", "contact_name"],
    "times_contacted": ["times_contacted", "number of times contacted", "num_contacted_notes", "num_notes"],
    "sales_activities": ["sales_activities", "number of sales activities", "num_notes_sales_activities"],
    "last_contacted": ["last_contacted", "last contacted", "notes_last_contacted"],
}


def pick(row, field):
    low = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for a in ALIASES[field]:
        v = low.get(a)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def to_int(s):
    s = re.sub(r"[,\s]", "", s or "")
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def norm_date(s):
    """'Oct 6, 2026 8:44 AM CDT' / ISO / epoch ms / 10/6/2026 -> 'YYYY-MM-DD' (CT). Unparseable -> raw; blank -> None."""
    s = (s or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{12,14}", s):  # epoch ms
        return datetime.fromtimestamp(int(s) / 1000, CT).date().isoformat()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (d.astimezone(CT) if d.tzinfo else d).date().isoformat()
    except ValueError:
        pass
    tz = None
    m = re.search(r"\s+([A-Z]{1,4})$", s)
    if m and m.group(1) in TZ_ABBR:
        off = TZ_ABBR[m.group(1)]
        tz = CT if off is None else timezone(timedelta(hours=off))
        s = s[: m.start()].strip()
    for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y %I:%M:%S %p", "%B %d, %Y %I:%M %p", "%b %d, %Y", "%B %d, %Y",
                "%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            d = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if tz is not None:
            d = d.replace(tzinfo=tz).astimezone(CT)
        return d.date().isoformat()
    return (s if tz is None else (s + " " + m.group(1)))


def parse_as_of(s, csv_path):
    if not s:
        return datetime.fromtimestamp(os.path.getmtime(csv_path), CT).replace(microsecond=0)
    if s == "now":
        return datetime.now(CT).replace(microsecond=0)
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (d.replace(tzinfo=CT) if d.tzinfo is None else d.astimezone(CT)).replace(microsecond=0)


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stdout}{r.stderr}")
    return r


def write_data(data, json_path, js_path):
    text = json.dumps(data, indent=2, ensure_ascii=False)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(JS_PREFIX + text + ";\n")


def check_sync(json_path, js_path):
    with open(json_path, encoding="utf-8") as f:
        a = json.load(f)
    with open(js_path, encoding="utf-8") as f:
        js = f.read().strip()
    if not (js.startswith(JS_PREFIX) and js.endswith(";")):
        return False
    return json.loads(js[len(JS_PREFIX):-1]) == a


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="touch-count CSV (same columns as contact_touch_counts.csv)")
    ap.add_argument("--data", default=os.path.join(HERE, "data.json"))
    ap.add_argument("--js", default=os.path.join(HERE, "data.js"))
    ap.add_argument("--as-of", help="touch_counts_updated value: ISO datetime (CT if no offset) or 'now'; default = CSV mtime")
    ap.add_argument("--dry-run", action="store_true", help="report only; don't write")
    ap.add_argument("--publish", action="store_true", help="git commit + push ONLY data.json and data.js to master")
    ap.add_argument("--branch", default="master")
    ap.add_argument("-v", "--verbose", action="store_true", help="list skipped CSV rows / unmatched contacts")
    a = ap.parse_args()

    data_abs, js_abs = os.path.abspath(a.data), os.path.abspath(a.js)
    repo = None
    if a.publish:
        if a.dry_run:
            ap.error("--publish and --dry-run are mutually exclusive")
        r = git(os.path.dirname(data_abs), "rev-parse", "--show-toplevel", check=False)
        if r.returncode != 0:
            raise SystemExit(f"--publish: {os.path.dirname(data_abs)} is not inside a git checkout")
        repo = r.stdout.strip()
        cur = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if cur != a.branch:
            raise SystemExit(f"--publish: checkout is on '{cur}', expected '{a.branch}'")
        git(repo, "fetch", "-q", "origin", a.branch)
        ahead = git(repo, "rev-list", f"origin/{a.branch}..HEAD").stdout.split()
        if ahead:
            raise SystemExit(f"--publish: local {a.branch} has {len(ahead)} unpushed commit(s); refusing so only "
                             f"data.json/data.js are pushed. Push or reset them first.")
        git(repo, "pull", "-q", "--rebase", "--autostash", "origin", a.branch)

    with open(a.data, encoding="utf-8") as f:
        data = json.load(f)
    with open(a.csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    as_of = parse_as_of(a.as_of, a.csv)

    contacts = data["contacts"]
    by_id, by_email = {}, {}
    for c in contacts:
        cid = str(c.get("hubspot_contact_id") or "")
        if not cid:
            m = re.search(r"/record/0-1/(\d+)", c.get("hubspot_url") or "")
            cid = m.group(1) if m else ""
        if cid:
            by_id[cid] = c
        if c.get("email"):
            by_email.setdefault(c["email"].strip().lower(), []).append(c)

    assigned = {}  # id(contact) -> (row, how)
    skipped, dup_rows = [], 0
    pending_email = []
    for row in rows:
        cid = re.sub(r"\D", "", pick(row, "contact_id"))
        c = by_id.get(cid) if cid else None
        if c is not None:
            if id(c) in assigned:
                dup_rows += 1
            assigned[id(c)] = (row, "id")
        else:
            pending_email.append(row)
    for row in pending_email:
        em = pick(row, "email").lower()
        hits = by_email.get(em, []) if em else []
        if len(hits) == 1 and (id(hits[0]) not in assigned or assigned[id(hits[0])][1] == "email"):
            if id(hits[0]) in assigned:
                dup_rows += 1
            assigned[id(hits[0])] = (row, "email")
        else:
            skipped.append(row)

    n_id = n_email = 0
    unmatched = []
    raw_dates = 0
    for c in contacts:
        hit = assigned.get(id(c))
        if hit:
            row, how = hit
            n_id += how == "id"
            n_email += how == "email"
            c["times_contacted"] = to_int(pick(row, "times_contacted"))
            c["sales_activities"] = to_int(pick(row, "sales_activities"))
            c["last_contacted"] = norm_date(pick(row, "last_contacted"))
            if c["last_contacted"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["last_contacted"]):
                raw_dates += 1
        else:
            unmatched.append(c)
            c["times_contacted"], c["sales_activities"], c["last_contacted"] = 0, 0, None

    # top-level metadata (inserted after "generated" the first time)
    meta = {"touch_counts_updated": as_of.isoformat(timespec="seconds"),
            "touch_counts_source": f"HubSpot 'Number of times contacted' (all logged calls, emails, meetings) · {os.path.basename(a.csv)}"}
    if "touch_counts_updated" in data:
        data.update(meta)
    else:
        new = {}
        for k, v in data.items():
            new[k] = v
            if k == "generated":
                new.update(meta)
        if "touch_counts_updated" not in new:
            new.update(meta)
        data = new
    notes = [n for n in data.get("notes", []) if not str(n).startswith("Sort order")]
    notes.insert(1 if notes else 0, SORT_NOTE)
    data["notes"] = notes
    data.setdefault("stats", {})["touch_counts"] = {
        "matched": n_id + n_email, "matched_by_id": n_id, "matched_by_email": n_email,
        "unmatched": len(unmatched), "csv_rows": len(rows), "csv_rows_skipped": len(skipped),
    }

    print(f"CSV rows: {len(rows)} · map contacts: {len(contacts)}")
    print(f"Matched: {n_id + n_email} (by id {n_id}, by email {n_email}) · unmatched map contacts (set 0/null): {len(unmatched)}")
    print(f"Skipped CSV rows (not on the map, not added): {len(skipped)}" + (f" · duplicate CSV rows for the same contact (last wins): {dup_rows}" if dup_rows else ""))
    if raw_dates:
        print(f"  ! {raw_dates} last_contacted values were not parseable and were kept as raw strings")
    if a.verbose:
        for r in skipped:
            print(f"  skip: {pick(r, 'contact_id')} {pick(r, 'name') or '(no name)'} <{pick(r, 'email')}> {pick(r, 'times_contacted') or 0} touches")
        for c in unmatched:
            print(f"  unmatched: {c.get('hubspot_contact_id')} {c.get('name')} <{c.get('email')}>")
    print(f"touch_counts_updated = {meta['touch_counts_updated']}")
    # Supplier pins reference contacts by ID (no copies), so their contacts pick up these counts automatically.
    ids_on_map = {str(c.get("hubspot_contact_id") or "") for c in contacts}
    for l in data.get("locations", []):
        if isinstance(l.get("contact_ids"), list):
            missing = [i for i in l["contact_ids"] if str(i) not in ids_on_map]
            print(f"Supplier pin {l.get('label') or l['id']}: {len(l['contact_ids'])} referenced contacts"
                  + (f" · ! {len(missing)} IDs not on the map (run sync_supplier_pins.py)" if missing else ""))

    if a.dry_run:
        print("Dry run: nothing written.")
        return
    write_data(data, data_abs, js_abs)
    if not check_sync(data_abs, js_abs):
        raise SystemExit("data.js and data.json are out of sync after writing (unexpected)")
    print(f"Wrote {data_abs} and {js_abs} (in sync)")

    if a.publish:
        rels = [os.path.relpath(p, repo) for p in (data_abs, js_abs)]
        git(repo, "add", "--", *rels)
        if git(repo, "diff", "--cached", "--quiet", "--", *rels, check=False).returncode == 0:
            print("Publish skipped (data files identical to HEAD).")
            return
        msg = (f"Touch counts as of {as_of.strftime('%Y-%m-%d %-I:%M %p')} CT · "
               f"{n_id + n_email}/{len(contacts)} matched")
        git(repo, "commit", "-q", "-m", msg, "--", *rels)
        r = git(repo, "push", "-q", "origin", f"HEAD:{a.branch}", check=False)
        if r.returncode != 0:  # e.g. called_today.json was pushed meanwhile
            git(repo, "pull", "-q", "--rebase", "--autostash", "origin", a.branch)
            git(repo, "push", "-q", "origin", f"HEAD:{a.branch}")
        sha = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
        print(f"Published {', '.join(rels)} → origin/{a.branch} @ {sha}")


if __name__ == "__main__":
    main()
