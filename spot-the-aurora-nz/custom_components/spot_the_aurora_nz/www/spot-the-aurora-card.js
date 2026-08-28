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
      title: "Aurora Oval",
      entity: "sensor.aurora_score",
      visibility_entity: "sensor.visibility_now",
      zoom: 4,
      height: "420px",
      dark: true,
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

  _findEntity(suffix) {
    if (!this._hass) return null;
    const exact = this._config[suffix];
    if (exact && this._hass.states[exact]) return exact;
    // Fall back to searching by unique-id suffix so renamed entities still work
    const match = Object.keys(this._hass.states).find((id) =>
      id.startsWith("sensor.") && id.includes(suffix.replace("_entity", ""))
    );
    return match || null;
  }

  _build() {
    if (this._root) return;
    this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      ha-card { overflow: hidden; }
      .head { padding: 12px 16px 4px; display:flex; justify-content:space-between; align-items:baseline; }
      .title { font-size: 1.25rem; font-weight: 500; }
      .badge { font-size: 0.9rem; font-weight: 500; }
      #map { width: 100%; background: #101014; }
      .legend { display:flex; gap:14px; flex-wrap:wrap; padding:8px 16px 12px; font-size:0.75rem; opacity:0.75; }
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
        <span class="title"></span>
        <span class="badge"></span>
      </div>
      <div id="map"></div>
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

    const tileUrl = this._config.dark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

    L.tileLayer(tileUrl, {
      attribution: "&copy; OpenStreetMap, &copy; CARTO",
      maxZoom: 10,
    }).addTo(this._map);

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

    const id = this._findEntity("entity") || this._config.entity;
    const st = this._hass.states[id];
    if (!st) {
      this._root.querySelector(".badge").textContent = "No data";
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

    const visId = this._config.visibility_entity;
    const vis = visId ? this._hass.states[visId]?.state : null;
    const badge = this._root.querySelector(".badge");
    badge.textContent = vis
      ? `${vis} - ${score.toFixed(0)}%`
      : `${score.toFixed(0)}%`;
    badge.style.color = line;

    const key = this._root.querySelector(".oval-key");
    if (key) key.style.borderTopColor = line;
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
  "%c SPOT-THE-AURORA-NZ %c v1.0.0 ",
  "background:#0ea5e9;color:#fff",
  ""
);
