#!/usr/bin/env python3
"""Drain map-queue items (manual adds, edits/deletes, titles, follow-ups) and keep last-call history.

    python3 manual_add.py rows [--existing-locations f] [--existing-contacts f] [--existing-changes f]
        Prints {"locations":[[...]],"contacts":[[...]],"changes":[[...]]}: new sheet rows (column orders below),
        skipping ids already in the sheet (one id per line, first column). Append them to the tabs
        "Added Locations" / "Added Contacts" / "Manual Changes" with the Sheets connector.
    python3 manual_add.py publish [--calls-json file] [--dry-run]
        Merges the ntfy queue into added_manual.json (union by id) and last call per contact into last_calls.json
        (queue calls + called_today.json + optional --calls-json rows from the sheet's Calls tab), then commits +
        pushes ONLY those two files to master. No-op when nothing changed. ntfy keeps ~12h, so run at least hourly.

Read-only against ntfy; never writes to HubSpot. Stdlib only, Python 3.9+. See MANUAL_ADD.md.
"""
import argparse, json, os, subprocess, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC_URL = "https://ntfy.sh/tsdm-calllog-ddbdae3e678c14eb"
FILE = os.path.join(HERE, "added_manual.json")
CALLS_FILE = os.path.join(HERE, "last_calls.json")
ADD_TYPES = ("add_location", "add_contact")
TYPES = ADD_TYPES + ("edit_item", "delete_item", "set_title", "followup", "hide_contact", "restore_contact", "move_contact", "reset_move")
LOC_COLS = ["loc_id", "created_at", "company", "city", "state", "address", "lat", "lon", "geo_source", "added_by",
            "logged_at", "source", "hubspot_synced"]
CON_COLS = ["contact_id", "created_at", "company", "name", "title", "phone", "mobile", "email", "location_id",
            "location_label", "added_by", "logged_at", "source", "hubspot_synced"]
CHG_COLS = ["change_id", "created_at", "type", "target_id", "detail", "added_by", "logged_at", "source", "hubspot_synced"]
KEYMAP = {"loc_id": "id", "contact_id": "id", "created_at": "added_at", "logged_at": "added_at", "change_id": "id"}


def _ndjson():
    with urllib.request.urlopen(TOPIC_URL + "/json?poll=1&since=all", timeout=30) as r:
        lines = [json.loads(l) for l in r.read().decode().splitlines() if l.strip()]
    deleted = {m.get("sequence_id") for m in lines if m.get("event") == "message_delete"}
    for m in lines:
        if m.get("event") == "message" and m["id"] not in deleted:
            try:
                x = json.loads(m["message"])
            except ValueError:
                continue
            if isinstance(x, dict):
                yield x


def fetch_queue():
    items, calls = {}, []
    for x in _ndjson():
        if x.get("type") in TYPES and x.get("id"):
            x.pop("ntfy_id", None)
            items[x["id"]] = x
        elif not x.get("type") and x.get("call_id") and x.get("contact_id"):
            calls.append(x)
    return items, calls


def load_file():
    try:
        return {i["id"]: i for i in json.load(open(FILE)).get("items", [])}
    except (OSError, ValueError):
        return {}


def load_calls():
    try:
        return json.load(open(CALLS_FILE)).get("calls", {})
    except (OSError, ValueError):
        return {}


def ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def merge_calls(cur, rows):
    out = dict(cur)
    for r in rows:
        cid, t = str(r.get("contact_id") or ""), r.get("timestamp") or r.get("time")
        if not cid or not ts(t):
            continue
        if cid not in out or ts(t) >= ts(out[cid]["time"]):
            out[cid] = {"time": t, "outcome": r.get("outcome", "") or "", "am": r.get("am", "") or ""}
    return out


def row(it, cols):
    out = []
    for c in cols:
        if c == "hubspot_synced":
            out.append("")
        elif c == "logged_at":
            out.append(datetime.now(timezone.utc).isoformat(timespec="seconds"))
        elif c == "target_id":
            out.append(it.get("target_id") or it.get("contact_id") or "")
        elif c == "detail":
            out.append(json.dumps({k: v for k, v in it.items() if k not in
                                   ("type", "id", "added_at", "added_by", "source", "target_id", "ntfy_id")}, ensure_ascii=False))
        else:
            v = it.get(KEYMAP.get(c, c), "")
            out.append("" if v is None else v)
    return out


def ids(path):
    return {l.strip() for l in open(path) if l.strip()} if path else set()


def git(*a):
    return subprocess.run(["git", "-C", HERE, *a], check=True, capture_output=True, text=True).stdout.strip()


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False); f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rows")
    for k in ("locations", "contacts", "changes"):
        r.add_argument("--existing-" + k)
    p = sub.add_parser("publish"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--calls-json")
    a = ap.parse_args()
    if a.cmd == "rows":
        items = {**load_file(), **fetch_queue()[0]}
        srt = sorted(items.values(), key=lambda i: i.get("added_at", ""))
        sl, sc, sg = ids(a.existing_locations), ids(a.existing_contacts), ids(a.existing_changes)
        print(json.dumps({
            "locations": [row(i, LOC_COLS) for i in srt if i["type"] == "add_location" and i["id"] not in sl],
            "contacts": [row(i, CON_COLS) for i in srt if i["type"] == "add_contact" and i["id"] not in sc],
            "changes": [row(i, CHG_COLS) for i in srt if i["type"] not in ADD_TYPES and i["id"] not in sg]},
            ensure_ascii=False))
        return
    qitems, qcalls = fetch_queue()
    extra = json.load(open(a.calls_json)) if a.calls_json else []
    try:
        ct = json.load(open(os.path.join(HERE, "called_today.json"))).get("calls", [])
    except (OSError, ValueError):
        ct = []
    old_items, old_calls = load_file(), load_calls()
    items = {**old_items, **qitems}
    calls = merge_calls(old_calls, list(extra) + list(ct) + qcalls)
    if set(items) == set(old_items) and calls == old_calls:
        print("no new items or calls (%d items, %d contacts with calls)" % (len(old_items), len(old_calls))); return
    print("added_manual.json: %d -> %d items; last_calls.json: %d -> %d contacts" % (len(old_items), len(items), len(old_calls), len(calls)))
    if a.dry_run:
        return
    git("pull", "--rebase", "--autostash", "origin", "master")
    items = {**load_file(), **items}
    calls = merge_calls(load_calls(), [{"contact_id": k, **v} for k, v in calls.items()])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(FILE, {"updated_at": now, "items": sorted(items.values(), key=lambda i: (i.get("added_at", ""), i["id"]))})
    write_json(CALLS_FILE, {"updated_at": now, "calls": calls})
    git("add", "added_manual.json", "last_calls.json")
    git("commit", "-m", "manual_add: %d items, %d last-calls" % (len(items), len(calls)), "--", "added_manual.json", "last_calls.json")
    git("push", "origin", "HEAD:master")
    print("published")


if __name__ == "__main__":
    main()
