# Log Call — design note

Approved by Steve O'Neill 2026-10-14 4:32 PM CT. Each contact on the map has a green **✎ Log Call** button next to
**Open in HubSpot**. It opens a modal with AM (Kili/Simran), date/time (defaults to now), outcome, Outbound/Inbound,
duration, and notes. Save marks the contact *Called today ✓ time · outcome* and stops the pulse on its pin(s).
**Nothing in this feature writes to HubSpot.**

## Storage (live today)
GitHub Pages is static and can't hold secrets, so the browser can't write to a Google Sheet directly unless an Apps
Script web app is deployed, and that deploy needs Steve's Google authorization. The live map uses:

1. **Shared write/read queue: ntfy.sh topic `tsdm-calllog-ddbdae3e678c14eb`** (free, no account, CORS-enabled, no token).
   Save = `POST https://ntfy.sh/tsdm-calllog-ddbdae3e678c14eb` with the call JSON as the body. On load and every 5 min, the map reads
   `GET …/json?poll=1&since=all`, keeps today's calls (CT), and merges them into `called_today.json` (latest call per contact wins).
   ntfy `message_delete` events are honored. ntfy.sh only **keeps messages for about 12 hours**, so this is a queue, not the record.
2. **Durable record: Google Sheet "AM Dialer Call Log"**
   (https://docs.google.com/spreadsheets/d/1DvmhdoaQMgoWAAbHpQG7gKtovL2fHOmH0Iq1J0FYg3c/edit), tab `Calls`. Columns:
   `call_id, timestamp (ISO UTC), am, contact_id, contact_name, company_location, phone, outcome, direction, duration_min, notes, logged_at, source, hubspot_logged`.
   The hourly sync copies new queue entries in: `python3 logcall_rows.py --existing <call_ids already in sheet>`
   prints the new rows, and the agent appends them with the Sheets connector (`append_rows`). Dedupe key: `call_id`.
3. **localStorage fallback**: every save is cached on the device. If the POST fails, the call goes to
   `dialerLogPending:v1`, shows as called on that device (tooltip: "saved on this device only"), and is re-posted on the next load or refresh.

Privacy: the topic name is unguessable, but anyone who knows it can read or post to it. Call notes should be treated as semi-public.
That's the same exposure as the contact data already in public `data.json`.

## Next step: HubSpot writeback in the hourly sync (not built yet)
1. Drain the queue: run `logcall_rows.py` with the sheet's existing `call_id`s, then append the new rows to `Calls` (hubspot_logged blank).
2. Read `Calls!A:N` and select rows where `hubspot_logged` is blank. Skip rows whose notes start with `TEST`.
3. For each row, open the contact (`https://app.hubspot.com/contacts/6029765/record/0-1/<contact_id>`) in the browser session → **Log activity → Log call**.
   Set the outcome (Connected / Left voicemail / No answer / Wrong number / Busy), direction, date/time (convert the ISO timestamp to CT), and duration.
   Body: `<notes> — logged via Dialer Map by <am> (call_id <call_id>)`. Including call_id lets you spot duplicates in HubSpot before retrying.
4. Right after each successful log, write `hubspot_logged` = `<ISO time CT> by sync` (or `ERROR: …` and leave it for the next run) for that row only.
   Mark rows one at a time so a crash mid-run doesn't double-log.
5. Feed the logged calls into `update_called_today.py` as usual. Map-logged calls already show on the map, so this is only for consistency.
