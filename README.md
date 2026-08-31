# Spot The Aurora NZ

**Aurora forecast, space weather and CME tracking for Kiwis, in Home Assistant.**

Tells you plainly whether the aurora is worth going outside for right now,
in 15 minutes, in 30 minutes, in an hour and in two hours — as **Nothing**,
**Camera**, **Phone** or **Eye** — for your actual location, not a national
average. Alongside that: NASA's live CME and solar flare catalog, GOES X-ray
flux, proton flux from three independent spacecraft, and every community
aurora sighting plotted on a map - all as Home Assistant entities you can
automate on.

Install it, click through one screen, and you get a device with all the
sensors plus a full dashboard - oval map, 3-day forecast, CME and flare
lists, a reportings map, solar imagery - laid out for you. No YAML, no
resource registration.

![screenshot](docs/screenshot.png)

## What you get

**Visibility forecast**

| Sensor | Tells you |
|---|---|
| `sensor.visibility_now` | What you'd see if you walked outside now |
| `sensor.visibility_15_minutes` | 15 minutes ahead |
| `sensor.visibility_30_minutes` | 30 minutes ahead |
| `sensor.visibility_1_hour` | An hour ahead |
| `sensor.visibility_2_hours` | Two hours ahead |

Each reads `Nothing`, `Camera`, `Phone` or `Eye`, with the numeric score as
an attribute.

**Solar wind and geomagnetic data**

IMF Bz, Bt, Bz 30-minute average, By 30-minute average, solar wind speed,
density, dynamic pressure, Newell coupling (plus 30 and 60-minute averages),
southward minutes, hemispheric power, substorm score, level, trend,
confidence, moon illumination and L1 propagation delay.

**CMEs and solar flares**

`sensor.cme_count` and `sensor.solar_flare_count` track NASA DONKI's live
catalog. Each carries the full recent list as an attribute (`cmes` /
`flares`) - speed, source location, whether it's Earth-directed, predicted
shock arrival time, flare class and peak time - so you can template on it,
or just read the dashboard's CME and flare list cards.

**X-ray flux and proton flux**

`sensor.x_ray_flux_long_band` (with the short band and derived A/B/C/M/X
flare class as attributes) from GOES, plus one proton flux sensor per L1
spacecraft - `sensor.proton_flux_solar_1`, `sensor.proton_flux_ace` and
`sensor.proton_flux_imap` - each with its full energy-channel spectrum
(47 keV to 1.9 MeV) in the attributes.

**Aurora reportings, on a map, gone by midday**

Every sighting the community submits shows up as a `geo_location` entity -
which means it's automatically on any Lovelace **Map** card with
`geo_location_sources: [spot_the_aurora_nz]` (the dashboard's map is already
set up this way), each with a distance and a name you can hover or tap.
`sensor.aurora_sightings_today` carries the full list as an attribute for a
plain-text view. Like the live site, this resets every day at midday NZ
time - reportings are for "tonight", so once local noon passes the list (and
the map) empties out and starts collecting again.

**Automating on how close a reporting is**

Every reporting entity's *state* is its distance from you in kilometres (a
plain `numeric_state` trigger works), and `sensor.closest_sighting_distance`
+ `sensor.closest_sighting_latitude_difference` track the nearest one at all
times. The latitude version matters more for aurora than raw distance -
someone 400 km away but at the same latitude as you tells you far more than
someone 50 km away but well to your north - see the example automation
below.

**A ready-made dashboard**

An **Aurora** item appears in your sidebar with the oval map, the 3-day
forecast, the visibility forecast, solar wind readings, X-ray/proton flux,
a reportings map, CME and flare lists, solar imagery and history graphs
already laid out. Nothing to configure. Turn it off during setup if you'd
rather build your own.

**Map card**

Registered automatically. Add it from the card picker as **Spot The Aurora
Map**, or in YAML:

```yaml
type: custom:spot-the-aurora-card
```

It draws the oval band, its equatorward and poleward edges, the visibility
view line and a marker at your location, with a five-slot forecast strip
underneath and a line telling you how far the view line sits from you.

Card options, all optional:

| Option | Default | Notes |
|---|---|---|
| `title` | `Spot The Aurora` | Card heading |
| `basemap` | `osm` | `osm`, `terrain`, `satellite` or `none` |
| `dark` | `true` | Dims and desaturates the basemap |
| `show_logo` | `true` | Logo in the header |
| `show_forecast` | `true` | The five-slot strip under the map |
| `height` | `420px` | Map height |
| `zoom` | `4` | Initial zoom, before auto-fit |
| `entity` | auto | Override the aurora score sensor |
| `visibility_entity` | auto | Override the visibility sensor |

All basemaps are keyless. CARTO is deliberately not offered — it now
watermarks unkeyed requests.

## Installation

### HACS

1. HACS → ⋮ (top right) → **Custom repositories**
2. URL: `https://github.com/tnrprotography/spot-the-aurora-nz-hacs`, category **Integration**
3. Find **Spot The Aurora NZ** in HACS and click **Download**
4. Restart Home Assistant
5. Settings → Devices & Services → **Add Integration** → search "Spot The Aurora NZ"
6. Pick how it should know your location (see below) and finish the wizard

No YAML and no dashboard resource to register by hand - the sensors, the
map card and the sidebar dashboard all set themselves up.

### Manual

1. Copy `custom_components/spot_the_aurora_nz` into your
   `config/custom_components` folder (so you end up with
   `config/custom_components/spot_the_aurora_nz/manifest.json`)
2. Restart Home Assistant
3. Settings → Devices & Services → **Add Integration** → search "Spot The Aurora NZ"

### Updating

HACS: **Update** whenever a new release shows. Manual installs: replace the
`custom_components/spot_the_aurora_nz` folder with the new version and
restart - your configuration (location mode, scan interval) is untouched.

## Choosing your location

Setup asks how the forecast should work out where you are. Three options:

**Use my Home Assistant location** — reads the coordinates you already set
in HA. Nothing to type.

**Follow a device or person** — pick a `device_tracker`, `person` or `zone`.
The forecast recalculates the moment it reports a new position, so if you
drive from town out to a dark sky site, your visibility numbers follow you.
If the tracker drops out or has no GPS fix, it falls back to your home
location rather than losing the forecast.

**Pick a spot on the map** — drag a marker to your usual viewing spot. Handy
if you always shoot from somewhere other than home.

You can also set the update interval (30–900 seconds, default 60) and choose
whether to create the Aurora dashboard in your sidebar.

Change any of it later via **Configure** on the integration — same three
options.

### Why it matters

On a moderate night with the view line at −48.3° geomagnetic:

| Location | Geomagnetic latitude | Result |
|---|---|---|
| Auckland | −39.9° | Nothing |
| Wellington | −44.3° | Nothing |
| Christchurch | −46.8° | Nothing (heavily damped) |
| Queenstown | −48.9° | Phone |
| Invercargill | −50.3° | Phone |

Same national data, five different answers.

## Why location matters

The auroral oval is a ring around the geomagnetic pole, so what you can see
depends on your geomagnetic latitude, not your geographic one. Christchurch
sits at about −46.8° geomagnetic; Auckland is around −41°. On a night when
the view line reaches −50°, Christchurch sees a display and Auckland sees
nothing.

This integration computes the oval boundary from live coupling and pressure
data, works out where the visibility line falls, and scales your score down
if you're north of it. Two people running this in different parts of the
country get genuinely different answers.

## How the forecast works

The equatorward oval boundary comes from a Newell coupling base law with
dynamic pressure expansion and Russell-McPherron seasonal weighting:

```
boundary  = -(65.5 - newell / 1800)
boundary += 0.9 x log2(pressure / 2 nPa)    clamped to [-1, +3] degrees
boundary  = clamp(boundary, -76, -44)
```

The view line sits at `boundary + 9° + (score / 100) x 16°`, reflecting the
higher emission altitude during active periods.

Projections apply a trend multiplier from the substorm risk trend, a boost
when Newell coupling is accelerating past its 30-minute average, and a
confidence dampener. All scores are forced to zero during daylight.

The two-hour slot uses the Spot The Aurora composite score rather than the
substorm projection, since substorm signals don't carry that far.

## Example automations

```yaml
automation:
  - alias: Aurora visible to the eye
    triggers:
      - trigger: state
        entity_id: sensor.visibility_now
        to: "Eye"
    actions:
      - action: notify.mobile_app
        data:
          title: Aurora visible now
          message: >
            Look south - score {{ state_attr('sensor.aurora_score','score_now') }}%
```

Notify when someone reports the aurora at roughly your latitude (so it's
plausible from your house too), even if they're a fair distance east or west:

```yaml
automation:
  - alias: Aurora reported near my latitude
    triggers:
      - trigger: numeric_state
        entity_id: sensor.closest_sighting_latitude_difference
        below: 1.5
    actions:
      - action: notify.mobile_app
        data:
          title: Aurora reported near your latitude
          message: >
            {{ state_attr('sensor.closest_sighting_latitude_difference', 'closest_sighting').name }}
            reported {{ state_attr('sensor.closest_sighting_latitude_difference', 'closest_sighting').status_label }},
            {{ states('sensor.closest_sighting_distance') }} km away.
```

Or trigger on any single reporting entity directly - its state is distance
in km from you:

```yaml
automation:
  - alias: A reporting appeared within 100km
    triggers:
      - trigger: geo_location
        source: spot_the_aurora_nz
        zone: zone.home
        event: enter
    actions:
      - action: notify.mobile_app
        data:
          message: New aurora reporting within your home zone's radius.
```

## Data sources

NOAA SWPC (Kp forecast, X-ray flux, solar wind) and NASA (DONKI CME/flare
catalog, SDO and SOHO imagery), via the Spot The Aurora workers. Proton flux
from the SOLAR-1, ACE and IMAP spacecraft. Community aurora reportings and
the forecast algorithm from [Spot The Aurora](https://www.spottheaurora.co.nz),
physics by [TNR Protography](https://www.tnrprotography.co.nz).

The map card loads Leaflet and CARTO tiles from the internet; the forecast
itself is computed in Home Assistant. Solar imagery cards load images
directly from `sdo.gsfc.nasa.gov` and `soho.nascom.nasa.gov` and refresh
when the dashboard reloads, not continuously.

## What this doesn't include

The web app's full 3D CME propagation simulation (Three.js, animated
timelines, GIF export) isn't ported here - Lovelace cards aren't a great
home for a 3D physics sim, and it wouldn't add much over the numbers
themselves. This integration gives you the same underlying data (CME
speed, direction, Earth-directed flag, predicted arrival) as sensors and a
dashboard list instead, which is what automations and glanceable dashboards
actually need.

## Licence

MIT
