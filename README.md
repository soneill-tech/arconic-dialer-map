# Team Steve — AM Dialer Map

Self-contained HTML map dashboard for Team Steve Closed Won dialer contacts:

| Company | AM | HubSpot | Contacts | w/ phone | Pins |
|---|---|---|---|---|---|
| Arconic | Kahekili Barrozo | `2359249037` | 419 | 168 | 9 (7 plant + 2 supplier) |
| Kaiser Aluminum | Simran Subramanian | `5360206404` | 50 | 26 | 9 |

Live: https://soneill-tech.github.io/arconic-dialer-map/

## Open it

Double-click `index.html` (data is bundled in `data.js`, so `file://` works), or:

```bash
python3 -m http.server 8765   # then open http://localhost:8765/
```

## What's included

- Leaflet + Esri World_Street_Map tiles (no API key)
- **Arconic pins (blue):** Chandler AZ (manual override: Kevin West), Pittsburgh HQ, Davenport Works (Bettendorf, IA), Lafayette, Lancaster (PA), Massena, Tennessee Ops (Alcoa) + All Arconic + Unassigned
- **Arconic supplier pins (blue rounded square, amber border; dashed card + "Supplier (Arconic-managed)" tag):**
  sites Arconic manages that are **not Arconic facilities**. They have no contacts of their own; they reference existing
  Arconic contacts by `hubspot_contact_id`:
  - **Champagne Metals (Middlebury, IN)** (`arc:sup:Middlebury`): Arconic supplier, managed by the Davenport/Bettendorf team; same contacts as Davenport Works / Bettendorf, IA (49)
  - **Minster, OH** (`arc:sup:Minster`): Lancaster, PA (27) ∪ Davenport Works / Bettendorf, IA (49), de-duplicated by ID = 76
    (overlap 0, since each contact has exactly one plant)
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
  All 17 pins pulse (15 plant + 2 supplier); the 309 Unassigned contacts have no pin (their ✓ shows in the list/cards only).
  A contact can sit at several pins (its plant pin plus any supplier pins that list it), and a call to them marks
  **every** one of those pins as called (e.g. a Davenport Works contact checks Davenport Works, Middlebury and Minster).
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

`update_called_today.py` also prints the pins each resolved contact lights up and a **Pins marked called** summary.

## Supplier pins (`sync_supplier_pins.py`)

Supplier locations in `data.json` have `kind: "supplier"`, `is_company_facility: false`, `supplier_tag`,
`contacts_from` (source plant pin ids) and `contact_ids` (the referenced `hubspot_contact_id`s, de-duplicated).
The page's membership check uses `contact_ids` for supplier pins and `plant_id` for plant pins. Contact records are
**not** copied, so touch counts, Open in HubSpot, sorting and the called-today pulse stay consistent, and header /
company / AM totals (counted from `contacts`) don't double count: Arconic stays 419 unique contacts, the team 469.
Supplier pin card counts (49, 76) are those pins' own lists and overlap the plant pins on purpose.

```bash
python3 sync_supplier_pins.py --check   # verify supplier pins are current and data.js == data.json (exit 1 if not)
python3 sync_supplier_pins.py           # (re)insert supplier pins, recompute contact_ids + stats, write both files
```

Supplier definitions (city, geocode, source pins) live at the top of the script. Rerun it after anything that changes
plant assignments (e.g. a rebuild); touch-count and called-today refreshes don't need it.

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
If you ever rerun `build_data.py`, rerun `update_touch_counts.py` and `sync_supplier_pins.py` afterwards (the build
carries neither the counts nor the supplier pins). Supplier pins pick up new counts automatically (same contact records).
The CSV itself is not committed (it includes contacts that aren't on the map).

## Scope notes

- Supplier pin contacts are assigned by request (Steve, 2026-10-06), not by area code.
- Plant assignment is **best-effort from phone area code**, city-level Nominatim geocodes. Unmapped ACs, toll-free, invalid numbers and no-phone contacts go to **Unassigned**.
- No HubSpot writes from this page; it only links to HubSpot records (plus `tel:` / `mailto:` links, which are not logged).

## Files

| File | Purpose |
|------|---------|
| `index.html` | Dashboard UI |
| `data.json` / `data.js` | Bundled locations + contacts (+ HubSpot touch counts) |
| `geocodes.json` | City geocode cache (incl. supplier cities) |
| `build_data.py` | Rebuild script (adds Kaiser to the v1 Arconic data) |
| `apply_site_overrides.py` | Adds manual plant pins + contact→plant overrides (Arconic Chandler, AZ ← Kevin West 37695051; **Reliable Silver** (Kahekili, HubSpot company 7228584362): Naugatuck, CT pin + 7 contacts; Kaiser Richmond (Bellwood), VA pin, contacts only by 804 area code (none today); **BRT Extrusions, Niles OH** pin under Simran (HubSpot company 3005488807, teal ring) with 9 contacts, Amanda Zepernick flagged primary POC); idempotent; also adds **Howmet Aerospace** (Kahekili, HubSpot company 32027566669): All Howmet + Pittsburgh HQ pin + area-code pins 216/219/585/231 (only codes with ≥6 contacts) + Unassigned, from `howmet_contacts.json` |
| `build_howmet_contacts.py` | CSV → `howmet_contacts.json` (display names from emails, normalized phones) |
| `sync_supplier_pins.py` | Adds/refreshes the Arconic-managed supplier pins (Champagne Metals Middlebury IN + Glenpool OK, Minster OH); `--check` verifies |
| `called_today.json` | Today's called contact IDs (drives the pulse); refreshed by a scheduled job |
| `update_called_today.py` | Resolves a calls CSV/JSON → `called_today.json`; `--publish` pushes it |
| `manual_add.py` / `added_manual.json` / `last_calls.json` | Drains queue items (adds/edits/deletes/titles/follow-ups) and last-call history; both files are merged into the map on load |
| `apply_touches_ytd.py` | Applies a `contact_id,touches_ytd` CSV (2026 activity counts) to `data.json` + `data.js` |
| `update_touch_counts.py` | Applies a HubSpot touch-count CSV → `data.json` + `data.js`; `--publish` pushes them |


## Log Call
Green **Log Call** button per contact → shared call log (ntfy.sh queue → Google Sheet "AM Dialer Call Log"), with a localStorage fallback. See [LOGCALL.md](LOGCALL.md). `logcall_rows.py` prints new rows for the sheet.

## Manual add (＋ Location / ＋ Contact)
Reps can add a new location pin or a new contact from the map header (badge **Added manually**, **Not in HubSpot yet**). Same ntfy queue as Log Call, typed `add_location` / `add_contact`; `manual_add.py` drains it to `added_manual.json` + the sheet tabs *Added Locations* / *Added Contacts*. See [MANUAL_ADD.md](MANUAL_ADD.md).

## Dialer features (v3)
- **Filters:** *Show: All / Not called today / Not called this week (since Monday, CT) / Not called this month (since the 1st, CT) / Follow-ups due* above the contact list (works with the All/Kahekili/Simran tabs; uncalled sorts by most touches).
- **Tap-to-call:** phone/mobile are large `tel:` buttons; when you return to the page Log Call opens prefilled for that contact (duration estimated from time away).
- **Last call + follow-ups:** each card shows *Last call: outcome · date* (from `last_calls.json`, today's calls, and the queue); Log Call has an optional **Follow up** date, shown as a badge, cleared with *done*.
- **Titles:** "Title not scraped" contacts get an inline *Add title* (saved via the queue, labeled "added by", not written to HubSpot).
- **Scoreboard** in the header: contacts called today per AM. **Called today** green ribbon on cards.
- **Pins:** smaller; fill = last-call recency (today / this week / older / never), ring = company, pulse = not called today. Legend is collapsible (collapsed on small screens).
- **Layout:** Unassigned contacts are a collapsible group in the locations list; contact cards are grouped by company with sticky headers.
- **Edit/delete** manual locations/contacts. Queue types and sync steps: [MANUAL_ADD.md](MANUAL_ADD.md).

**Last-called day** (week/month filters) = latest of `last_calls.json` (history only as far back as seeded + hourly publishes), today's `called_today.json`, the Log Call queue, and HubSpot `last_contacted` (which also counts emails/meetings). No data = never called = included. Manual contacts count as never called until a call is logged.

## Touches this year (sort + card badge)
Sort **Most touches this year** (alongside *Most contacted*) works with the Not called today/week/month filters and shows a yellow
"N this year" badge per card from the `touches_ytd` field. **Data status: not loaded.** `times_contacted` / `sales_activities` are
all-time counts with no per-activity dates, so a since-Jan-1-2026 count can't be derived from `contact_touch_counts.csv`, `called_today.json`
or `last_calls.json`. Until it's loaded the sort falls back to all-time touches and cards show "this year: not loaded".
**Needed:** a HubSpot activity export for 2026 (calls + emails + meetings, 2026-01-01 → today, counted per contact) as CSV `contact_id,touches_ytd`, then:
`python3 apply_touches_ytd.py ytd.csv --as-of <ISO> --source "<how pulled>"` (updates `data.json` + `data.js`; commit/push them). Re-run it periodically; the sync scripts leave `touches_ytd` alone.

## Weather radar overlay
Top-right **Radar** toggle + opacity slider (off by default; choice remembered per device). Uses RainViewer's free public API (`api.rainviewer.com/public/weather-maps.json`, latest radar frame, auto-refresh every 10 min, attribution "Radar © RainViewer"). Drawn in its own pane above the basemap and below pins/popups, so it works with the AM filter and pins. If the API or tiles fail it shows "Radar unavailable right now" and the map is unaffected. Radar tiles are native to zoom 7 and upscale beyond that.

## Look & layout (v4)
- **Basemap**: dark Esri Dark Gray Canvas + labels layer (CARTO dark tiles now require an API key, so not used). Radar (RainViewer) sits between base and labels.
- **Clusters**: Leaflet.markercluster numbered bubbles (ring color = company, pulse if any child pin was not called today); pins stay individual from zoom 10.
- **Cards**: name, title, big tap-to-call button first, then one wrapping badge row (manual, POC, touches, this year, last call, follow-up). Company ring color = thin left stripe on contact cards and location entries.
- **Header**: one filter bar, `＋ Add` menu (new location / new contact), scoreboard visible. On the All tab a navy-to-burgundy strip ties the Cowboys star and burgundy ribbon together.
- **Mobile (<=900px)**: map on top, bottom sheet with Locations / Contacts tabs (peek / half / full), 40px+ touch targets.
- **Howmet supplier pins**: `how:sup:Mogadore` (contacts with area code 330/234: 4) and `how:sup:Laredo` (956: none yet) are supplier squares defined in `apply_site_overrides.py` (`HOWMET_SUPPLIERS`); they reference existing contacts only.
- **Basemap toggle**: Light (Esri World Street, default) / Dark (Esri Dark Gray + labels) segmented control in the Radar box; choice saved per device in localStorage (`dialerBasemap:v1`). Layer order: base < radar < labels < pins.
- **Howmet Tucson, AZ** plant pin (`how:Tucson`): contacts John Fox (3192251) and Miguel Angulo (4526951) assigned by explicit `OVERRIDES` in `apply_site_overrides.py`.

## v5
- **Kawneer** (Simran, HubSpot 8178764938): 21 contacts from `kili_contacts.csv` (`build_howmet_contacts.py <csv> kawneer` -> `kawneer_contacts.json`), `All Kawneer`, `Norcross, GA` pin (area code 770 on 11 contacts), `Kawneer corporate office` pin in Newnan, GA that cross-references Paul Laslou (an Arconic DM, not moved; `cross_company` + `contact_ids`). Notes kept. Not shown on the Kahekili tab.
- **Hide / Restore / Relocate** any contact (queue types `hide_contact`, `restore_contact`, `move_contact`, see MANUAL_ADD.md). Map-only; nothing is written to HubSpot.
- **Scorebug** header scoreboard (KILI navy / SIMRAN burgundy, pop animation on change, CT clock + last sync strip; compact single bar under 900px).
- **Dark mode borders**: `assets/borders.json` (US states + country lines, Natural-Earth-style simplified) in a pane above radar/labels and below pins; hidden in Light mode.

## v6
- **Cards | List** toggle at the top of the left panel (remembered per device, `dialerLocView:v1`): flat compact location rows (company stripe, name, city/state, pin type Plant/Supplier/HQ, called-today badge, contact count), Rep seg (synced with the top tabs), Account chips built from `DATA.companies` (filtered to the selected rep), and name search. Clicking a row = `selectLoc` like cards. Works in the mobile bottom sheet.
- **Scorebug** is ~30% larger; saving a Log Call (successful POST, non-test) fires a canvas fireworks burst over that AM's score (Kili navy/silver/white, Simran burgundy/gold; pointer-events none; skipped for prefers-reduced-motion, page load, other reps' synced calls, test rows).
- **Relocate** can now move a contact to any customer + location (`move_contact.company_to`), display-only; **Reset location** (`reset_move`) undoes it. See MANUAL_ADD.md.

## Header sizing (v6.1)
Header is part of the flex column (no fixed/sticky): ~75-95px on desktop (was ~142-179px), single row with title | scorebug | stats + filters; map and side panels fill the rest and scroll internally; layout stays 3-column down to 901px; below 900px the mobile bottom-sheet layout applies. Short viewports (<=760px high) shrink the scorebug and drop the strip/sub-title. The page scrolls to top on load (scroll restoration off).
- **No document scroll (v6.2)**: `html`/`body` are `100dvh`, `overflow:hidden`, body is `position:fixed; inset:0` (flex column: header, layout, footer); only the panels/lists scroll internally. All `focus()` calls use `preventScroll`, and a scroll listener resets any stray document scroll to (0,0) (`documentElement.scrollHeight == clientHeight`).
- **Account scopes the map (v6.3)**: picking an account chip (List view) or an "All <company>" entry (Cards or List) shows only that company's pins (supplier pins carry their own company) and fits the map to them; "All"/"All companies"/the map pill's "Show all" restores everything. Combines with the Rep tabs (a company outside the selected rep clears the scope), radar/borders overlays, clusters and recency colors. Active chip is marked with a check + ring, and a pill on the map says "Map: <company> only".
- **Champagne Metals (Glenpool, OK)** is an Arconic-managed supplier pin (`arc:sup:Glenpool`, defined in `sync_supplier_pins.py`, run by `apply_site_overrides.py`) referencing the same 49 contacts as Middlebury, IN (Davenport Works / Bettendorf). References only, no duplicate contacts; map only. Arconic now has 10 pins (7 plant + 3 supplier).
- **Champagne Metals** has two Arconic suppliers, **Middlebury, IN** and **Glenpool, OK** (labels "Champagne Metals (Middlebury, IN)" / "Champagne Metals (Glenpool, OK)"), both tagged "Arconic supplier, managed by the Davenport/Bettendorf team" (`supplier_tag`, shown on cards and in popups) and both referencing the 49 Davenport Works/Bettendorf contacts. Minster, OH is unchanged.

## Nick / Mia / Addie (HubSpot Closed Won accounts)

Tabs for Nick (Nicholas McNamara), Mia (Mia Medjedovic) and Addie (Addison Parker) show **only** their HubSpot Closed Won companies,
contacts and locations (map-only; nothing is ever written to HubSpot). They are built by `rep_loader.py` (called from
`apply_site_overrides.py`) from `/workspace/{nick,mia,addie}-closed-won/{companies,contacts}.csv`:

```bash
python3 apply_site_overrides.py              # re-runnable / idempotent: rebuilds the three reps' records from the CSVs; Kili/Simran data untouched
python3 apply_site_overrides.py --no-geocode # use only cached geocodes (rep_geocodes.json)
REP_DATA_DIR=/path python3 apply_site_overrides.py
```

- One pin per company address (Nominatim, 1 req/s, cached in `rep_geocodes.json`; street -> city/state fallback). Companies with no address go to
  that company's **Unassigned** entry. Companies with contacts in >= 3 cities (plus Boart Longyear, 3M, True Manufacturing, Novelis, Engie) get one pin per
  distinct contact city; contacts with no city sit at the company-address pin. 3M has two DeKalb IL DC pins (DKC 1250 Macom Dr, DK6 1650 Macom Dr).
- Bad HubSpot addresses are corrected in the `MANUAL` table of `rep_loader.py`; each correction is shown as a flag on the pin and listed in `rep_load_report.json`
  (with skipped contacts, companies without contacts, geocode failures).
- The Kili vs Simran scorebug is unchanged; Nick/Mia/Addie call counts are appended to the "Called today" badge once they have calls. `update_called_today.py` accepts Nick/Mia/Addie as `am`.
