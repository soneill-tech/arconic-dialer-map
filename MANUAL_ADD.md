# Manual add — new locations and contacts from the map

Reps (Kili, Simran) can add a **＋ Location** (company Arconic/Kaiser, city, state, optional address) or a **＋ Contact**
(name, title, phone, mobile, email, optional location) from the map header. **Nothing is written to HubSpot.**
Added items show an **Added manually** badge; manual contacts show **Not in HubSpot yet** instead of *Open in HubSpot*,
and **Log Call still works** on them (their id is `mc-…`, used as the call's `contact_id`).

## How it works
- **Location pin:** the browser geocodes city/state (and address if given) with Nominatim. If that fails, or the pin is
  wrong, **Drop pin manually** lets the rep click the map. Duplicate check: confirms if the same company already has a pin within ~0.1°.
- **Save:** `POST https://ntfy.sh/tsdm-calllog-ddbdae3e678c14eb` (same queue as Log Call) with JSON whose `type` is
  `add_location` or `add_contact` and an `id` (`ml-…` / `mc-…`). Log Call readers need `call_id` and skip typed messages;
  the manual-add readers only take typed messages. Also cached in localStorage (`dialerAddCache:v1`); if the POST fails it
  goes to `dialerAddPending:v1` and is re-posted on the next load.
- **Read/merge:** on load and every 5 min the map merges, by `id`: `added_manual.json` (durable, committed), the ntfy queue
  (~12h), and localStorage. ntfy `message_delete` events are honored.
- ntfy only keeps ~12h, so the hourly sync **must** publish new items into `added_manual.json` (step 2) or they vanish for other reps.

Item shapes
```json
{"type":"add_location","id":"ml-…","company":"Arconic","city":"Chandler","state":"AZ","address":"","lat":33.3062,"lon":-111.8412,
 "geo_source":"nominatim|manual-pin","added_by":"Kili","added_at":"<ISO UTC>","source":"dialer-map"}
{"type":"add_contact","id":"mc-…","company":"Arconic","name":"…","title":"","phone":"","mobile":"","email":"",
 "location_id":"arc:Lancaster | ml-… | ''","location_label":"","added_by":"Simran","added_at":"<ISO UTC>","source":"dialer-map"}
```

## Hourly routine (run after the Log Call drain)
1. **Existing ids:** read `'Added Locations'!A2:A` and `'Added Contacts'!A2:A` from sheet
   `1DvmhdoaQMgoWAAbHpQG7gKtovL2fHOmH0Iq1J0FYg3c`; write them one per line to `/tmp/loc_ids.txt` and `/tmp/con_ids.txt`.
   (Tabs are created once with the header rows below; create them if missing.)
2. **Publish for all reps:** `cd <repo> && python3 manual_add.py publish` (merges the queue into `added_manual.json`,
   commits + pushes only that file; no-op if nothing new; `--dry-run` to preview).
3. **Rows:** `python3 manual_add.py rows --existing-locations /tmp/loc_ids.txt --existing-contacts /tmp/con_ids.txt`
   prints `{"locations":[[…]],"contacts":[[…]]}`. Append `locations` to `Added Locations` and `contacts` to `Added Contacts`
   with the Sheets connector (`append_rows`). Dedupe key = first column.

Headers
- **Added Locations:** `loc_id, created_at, company, city, state, address, lat, lon, geo_source, added_by, logged_at, source, hubspot_synced`
- **Added Contacts:** `contact_id, created_at, company, name, title, phone, mobile, email, location_id, location_label, added_by, logged_at, source, hubspot_synced`

`hubspot_synced` stays blank: creating HubSpot companies/contacts is a separate, manual decision (not automated).

## Notes / limits
- Call-log rows for manual contacts have `contact_id` = `mc-…` (no HubSpot record). The HubSpot call writeback in LOGCALL.md must
  **skip rows whose contact_id starts with `mc-`** (mark `hubspot_logged` = `n/a: not in HubSpot`). `update_called_today.py` won't resolve them either; the map still shows them called via the queue for that day.
- No in-app edit/delete. To remove a bad entry: delete its message from ntfy (if still there) **and** remove its object from `added_manual.json`, then push.
- Same exposure as Log Call: anyone with the topic name can post or read. Manual adds are shown to all reps as-is.
- Manual contacts are not assigned by area code; they sit at the chosen location (or Unassigned) and appear under All / the company list.
