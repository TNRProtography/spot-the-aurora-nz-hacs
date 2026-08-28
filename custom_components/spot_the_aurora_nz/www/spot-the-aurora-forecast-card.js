/**
 * Spot The Aurora NZ - 3 day forecast card
 *
 * A 72 hour timeline of what the southern sky may look like: day/night
 * shading from computed solar elevation, moonrise and moonset markers with
 * the correct phase, and aurora bars sized against the Kp needed to see
 * anything from your latitude.
 *
 * Kp comes from NOAA SWPC via the integration. Sun and moon positions are
 * computed locally, so the card works without any extra data source.
 */

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

// --- Solar position (NOAA solar calculator, simplified) --------------------

function julianDay(date) {
  return date.getTime() / 86400000 + 2440587.5;
}

function solarElevation(date, lat, lon) {
  const jd = julianDay(date);
  const n = jd - 2451545.0;
  const L = (280.46 + 0.9856474 * n) % 360;
  const g = ((357.528 + 0.9856003 * n) % 360) * D2R;
  const lambda =
    (L + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * D2R;
  const epsilon = (23.439 - 0.0000004 * n) * D2R;

  const dec = Math.asin(Math.sin(epsilon) * Math.sin(lambda));
  let ra = Math.atan2(
    Math.cos(epsilon) * Math.sin(lambda),
    Math.cos(lambda)
  );
  ra = (ra * R2D + 360) % 360;

  const gmst = (18.697374558 + 24.06570982441908 * n) % 24;
  const lst = (gmst * 15 + lon + 360) % 360;
  const ha = ((lst - ra + 540) % 360) - 180;

  const phi = lat * D2R;
  const sinAlt =
    Math.sin(phi) * Math.sin(dec) +
    Math.cos(phi) * Math.cos(dec) * Math.cos(ha * D2R);
  return Math.asin(Math.max(-1, Math.min(1, sinAlt))) * R2D;
}

// --- Lunar position and phase (Meeus, low precision) -----------------------

function moonState(date, lat, lon) {
  const jd = julianDay(date);
  const T = (jd - 2451545.0) / 36525.0;

  const Lp = (218.316 + 481267.8813 * T) * D2R;      // mean longitude
  const M = (357.529 + 35999.0503 * T) * D2R;        // sun mean anomaly
  const Mp = (134.963 + 477198.8676 * T) * D2R;      // moon mean anomaly
  const D = (297.850 + 445267.1115 * T) * D2R;       // mean elongation
  const F = (93.272 + 483202.0175 * T) * D2R;        // argument of latitude

  const lambda =
    Lp +
    (6.289 * Math.sin(Mp) +
      1.274 * Math.sin(2 * D - Mp) +
      0.658 * Math.sin(2 * D) +
      0.214 * Math.sin(2 * Mp) -
      0.186 * Math.sin(M) -
      0.114 * Math.sin(2 * F)) *
      D2R;
  const beta =
    (5.128 * Math.sin(F) +
      0.281 * Math.sin(Mp + F) -
      0.278 * Math.sin(F - Mp) -
      0.173 * Math.sin(2 * D - F)) *
    D2R;

  const eps = (23.439 - 0.0000004 * (jd - 2451545.0)) * D2R;
  const ra = Math.atan2(
    Math.sin(lambda) * Math.cos(eps) - Math.tan(beta) * Math.sin(eps),
    Math.cos(lambda)
  );
  const dec = Math.asin(
    Math.sin(beta) * Math.cos(eps) +
      Math.cos(beta) * Math.sin(eps) * Math.sin(lambda)
  );

  const n = jd - 2451545.0;
  const gmst = (18.697374558 + 24.06570982441908 * n) % 24;
  const lst = (gmst * 15 + lon + 360) % 360;
  const ha = ((lst - ((ra * R2D + 360) % 360) + 540) % 360) - 180;

  const phi = lat * D2R;
  const sinAlt =
    Math.sin(phi) * Math.sin(dec) +
    Math.cos(phi) * Math.cos(dec) * Math.cos(ha * D2R);
  const altitude = Math.asin(Math.max(-1, Math.min(1, sinAlt))) * R2D;

  // Illuminated fraction from phase angle
  const phaseAngle =
    180 -
    D * R2D -
    6.289 * Math.sin(Mp) +
    2.1 * Math.sin(M) -
    1.274 * Math.sin(2 * D - Mp) -
    0.658 * Math.sin(2 * D) -
    0.214 * Math.sin(2 * Mp) -
    0.11 * Math.sin(D);
  const illumination = (1 + Math.cos(phaseAngle * D2R)) / 2;

  // Waxing when elongation is in the first half of the cycle
  const elong = ((D * R2D) % 360 + 360) % 360;
  const waxing = elong < 180;

  return { altitude, illumination, waxing };
}

// --- Card ------------------------------------------------------------------

const HOUR = 3600000;

class SpotTheAuroraForecastCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:spot-the-aurora-forecast-card" };
  }

  setConfig(config) {
    this._config = {
      title: "3-day aurora forecast",
      subtitle:
        "What the southern sky may look like over the next 72 hours",
      hours: 72,
      height: 300,
      ...config,
    };
    this._build();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._render();
    else this._maybeRerender();
  }

  getCardSize() {
    return 7;
  }

  _findEntity(needle) {
    if (!this._hass) return null;
    const cands = Object.keys(this._hass.states).filter(
      (id) => id.startsWith("sensor.") && id.endsWith(needle)
    );
    const usable = (id) => {
      const s = this._hass.states[id]?.state;
      return s !== "unavailable" && s !== "unknown";
    };
    return (
      cands.find((id) => id.includes("spot_the_aurora") && usable(id)) ??
      cands.find(usable) ??
      cands[0] ??
      null
    );
  }

  _build() {
    if (this._root) return;
    this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      ha-card { overflow: hidden; }
      .head { padding: 14px 16px 6px; }
      .title { font-size: 1.2rem; font-weight: 500; }
      .sub { font-size: 0.78rem; opacity: 0.6; margin-top: 3px; }
      .wrap { overflow-x: auto; padding: 0 8px 4px; }
      .wrap::-webkit-scrollbar { height: 6px; }
      .wrap::-webkit-scrollbar-thumb {
        background: var(--divider-color, #444); border-radius: 3px;
      }
      svg { display: block; }
      .legend {
        display: flex; gap: 16px; flex-wrap: wrap;
        padding: 6px 16px 14px; font-size: 0.72rem; opacity: 0.75;
        align-items: center;
      }
      .key { display: flex; align-items: center; gap: 6px; }
      .dot { width: 10px; height: 10px; border-radius: 2px; }
      .note { margin-left: auto; opacity: 0.6; font-size: 0.7rem; }
      .empty { padding: 24px 16px; opacity: 0.6; font-size: 0.85rem; }
    `;
    const card = document.createElement("ha-card");
    card.innerHTML = `
      <div class="head">
        <div class="title"></div>
        <div class="sub"></div>
      </div>
      <div class="wrap"></div>
      <div class="legend"></div>
    `;
    this.shadowRoot.append(style, card);
    this._root = card;
    card.querySelector(".title").textContent = this._config.title;
    card.querySelector(".sub").textContent = this._config.subtitle;
  }

  _maybeRerender() {
    // Kp updates rarely; redraw at most once a minute
    const now = Date.now();
    if (this._lastDraw && now - this._lastDraw < 60000) return;
    this._render();
  }

  _render() {
    if (!this._hass || !this._root) return;
    this._lastDraw = Date.now();

    const scoreId = this._findEntity("aurora_score");
    const attrs = scoreId ? this._hass.states[scoreId]?.attributes ?? {} : {};

    const kpId = this._findEntity("kp_forecast");
    const kpAttrs = kpId ? this._hass.states[kpId]?.attributes ?? {} : {};
    const kpData = kpAttrs.forecast ?? [];

    const wrap = this._root.querySelector(".wrap");
    if (!Array.isArray(kpData) || kpData.length === 0) {
      wrap.innerHTML =
        `<div class="empty">Waiting for the NOAA Kp forecast. This updates a few times a day.</div>`;
      return;
    }

    const lat = attrs.latitude ?? this._hass.config.latitude;
    const lon = attrs.longitude ?? this._hass.config.longitude;
    const threshold = kpAttrs.threshold ?? attrs.kp_threshold ?? 5;

    wrap.innerHTML = this._buildSvg(kpData, lat, lon, threshold);
    this._renderLegend(threshold, lat);
  }

  _buildSvg(kpData, lat, lon, threshold) {
    const H = this._config.height;
    const HEADER = 26;      // day labels
    const AXIS = 20;        // hour labels
    const PLOT = H - HEADER - AXIS;
    const PX_PER_HOUR = 13;

    const start = new Date(kpData[0].t).getTime();
    const end = new Date(kpData[kpData.length - 1].t).getTime() + 3 * HOUR;
    const hours = Math.min(this._config.hours, (end - start) / HOUR);
    const W = Math.round(hours * PX_PER_HOUR);
    const x = (t) => ((t - start) / HOUR) * PX_PER_HOUR;

    const parts = [];
    parts.push(
      `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`
    );
    parts.push(`<defs>
      <linearGradient id="auroraG" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#22c55e" stop-opacity="0.95"/>
        <stop offset="70%" stop-color="#22c55e" stop-opacity="0.25"/>
        <stop offset="100%" stop-color="#22c55e" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="auroraP" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#ec4899" stop-opacity="0.95"/>
        <stop offset="70%" stop-color="#ec4899" stop-opacity="0.25"/>
        <stop offset="100%" stop-color="#ec4899" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="auroraB" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.95"/>
        <stop offset="70%" stop-color="#3b82f6" stop-opacity="0.3"/>
        <stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/>
      </linearGradient>
    </defs>`);

    // --- Sky: sample solar elevation every 15 min ---
    const STEP = 15 * 60000;
    for (let t = start; t < start + hours * HOUR; t += STEP) {
      const d = new Date(t);
      const elev = solarElevation(d, lat, lon);
      const x0 = x(t);
      const w = (STEP / HOUR) * PX_PER_HOUR + 0.6;
      let fill;
      if (elev > 0) {
        fill = "#3b6ea8";                       // daylight
      } else if (elev > -6) {
        fill = "#8a5a3c";                       // civil twilight
      } else if (elev > -12) {
        fill = "#3c3a5c";                       // nautical
      } else if (elev > -18) {
        fill = "#1a1c33";                       // astronomical
      } else {
        fill = "#0a0b16";                       // full dark
      }
      parts.push(
        `<rect x="${x0.toFixed(1)}" y="${HEADER}" width="${w.toFixed(1)}" height="${PLOT}" fill="${fill}"/>`
      );
    }

    // --- Stars in the dark hours ---
    let seed = 7;
    const rnd = () => {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed / 0x7fffffff;
    };
    for (let i = 0; i < Math.round(hours * 2.2); i++) {
      const t = start + rnd() * hours * HOUR;
      if (solarElevation(new Date(t), lat, lon) > -10) continue;
      const sx = x(t);
      const sy = HEADER + rnd() * PLOT * 0.8;
      const r = rnd() * 0.9 + 0.3;
      parts.push(
        `<circle cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="${r.toFixed(1)}" fill="#fff" opacity="${(0.25 + rnd() * 0.5).toFixed(2)}"/>`
      );
    }

    // --- Aurora bars, one per 3-hour Kp block ---
    // Height is how far Kp exceeds what you need. Bars start appearing
    // one Kp step below threshold so a near miss is still visible.
    const barW = 3 * PX_PER_HOUR;
    for (const row of kpData) {
      const t = new Date(row.t).getTime();
      if (t < start || t >= start + hours * HOUR) continue;
      const kp = row.kp;
      const over = kp - (threshold - 1);
      if (over <= 0) continue;

      const frac = Math.max(0, Math.min(1, over / 3.5));
      const h = frac * PLOT * 0.92;
      const grad =
        kp >= 7 ? "auroraB" : kp >= threshold + 0.5 ? "auroraP" : "auroraG";

      parts.push(
        `<rect x="${x(t).toFixed(1)}" y="${(HEADER + PLOT - h).toFixed(1)}" width="${barW}" height="${h.toFixed(1)}" fill="url(#${grad})">` +
          `<title>Kp ${kp.toFixed(2)} - ${new Date(row.t).toLocaleString()} (${row.observed})</title></rect>`
      );
    }

    // --- Moon markers at rise and set ---
    let prevAlt = moonState(new Date(start), lat, lon).altitude;
    for (let t = start + STEP; t < start + hours * HOUR; t += STEP) {
      const m = moonState(new Date(t), lat, lon);
      if (prevAlt < 0 !== m.altitude < 0) {
        const rising = m.altitude > prevAlt;
        const cx = x(t);
        const cy = HEADER + PLOT * (rising ? 0.72 : 0.28);
        const illum = m.illumination;
        const grey = illum < 0.35;
        parts.push(
          `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="7" fill="${grey ? "#4b5563" : "#e8e2b8"}" stroke="#94a3b8" stroke-width="1" opacity="0.9">` +
            `<title>Moon ${rising ? "rise" : "set"} - ${Math.round(illum * 100)}% illuminated</title></circle>`
        );
      }
      prevAlt = m.altitude;
    }

    // --- Day dividers, labels and hour ticks ---
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    let lastDay = null;
    for (let t = start; t < start + hours * HOUR; t += HOUR) {
      const d = new Date(t);
      const day = d.toLocaleDateString(undefined, { timeZone: tz });
      const hr = d.getHours();

      if (day !== lastDay) {
        if (lastDay !== null) {
          parts.push(
            `<line x1="${x(t)}" y1="0" x2="${x(t)}" y2="${HEADER + PLOT}" stroke="#94a3b8" stroke-opacity="0.5" stroke-width="1"/>`
          );
        }
        const label = d.toLocaleDateString(undefined, {
          weekday: "short",
          day: "numeric",
          month: "short",
        });
        parts.push(
          `<text x="${x(t) + 8}" y="17" fill="currentColor" opacity="0.85" font-size="12" font-weight="600">${label}</text>`
        );
        lastDay = day;
      }

      if (hr % 3 === 0) {
        parts.push(
          `<text x="${x(t) + 2}" y="${H - 6}" fill="currentColor" opacity="0.45" font-size="10">${hr}:00</text>`
        );
      }
    }

    // --- "now" marker ---
    const now = Date.now();
    if (now >= start && now < start + hours * HOUR) {
      parts.push(
        `<line x1="${x(now).toFixed(1)}" y1="${HEADER - 8}" x2="${x(now).toFixed(1)}" y2="${HEADER + PLOT}" stroke="#fff" stroke-width="1.5" stroke-dasharray="3 3"/>`
      );
      parts.push(
        `<text x="${(x(now) + 4).toFixed(1)}" y="${HEADER - 10}" fill="#fff" font-size="10" font-weight="600">now</text>`
      );
    }

    parts.push(`</svg>`);
    return parts.join("");
  }

  _renderLegend(threshold, lat) {
    const el = this._root.querySelector(".legend");
    el.innerHTML = `
      <span class="key"><span class="dot" style="background:#22c55e"></span>Aurora possible</span>
      <span class="key"><span class="dot" style="background:#ec4899"></span>Active</span>
      <span class="key"><span class="dot" style="background:#3b82f6"></span>Intense (G3+)</span>
      <span class="key"><span class="dot" style="background:#e8e2b8;border-radius:50%"></span>Moonrise / moonset</span>
      <span class="note">Calibrated to ${lat != null ? Math.abs(lat).toFixed(1) + "&deg;S" : "your location"} &middot; aurora threshold Kp ${Number(threshold).toFixed(1)}</span>
    `;
  }
}

customElements.define(
  "spot-the-aurora-forecast-card",
  SpotTheAuroraForecastCard
);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "spot-the-aurora-forecast-card",
  name: "Spot The Aurora 3-Day Forecast",
  description:
    "72 hour Kp forecast with day, night and moon, calibrated to your latitude",
  preview: false,
});
