#!/usr/bin/env python3
"""Drain manually-added locations/contacts (map "＋ Location" / "＋ Contact") from the ntfy queue.

    python3 manual_add.py rows [--existing-locations ids.txt] [--existing-contacts ids.txt]
        Prints {"locations": [[...]], "contacts": [[...]]}: new sheet rows (column order below), skipping ids
        already in the sheet (one id per line). The agent appends them to tabs "Added Locations" / "Added Contacts".
    python3 manual_add.py publish [--dry-run]
        Merges the queue into added_manual.json (union by id; the map reads this file, so additions outlive ntfy's
        ~12h cache) and commits + pushes ONLY that file to master. No-op when nothing changed.

Read-only against ntfy; never writes to HubSpot. Stdlib only. See MANUAL_ADD.md.
"""
import argparse, json, os, subprocess, sys, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC_URL = "https://ntfy.sh/tsdm-calllog-ddbdae3e678c14eb"
FILE = os.path.join(HERE, "added_manual.json")
LOC_COLS = ["loc_id", "created_at", "company", "city", "state", "address", "lat", "lon", "geo_source", "added_by",
            "logged_at", "source", "hubspot_synced"]
CON_COLS = ["contact_id", "created_at", "company", "name", "title", "phone", "mobile", "email", "location_id",
            "location_label", "added_by", "logged_at", "source", "hubspot_synced"]
KEYMAP = {"loc_id": "id", "contact_id": "id", "created_at": "added_at", "logged_at": "added_at"}


def fetch_items():
    with urllib.request.urlopen(TOPIC_URL + "/json?poll=1&since=all", timeout=30) as r:
        lines = [json.loads(l) for l in r.read().decode().splitlines() if l.strip()]
    deleted = {m.get("sequence_id") for m in lines if m.get("event") == "message_delete"}
    items = {}
    for m in lines:
        if m.get("event") != "message" or m["id"] in deleted:
            continue
        try:
            it = json.loads(m["message"])
        except ValueError:
            continue
        if isinstance(it, dict) and it.get("type") in ("add_location", "add_contact") and it.get("id"):
            items[it["id"]] = it
    return items


def load_file():
    try:
        return {i["id"]: i for i in json.load(open(FILE)).get("items", [])}
    except (OSError, ValueError):
        return {}


def row(it, cols):
    out = []
    for c in cols:
        if c == "hubspot_synced":
            out.append("")
        elif c == "logged_at":
            out.append(datetime.now(timezone.utc).isoformat(timespec="seconds"))
        else:
            v = it.get(KEYMAP.get(c, c), "")
            out.append("" if v is None else v)
    return out


def ids(path):
    return {l.strip() for l in open(path) if l.strip()} if path else set()


def git(*a):
    return subprocess.run(["git", "-C", HERE, *a], check=True, capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rows"); r.add_argument("--existing-locations"); r.add_argument("--existing-contacts")
    p = sub.add_parser("publish"); p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "rows":
        items = {**load_file(), **fetch_items()}
        key = lambda i: i.get("added_at", "")
        sl, sc = ids(a.existing_locations), ids(a.existing_contacts)
        locs = [row(i, LOC_COLS) for i in sorted(items.values(), key=key) if i["type"] == "add_location" and i["id"] not in sl]
        cons = [row(i, CON_COLS) for i in sorted(items.values(), key=key) if i["type"] == "add_contact" and i["id"] not in sc]
        print(json.dumps({"locations": locs, "contacts": cons}, ensure_ascii=False))
        return
    merged = {**load_file(), **fetch_items()}
    old = load_file()
    if set(merged) == set(old):
        print("added_manual.json: no new items (%d total)" % len(old)); return
    new = sorted(merged.values(), key=lambda i: i.get("added_at", ""))
    for i in new:
        i.pop("ntfy_id", None)
    print("added_manual.json: %d -> %d items" % (len(old), len(new)))
    if a.dry_run:
        return
    git("pull", "--rebase", "--autostash", "origin", "master")
    merged = {**load_file(), **merged}
    json.dump({"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "items": sorted(merged.values(), key=lambda i: i.get("added_at", ""))},
              open(FILE, "w"), indent=1, ensure_ascii=False)
    open(FILE, "a").write("\n")
    git("add", "added_manual.json")
    git("commit", "-m", "added_manual: %d items" % len(merged), "--", "added_manual.json")
    git("push", "origin", "HEAD:master")
    print("published")


if __name__ == "__main__":
    main()
