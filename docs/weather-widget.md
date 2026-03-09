# Weather Widget

## METAR API

**Endpoint:** `https://aviationweather.gov/api/data/metar?ids={station}&format=json`

- No API key required
- Returns JSON array of METAR observations
- We use the first element (most recent)

### Response Fields Used

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `icaoId` | str | "KIAH" | Airport ICAO code |
| `name` | str | "George Bush Intercontinental" | Airport name |
| `temp` | int | 22 | Temperature in Celsius |
| `wdir` | int | 270 | Wind direction in degrees |
| `wspd` | int | 12 | Wind speed in knots |
| `wgst` | int/null | 25 | Gust speed in knots |
| `visib` | float | 10 | Visibility in statute miles |
| `fltcat` | str | "VFR" | Flight category |
| `clouds` | list | `[{"cover":"FEW","base":5000}]` | Cloud layers |
| `wxString` | str/null | "RA BR" | Weather phenomena |
| `rawOb` | str | "KIAH 091453Z..." | Raw METAR text |

## Weather Icon Mapping

Priority order (first match wins):

1. **Precipitation** (from `wxString`):
   - `TS` -> thunderstorm
   - `SN` -> snow
   - `RA` -> rain
   - `FG` -> fog

2. **Cloud cover** (from highest cloud layer):
   - `SKC`/`CLR` -> sunny
   - `FEW`/`SCT` -> partly_cloudy
   - `BKN` -> mostly_cloudy
   - `OVC` -> overcast

3. **Default:** sunny (no clouds reported)

## Screen Layout

Top-to-bottom on 135x240 black background:

1. Station code (white, centered)
2. Station name (gray, centered, truncated at 20 chars)
3. Weather icon (drawn with PIL shapes)
4. Temperature (white, imperial: F, metric: C)
5. Wind direction + speed (white, includes gust if present)
6. Visibility in SM (white)
7. Flight category (color-coded: VFR=green, MVFR=blue, IFR=red, LIFR=magenta)
8. Raw METAR text (gray, word-wrapped)

## Error Display

`render_error_screen(message)` shows red text centered on black background. Used by the daemon when METAR fetch fails with no cached image.
