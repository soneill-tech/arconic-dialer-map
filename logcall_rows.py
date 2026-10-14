#!/usr/bin/env python3
"""Read Log Call entries from the shared ntfy.sh topic and print them as Google Sheet rows.

    python3 logcall_rows.py [--existing ids.txt] [--json]

Prints a JSON array of rows in the "AM Dialer Call Log" column order (see LOGCALL.md), skipping
call_ids already in the sheet (pass them one per line via --existing). The sync agent appends the
output with the Google Sheets connector (append_rows). Read-only: never writes anywhere.
ntfy.sh keeps messages ~12h, so run this at least every few hours (the hourly sync does).
"""
import argparse, json, urllib.request

TOPIC_URL = "https://ntfy.sh/tsdm-calllog-ddbdae3e678c14eb"
COLUMNS = ["call_id", "timestamp", "am", "contact_id", "contact_name", "company_location", "phone",
           "outcome", "direction", "duration_min", "notes", "logged_at", "source", "hubspot_logged"]


def fetch_calls():
    with urllib.request.urlopen(TOPIC_URL + "/json?poll=1&since=all", timeout=30) as r:
        lines = [json.loads(l) for l in r.read().decode().splitlines() if l.strip()]
    deleted = {m.get("sequence_id") for m in lines if m.get("event") == "message_delete"}
    calls = {}
    for m in lines:
        if m.get("event") != "message" or m["id"] in deleted:
            continue
        try:
            c = json.loads(m["message"])
        except ValueError:
            continue
        if isinstance(c, dict) and c.get("call_id") and c.get("contact_id"):
            c["ntfy_id"] = m["id"]
            calls[c["call_id"]] = c
    return sorted(calls.values(), key=lambda c: c.get("timestamp", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing", help="file with call_ids already in the sheet, one per line")
    a = ap.parse_args()
    seen = set()
    if a.existing:
        seen = {l.strip() for l in open(a.existing) if l.strip()}
    rows = [[("" if c.get(k) is None else c.get(k, "")) if k != "hubspot_logged" else "" for k in COLUMNS]
            for c in fetch_calls() if c["call_id"] not in seen]
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
