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
- Click a pin or card → that location's contacts, sorted **Decision Maker → has phone → name**
- Every contact has an **Open in HubSpot** button (`https://app.hubspot.com/contacts/6029765/record/0-1/<contactId>`, field `hubspot_contact_id`). Open it, then click **Call** in HubSpot so the call is logged. The 📞 `tel:` links dial from your phone and are **not logged**. If a contact ever lacks an ID, the UI falls back to a HubSpot search link.

## Scope notes

- Plant assignment is **best-effort from phone area code**, city-level Nominatim geocodes. Unmapped ACs, toll-free, invalid numbers and no-phone contacts go to **Unassigned**.
- No HubSpot writes from this page; it only links to HubSpot records (plus `tel:` / `mailto:` links, which are not logged).

## Files

| File | Purpose |
|------|---------|
| `index.html` | Dashboard UI |
| `data.json` / `data.js` | Bundled locations + contacts |
| `geocodes.json` | City geocode cache |
| `build_data.py` | Rebuild script (adds Kaiser to the v1 Arconic data) |
