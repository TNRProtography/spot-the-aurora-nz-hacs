# Spot The Aurora NZ

**Aurora forecast for Kiwis, in Home Assistant.**

Tells you plainly whether the aurora is worth going outside for right now,
in 15 minutes, in 30 minutes, in an hour and in two hours — as **Nothing**,
**Camera**, **Phone** or **Eye** — for your actual location, not a national
average.

Install it, click through one screen, and you get a device with all the
sensors plus a map card showing the auroral oval over your house. No YAML,
no resource registration.

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

**Map card**

Registered automatically. Add it from the card picker as **Spot The Aurora
Map**, or in YAML:

```yaml
type: custom:spot-the-aurora-card
```

It draws the oval band, its equatorward and poleward edges, the visibility
view line and a marker at your location.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories**
2. URL: `https://github.com/tnrprotography/spot-the-aurora-nz`, category **Integration**
3. Install, then restart Home Assistant
4. Settings → Devices & Services → **Add Integration** → "Spot The Aurora NZ"

### Manual

Copy `custom_components/spot_the_aurora_nz` into your `config/custom_components`
folder, restart, then add the integration.

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

You can also set the update interval (30–900 seconds, default 60).

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

## Example automation

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

## Data sources

NOAA SWPC and NASA, via the Spot The Aurora workers. Forecast algorithm and
physics by [TNR Protography](https://www.tnrprotography.co.nz).

The map card loads Leaflet and CARTO tiles from the internet; the forecast
itself is computed in Home Assistant.

## Licence

MIT
