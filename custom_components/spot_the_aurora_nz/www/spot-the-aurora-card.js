/**
 * Spot The Aurora NZ - map card
 *
 * Draws the auroral oval, its edges and the visibility view line, with a
 * marker at your location. Geometry comes from the integration's
 * sensor.aurora_score attributes, so the card and any notifications always
 * agree - the physics runs once, server side.
 *
 * Registered automatically by the integration. No resource entry needed.
 */

const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LOGO_URL = "/spot_the_aurora_nz/logo.png";

// Basemaps that need no API key. CARTO now watermarks unkeyed requests,
// so it is deliberately not offered here.
const BASEMAPS = {
  osm: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 12,
    dimmable: true,
  },
  terrain: {
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attribution: "&copy; OpenTopoMap, &copy; OpenStreetMap contributors",
    maxZoom: 12,
    dimmable: true,
  },
  satellite: {
    url:
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "&copy; Esri, Maxar, Earthstar Geographics",
    maxZoom: 12,
    dimmable: false,
  },
  none: null,
};

const POLE_LAT_RAD = (80.65 * Math.PI) / 180;
const POLE_LON_RAD = (-72.68 * Math.PI) / 180;

function geoToGmag(latDeg, lonDeg) {
  const phi = (latDeg * Math.PI) / 180;
  const lam = (lonDeg * Math.PI) / 180;
  const s =
    Math.sin(phi) * Math.sin(POLE_LAT_RAD) +
    Math.cos(phi) * Math.cos(POLE_LAT_RAD) * Math.cos(lam - POLE_LON_RAD);
  return (Math.asin(Math.max(-1, Math.min(1, s))) * 180) / Math.PI;
}

function gmagToGeoLat(gmagLat, lonDeg) {
  let lo = -90;
  let hi = 90;
  for (let i = 0; i < 48; i++) {
    const mid = (lo + hi) / 2;
    if (geoToGmag(mid, lonDeg) < gmagLat) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}

function buildOvalRing(gmagLat, lonStep = 1.5) {
  const pts = [];
  for (let lon = -180; lon <= 200; lon += lonStep) {
    const normLon = ((lon + 180) % 360) - 180;
    const geoLat = gmagToGeoLat(gmagLat, normLon);
    if (geoLat >= -85 && geoLat <= 85) pts.push([geoLat, lon]);
  }
  return pts;
}

function buildBandPolygon(gmagInner, gmagOuter, lonStep = 2) {
  const outer = [];
  const inner = [];
  for (let lon = -180; lon <= 200; lon += lonStep) {
    const normLon = ((lon + 180) % 360) - 180;
    outer.push([gmagToGeoLat(gmagOuter, normLon), lon]);
    inner.push([gmagToGeoLat(gmagInner, normLon), lon]);
  }
  inner.reverse();
  return [...outer, ...inner];
}

function ovalColour(score) {
  if (score >= 80) return { line: "#f87171", fill: "#f87171", fillOpacity: 0.22 };
  if (score >= 65) return { line: "#fb923c", fill: "#fb923c", fillOpacity: 0.2 };
  if (score >= 50) return { line: "#f59e0b", fill: "#f59e0b", fillOpacity: 0.18 };
  if (score >= 35) return { line: "#a3e635", fill: "#a3e635", fillOpacity: 0.15 };
  if (score >= 20) return { line: "#34d399", fill: "#34d399", fillOpacity: 0.12 };
  return { line: "#38bdf8", fill: "#38bdf8", fillOpacity: 0.08 };
}

const TIER_COLOUR = {
  Eye: "#f59e0b",
  Phone: "#a3e635",
  Camera: "#34d399",
  Nothing: "#64748b",
};

const SLOTS = [
  { key: "now", label: "Now" },
  { key: "15", label: "15 min" },
  { key: "30", label: "30 min" },
  { key: "60", label: "1 hr" },
  { key: "120", label: "2 hr" },
];

function fireMoreInfo(el, entityId) {
  const ev = new Event("hass-more-info", { bubbles: true, composed: true });
  ev.detail = { entityId };
  el.dispatchEvent(ev);
}

let leafletPromise = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (leafletPromise) return leafletPromise;
  leafletPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = LEAFLET_JS;
    s.onload = () => resolve(window.L);
    s.onerror = () => reject(new Error("Leaflet failed to load"));
    document.head.appendChild(s);
  });
  return leafletPromise;
}

class SpotTheAuroraCard extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:spot-the-aurora-card" };
  }

  setConfig(config) {
    this._config = {
      title: "Spot The Aurora",
      entity: null,
      visibility_entity: null,
      basemap: "osm",
      zoom: 4,
      height: "420px",
      dark: true,
      show_logo: true,
      show_forecast: true,
      ...config,
    };
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 8;
  }

  _findEntity(configKey, needle) {
    if (!this._hass) return null;
    const exact = this._config[configKey];
    if (exact && this._hass.states[exact]) return exact;

    // The integration uses has_entity_name, so IDs are prefixed with the
    // device name. Match on what the entity actually is.
    //
    // Orphaned entities from an older YAML setup can share the same
    // suffix, so prefer ones that belong to this integration and that
    // are actually reporting a state.
    const candidates = Object.keys(this._hass.states).filter(
      (id) => id.startsWith("sensor.") && id.endsWith(needle)
    );
    if (candidates.length === 0) return null;

    const usable = (id) => {
      const st = this._hass.states[id]?.state;
      return st !== "unavailable" && st !== "unknown";
    };

    return (
      candidates.find((id) => id.includes("spot_the_aurora") && usable(id)) ??
      candidates.find(usable) ??
      candidates[0]
    );
  }

  _build() {
    if (this._root) return;
    this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      ha-card { overflow: hidden; }
      .head {
        padding: 12px 16px 8px;
        display: flex; align-items: center; gap: 12px;
      }
      .logo { width: 34px; height: 34px; border-radius: 8px; flex: none; }
      .heading { flex: 1; min-width: 0; }
      .title { font-size: 1.2rem; font-weight: 500; line-height: 1.2; }
      .sub { font-size: 0.75rem; opacity: 0.6; margin-top: 2px; }
      .badge {
        font-size: 0.95rem; font-weight: 600; white-space: nowrap;
        padding: 4px 10px; border-radius: 999px;
        border: 1px solid currentColor;
      }
      #map { width: 100%; background: #0b0b10; }
      .forecast {
        display: grid; grid-template-columns: repeat(5, 1fr);
        gap: 1px; background: var(--divider-color, #333);
        border-top: 1px solid var(--divider-color, #333);
      }
      .slot {
        background: var(--card-background-color, #1c1c1c);
        padding: 8px 4px; text-align: center;
        cursor: pointer; transition: background 0.15s;
      }
      .slot:hover { background: var(--secondary-background-color, #2a2a2a); }
      .slot .when { font-size: 0.65rem; opacity: 0.6; text-transform: uppercase; letter-spacing: 0.04em; }
      .slot .tier { font-size: 0.8rem; font-weight: 600; margin-top: 3px; }
      .slot .pct  { font-size: 0.65rem; opacity: 0.5; margin-top: 1px; }
      .legend { display:flex; gap:14px; flex-wrap:wrap; padding:8px 16px 12px; font-size:0.72rem; opacity:0.7; }
      .key { display:flex; align-items:center; gap:6px; }
      .swatch { width:16px; height:0; border-top-width:2px; border-top-style:solid; }
      .err { padding: 16px; color: var(--error-color, #f87171); font-size: 0.85rem; }
    `;

    const cssLink = document.createElement("link");
    cssLink.rel = "stylesheet";
    cssLink.href = LEAFLET_CSS;

    const card = document.createElement("ha-card");
    card.innerHTML = `
      <div class="head">
        <img class="logo" src="${LOGO_URL}" alt="" hidden>
        <div class="heading">
          <div class="title"></div>
          <div class="sub"></div>
        </div>
        <span class="badge"></span>
      </div>
      <div id="map"></div>
      <div class="forecast" hidden></div>
      <div class="legend">
        <span class="key"><span class="swatch" style="border-top-color:#38bdf8;border-top-style:dotted"></span>View line</span>
        <span class="key"><span class="swatch oval-key"></span>Oval edge</span>
        <span class="key"><span class="swatch" style="border-top-color:#94a3b8;border-top-style:dashed"></span>Poleward edge</span>
      </div>
    `;

    this.shadowRoot.append(style, cssLink, card);
    this._root = card;
    this._mapEl = card.querySelector("#map");
    this._mapEl.style.height = this._config.height;
    card.querySelector(".title").textContent = this._config.title;
    if (this._config.show_logo) {
      card.querySelector(".logo").hidden = false;
    }
    this._forecastEl = card.querySelector(".forecast");

    loadLeaflet()
      .then((L) => this._initMap(L))
      .catch(() => {
        const e = document.createElement("div");
        e.className = "err";
        e.textContent =
          "Could not load the map library. Check this device has internet access.";
        card.appendChild(e);
      });
  }

  _initMap(L) {
    const lat = this._hass?.config?.latitude ?? -43.53;
    const lon = this._hass?.config?.longitude ?? 172.63;

    this._map = L.map(this._mapEl, {
      center: [lat - 6, lon],
      zoom: this._config.zoom,
      zoomControl: true,
      worldCopyJump: false,
    });

    const base = BASEMAPS[this._config.basemap] ?? BASEMAPS.osm;
    if (base) {
      const layer = L.tileLayer(base.url, {
        attribution: base.attribution,
        maxZoom: base.maxZoom,
      }).addTo(this._map);

      // Dim and desaturate so the oval reads clearly on top
      if (this._config.dark && base.dimmable) {
        const c = layer.getContainer();
        if (c) c.style.filter = "brightness(0.55) saturate(0.5) contrast(1.1)";
      }
    }

    L.circleMarker([lat, lon], {
      radius: 6,
      color: "#ffffff",
      weight: 2,
      fillColor: "#0ea5e9",
      fillOpacity: 1,
    })
      .addTo(this._map)
      .bindPopup("Your location");

    this._layers = L.layerGroup().addTo(this._map);
    setTimeout(() => this._map.invalidateSize(), 250);
    this._update();
  }

  _update() {
    if (!this._map || !this._hass) return;

    const id = this._findEntity("entity", "aurora_score");
    const st = this._hass.states[id];
    if (!st) {
      this._root.querySelector(".badge").textContent = "Sensor not found";
      return;
    }

    const a = st.attributes || {};
    const equatorward = parseFloat(a.oval_equatorward);
    const poleward = parseFloat(a.oval_poleward);
    const viewLine = parseFloat(a.oval_view_line);
    const score = parseFloat(st.state) || 0;

    if (!isFinite(equatorward) || !isFinite(viewLine)) {
      this._root.querySelector(".badge").textContent = "Waiting for data";
      return;
    }

    const { line, fill, fillOpacity } = ovalColour(score);
    const L = window.L;
    this._layers.clearLayers();

    L.polygon(buildBandPolygon(poleward, equatorward, 2), {
      color: "transparent",
      fillColor: fill,
      fillOpacity,
      weight: 0,
    }).addTo(this._layers);

    L.polyline(buildOvalRing(poleward, 1.5), {
      color: line,
      weight: 1,
      opacity: 0.35,
      dashArray: "4 6",
    }).addTo(this._layers);

    L.polyline(buildOvalRing(equatorward, 1.5), {
      color: line,
      weight: 2.5,
      opacity: 0.9,
      dashArray: score < 25 ? "6 5" : undefined,
    }).addTo(this._layers);

    L.polyline(buildOvalRing(viewLine, 1.5), {
      color: "#38bdf8",
      weight: score >= 20 ? 2 : 1.5,
      opacity: score >= 20 ? 0.85 : 0.5,
      dashArray: "2 8",
    })
      .addTo(this._layers)
      .bindPopup("Visibility view line");

    const visId = this._findEntity("visibility_entity", "visibility_now");
    const vis = visId ? this._hass.states[visId]?.state : null;
    const badge = this._root.querySelector(".badge");
    badge.textContent = vis ?? `${score.toFixed(0)}%`;
    badge.style.color = vis ? TIER_COLOUR[vis] ?? line : line;

    const key = this._root.querySelector(".oval-key");
    if (key) key.style.borderTopColor = line;

    // Subheading: where the forecast is being calculated for
    const sub = this._root.querySelector(".sub");
    if (sub) {
      const src = a.location_source;
      const gmag = a.geomagnetic_latitude;
      if (a.is_daylight) {
        sub.textContent = "Daylight - nothing visible until dark";
      } else if (gmag != null) {
        const gap = (gmag - viewLine).toFixed(1);
        sub.textContent =
          gap <= 0
            ? `You are inside the view line by ${Math.abs(gap)} deg`
            : `View line is ${gap} deg south of you`;
      } else if (src) {
        sub.textContent = `Location: ${src}`;
      }
    }

    this._renderForecast();
    this._fitToOval(viewLine);
  }

  _renderForecast() {
    if (!this._config.show_forecast || !this._forecastEl) return;

    const cells = SLOTS.map(({ key, label }) => {
      const suffix = key === "now" ? "visibility_now"
        : key === "15" ? "visibility_15_minutes"
        : key === "30" ? "visibility_30_minutes"
        : key === "60" ? "visibility_1_hour"
        : "visibility_2_hours";
      const id = this._findEntity(`__slot_${key}`, suffix);
      const st = id ? this._hass.states[id] : null;
      if (!st) return "";
      const tier = st.state;
      const pct = st.attributes?.[`score_${key}`];
      const colour = TIER_COLOUR[tier] ?? "#64748b";
      return `
        <div class="slot" data-entity="${id}">
          <div class="when">${label}</div>
          <div class="tier" style="color:${colour}">${tier}</div>
          <div class="pct">${pct != null ? Math.round(pct) + "%" : ""}</div>
        </div>`;
    }).join("");

    if (!cells.trim()) return;
    this._forecastEl.innerHTML = cells;
    this._forecastEl.hidden = false;

    this._forecastEl.querySelectorAll(".slot").forEach((el) => {
      el.onclick = () => fireMoreInfo(this, el.dataset.entity);
    });
  }

  _fitToOval(viewLine) {
    // Frame the user and the view line together, so the card is useful
    // whether the oval is far south or pushing overhead. Only auto-fits
    // once, so it never fights the user panning around.
    if (this._fitted || !this._map) return;
    const lat = this._hass?.config?.latitude;
    const lon = this._hass?.config?.longitude;
    if (lat == null || lon == null) return;

    const viewGeoLat = gmagToGeoLat(viewLine, lon);
    const south = Math.min(lat, viewGeoLat) - 4;
    const north = Math.max(lat, viewGeoLat) + 3;
    try {
      this._map.fitBounds(
        [[south, lon - 14], [north, lon + 14]],
        { padding: [10, 10] }
      );
      this._fitted = true;
    } catch (e) {
      /* leave the default view */
    }
  }
}

customElements.define("spot-the-aurora-card", SpotTheAuroraCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "spot-the-aurora-card",
  name: "Spot The Aurora Map",
  description: "Auroral oval and visibility view line on a map",
  preview: false,
});

console.info(
  "%c SPOT-THE-AURORA-NZ %c v1.2.0 ",
  "background:#0ea5e9;color:#fff",
  ""
);
