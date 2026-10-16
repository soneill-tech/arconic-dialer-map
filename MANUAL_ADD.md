# Map queue items — manual adds, edits/deletes, titles, follow-ups, last calls

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

## Edit / delete, titles, follow-ups (all typed queue messages)
| `type` | Fields | Effect on the map |
|---|---|---|
| `edit_item` | `target_id` (an `ml-…`/`mc-…` id), `fields` (location: city, state, address, lat, lon, geo_source; contact: name, title, phone, mobile, email, location_id) | Applied in time order on top of the add. Only manual items can be edited. |
| `delete_item` | `target_id` | Removes the manual location/contact (its contacts become unassigned). The tombstone stays in `added_manual.json` so it stays deleted. |
| `set_title` | `contact_id` (HubSpot id or `mc-…`), `title` | Shows the title (labeled "added by …") for contacts with "Title not scraped". Latest wins; empty clears. **Not written to HubSpot.** |
| `followup` | `contact_id`, `due` (YYYY-MM-DD, empty = cleared), `note` | "↩ Follow up Tue 10/20" badge; due/overdue ones appear under **Follow-ups due**. Set from Log Call; "done" clears. Latest wins. |

All are merged by `manual_add.py publish` into `added_manual.json` (the map applies them in `added_at` order), so they outlive ntfy's ~12h cache.

## Last-call history (`last_calls.json`)
`publish` also keeps the **last call per contact** in `last_calls.json` (`{"calls": {contact_id: {time, outcome, am}}}`), merged from queue calls,
`called_today.json`, and optionally `--calls-json rows.json` (rows with `contact_id`, `timestamp`/`time`, `outcome`, `am`, e.g. the sheet's `Calls` tab).
The map shows "Last call: outcome · date" on each contact and colors pins by the most recent call among their contacts:
green = today, yellow = within 6 days, pink = older, grey = never. If you want older history, export `Calls!A:N` to JSON and pass it once.

## Hourly routine (run after the Log Call drain)
1. **Existing ids:** read `'Added Locations'!A2:A` and `'Added Contacts'!A2:A` from sheet
   `1DvmhdoaQMgoWAAbHpQG7gKtovL2fHOmH0Iq1J0FYg3c`; write them one per line to `/tmp/loc_ids.txt` and `/tmp/con_ids.txt`.
   (Tabs are created once with the header rows below; create them if missing.)
2. **Publish for all reps:** `cd <repo> && python3 manual_add.py publish [--calls-json calls.json]` (merges the queue into `added_manual.json`
   and `last_calls.json`, commits + pushes only those files; no-op if nothing new; `--dry-run` to preview).
3. **Rows:** also read `'Manual Changes'!A2:A` into `/tmp/chg_ids.txt`, then
   `python3 manual_add.py rows --existing-locations /tmp/loc_ids.txt --existing-contacts /tmp/con_ids.txt --existing-changes /tmp/chg_ids.txt`
   prints `{"locations":[[…]],"contacts":[[…]],"changes":[[…]]}`. Append them to `Added Locations`, `Added Contacts` and `Manual Changes`
   with the Sheets connector (`append_rows`). Dedupe key = first column.

Headers
- **Added Locations:** `loc_id, created_at, company, city, state, address, lat, lon, geo_source, added_by, logged_at, source, hubspot_synced`
- **Manual Changes:** `change_id, created_at, type, target_id, detail, added_by, logged_at, source, hubspot_synced` (edits, deletes, titles, follow-ups; `detail` is JSON)
- **Added Contacts:** `contact_id, created_at, company, name, title, phone, mobile, email, location_id, location_label, added_by, logged_at, source, hubspot_synced`

`hubspot_synced` stays blank: creating HubSpot companies/contacts is a separate, manual decision (not automated).

## Notes / limits
- Call-log rows for manual contacts have `contact_id` = `mc-…` (no HubSpot record). The HubSpot call writeback in LOGCALL.md must
  **skip rows whose contact_id starts with `mc-`** (mark `hubspot_logged` = `n/a: not in HubSpot`). `update_called_today.py` won't resolve them either; the map still shows them called via the queue for that day.
- Edit/delete exist in the app for manual locations/contacts (✎ / ✕ on the card). Edits/deletes of HubSpot contacts are not possible (titles only).
- Same exposure as Log Call: anyone with the topic name can post or read. Manual adds are shown to all reps as-is.
- Manual contacts are not assigned by area code; they sit at the chosen location (or Unassigned) and appear under All / the company list.

## Hide / restore / relocate any contact (v5)
Reps can **Delete (hide)** or **Relocate** any contact card, including HubSpot-sourced ones. Typed queue messages (same ntfy topic):
`hide_contact {contact_id, contact_name, company}`, `restore_contact {contact_id}`, `move_contact {contact_id, location_id ("" = Unassigned), location_label}`.
Latest message per contact wins (time order). `manual_add.py publish` stores them in `added_manual.json` with the other items and `manual_add.py rows`
lists them in the **Manual Changes** tab (type, target_id = contact id, detail JSON), so the hourly routine needs no new steps: just keep running
`manual_add.py publish` (and `rows` for the sheet). Hidden contacts drop out of counts, filters, pins/pulses and the scoreboard; the **Show → Hidden** view
lists them with **Restore to map**. Delete asks for confirmation. Relocate only moves within the contact's company (non-supplier pins or Unassigned).
**Nothing is ever written to HubSpot** (hide/move are map-only overlays; the HubSpot record is untouched).
