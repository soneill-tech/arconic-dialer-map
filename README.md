# Arconic Dialer Map (Team Steve)

Self-contained HTML map dashboard for **Arconic** Closed Won dialer contacts (Kahekili Barrozo).

## Open it

**Option A — local file**

```bash
open /workspace/kili-simran-closed-won/map-dashboard/index.html
```

Or double-click `index.html`. Contact data is bundled in `data.js` + `data.json` so `file://` works without a server.

**Option B — simple static server (recommended)**

```bash
cd /workspace/kili-simran-closed-won/map-dashboard
python3 -m http.server 8765
```

Then open http://localhost:8765/

## What’s included

- Leaflet + Carto dark basemap (OSM data; no API key)
- **6 plant/city pins** (city-level Nominatim geocodes): Pittsburgh HQ, Davenport Works, Lafayette, Lancaster, Massena, Tennessee Ops (Alcoa)
- Side location list + contact panel (name, role, phone, mobile, email, HubSpot link)
- Contacts sorted: **Decision Maker → has phone → name**
- AM filter (All / Kahekili / Simran) and search
- Large clickable cards in the sidebar if the map is unused

## Scope notes

- **Arconic only** (HubSpot company `2359249037`)
- 419 contacts from `Kahekili_Barrozo_dialer.csv`
- Plant assignment is **best-effort from phone area code** (e.g. 563→Davenport, 717→Lancaster). Contacts without a mapped AC are under **Unassigned**
- No HubSpot writes, no dialing from this page beyond `tel:` / `mailto:` links

## Files

| File | Purpose |
|------|---------|
| `index.html` | Dashboard UI |
| `data.json` | Bundled locations + contacts |
| `geocodes.json` | City geocode cache |
| `README.md` | This file |
