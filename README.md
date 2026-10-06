# Team Steve — Closed Won Dialer Map

Self-contained HTML map dashboard for Team Steve Closed Won dialer contacts:

| Company | AM | HubSpot | Contacts | w/ phone | Pins |
|---|---|---|---|---|---|
| Arconic | Kahekili Barrozo | `2359249037` | 419 | 168 | 6 |
| Kaiser Aluminum | Simran Subramanian | `5360206404` | 50 | 26 | 9 |

Live: https://soneill-tech.github.io/arconic-dialer-map/

## Open it

Double-click `index.html` (data is bundled in `data.js`, so `file://` works), or:

```bash
python3 -m http.server 8765   # then open http://localhost:8765/
```

## What's included

- Leaflet + Esri World_Street_Map tiles (no API key)
- **Arconic pins (blue):** Pittsburgh HQ, Davenport Works, Lafayette, Lancaster, Massena, Tennessee Ops (Alcoa) + All Arconic + Unassigned
- **Kaiser pins (orange):** Trentwood Works (Spokane Valley WA, 509), Warrick (Newburgh IN, 812), Knoxville TN (865),
  Franklin TN HQ (615), Tucson AZ (520), Newark Works (Heath OH, 740), Jackson TN (731), Foothill Ranch CA (949),
  Kalamazoo MI (269) + All Kaiser + Unassigned
- Side list grouped by company/AM; AM filter (All / Kahekili / Simran) and search
- Click a pin or card → that location's contacts, sorted **most contacted in HubSpot** first
  (`times_contacted` desc → `sales_activities` desc → Decision Maker first → name). A toggle in the panel switches to
  **Decision makers first** (DM → has phone → name). Each contact shows a badge like **2,494 touches · last 10/5**
  (HubSpot *Number of times contacted* = all logged calls, emails and meetings, not calls only), and the footer shows
  **Touch counts as of <date time> CT** (`touch_counts_updated` in the data).
- **"Not called today" pulse:** on load and every 5 min the page fetches `called_today.json?ts=<now>` (no-cache).
  A pin **pulses** (ring in its own color) when none of its contacts' `hubspot_contact_id`s are in `called_contact_ids`;
  pins with ≥1 contact called today stop pulsing and show a green ✓. Called contacts get a **✓ Called today <time>** badge,
  location cards show **✓ N called today**, and the header shows **Last synced: <time> CT**. If the file's `date` isn't
  today (America/Chicago) it's treated as stale → everything pulses + a "Call status last synced …" notice.
  Only the 15 plant pins pulse; the 309 Unassigned contacts have no pin (their ✓ shows in the list/cards only).
- Every contact has an **Open in HubSpot** button (`https://app.hubspot.com/contacts/6029765/record/0-1/<contactId>`, field `hubspot_contact_id`). Open it, then click **Call** in HubSpot so the call is logged. The 📞 `tel:` links dial from your phone and are **not logged**. If a contact ever lacks an ID, the UI falls back to a HubSpot search link.

## Call status (`called_today.json`)

```json
{"date":"2026-10-06","updated_at":"2026-10-06T08:44:52-05:00","source":"HubSpot calls (browser sync)",
 "called_contact_ids":["1190201"],
 "calls":[{"contact_id":"1190201","contact_name":"Jeremiah Libby","am":"Kahekili","time":"2026-10-06T09:14:00-05:00","outcome":"Left voicemail"}]}
```

Refresh it with `update_called_today.py` (stdlib only, Python 3.9+). Input CSV/JSON rows need one of
`contact_id` / `contact_email` / `contact_name`, plus optional `am`, `time`, `outcome`. Rows resolve via `data.json`
by ID → email → case-insensitive exact name within that AM's companies; unresolved rows are reported and skipped.

```bash
python3 update_called_today.py calls.csv              # write locally + report (no git)
python3 update_called_today.py calls.json --publish   # also commit+push ONLY called_today.json to master
python3 update_called_today.py --empty --publish      # reset to today's empty state (e.g. at midnight)
cat calls.json | python3 update_called_today.py - --publish --strict   # stdin; exit 2 if any row unresolved
```

`--publish` pushes only when the called set changed or the date rolled over vs `origin/master` (timestamp-only
refreshes are skipped; `--force` overrides), and refuses if local `master` has other unpushed commits.
Note: the live "Last synced" time is therefore the last *published change*, not the last check.

## Touch counts (`update_touch_counts.py`)

Contacts carry `times_contacted` (HubSpot "Number of times contacted"), `sales_activities` and `last_contacted`
(ISO date, CT). HubSpot has no call-only count per contact. Refresh from a new CSV with the same columns
(`contact_id,name,email,times_contacted,sales_activities,last_contacted,company`); stdlib only, Python 3.9+.
Join: `contact_id` = `hubspot_contact_id`, else email (case-insensitive). CSV rows not on the map are skipped
(never added); map contacts with no row get 0 / 0 / null. `touch_counts_updated` defaults to the CSV's file mtime (CT).

```bash
python3 update_touch_counts.py contact_touch_counts.csv --dry-run      # report matches only
python3 update_touch_counts.py contact_touch_counts.csv                # rewrite data.json + data.js (kept in sync)
python3 update_touch_counts.py new.csv --as-of 2026-10-07T09:00 -v     # explicit as-of (CT); list skipped rows
python3 update_touch_counts.py new.csv --publish                       # + commit/push ONLY data.json, data.js
```

`--publish` refuses if local `master` has unpushed commits, pulls first, and commits only the two data files.
If you ever rerun `build_data.py`, rerun `update_touch_counts.py` afterwards (the build doesn't carry the counts).
The CSV itself is not committed (it includes contacts that aren't on the map).

## Scope notes

- Plant assignment is **best-effort from phone area code**, city-level Nominatim geocodes. Unmapped ACs, toll-free, invalid numbers and no-phone contacts go to **Unassigned**.
- No HubSpot writes from this page; it only links to HubSpot records (plus `tel:` / `mailto:` links, which are not logged).

## Files

| File | Purpose |
|------|---------|
| `index.html` | Dashboard UI |
| `data.json` / `data.js` | Bundled locations + contacts (+ HubSpot touch counts) |
| `geocodes.json` | City geocode cache |
| `build_data.py` | Rebuild script (adds Kaiser to the v1 Arconic data) |
| `called_today.json` | Today's called contact IDs (drives the pulse); refreshed by a scheduled job |
| `update_called_today.py` | Resolves a calls CSV/JSON → `called_today.json`; `--publish` pushes it |
| `update_touch_counts.py` | Applies a HubSpot touch-count CSV → `data.json` + `data.js`; `--publish` pushes them |
