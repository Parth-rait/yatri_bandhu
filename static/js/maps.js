/* Yatri Bandhu maps — vector maps (MapLibre GL + OpenFreeMap, no API key).
 *
 * Visual language (same on every map):
 *   bus ride   = blue line with a white casing; white stop dots along it
 *   2nd bus    = violet line (so a change is obvious)
 *   walking    = grey dotted line
 *   start      = blue dot with white ring          destination = red pin
 *   labels     = white cards ("Board 38B", "Get off") that hide when they would overlap
 *   you        = blue dot with a soft pulsing halo
 * Maps are fenced to the Tricity (Chandigarh, Mohali, Panchkula and the towns around them).
 */
(function () {
  'use strict';
  const RM = (window.RM = window.RM || {});
  const root = document.documentElement;

  const C = { blue: '#2563eb', violet: '#7c3aed', teal: '#0891b2', walk: '#8a93a6', red: '#ef4444', amber: '#f59e0b', green: '#16a34a' };
  const BUS_COLORS = [C.blue, C.violet, C.teal];
  RM.routeColor = () => C.blue;

  // Service area, as [lng, lat]
  const AREA = [[76.52, 30.52], [76.98, 30.90]];
  const FENCE = [[76.38, 30.44], [77.12, 30.98]];
  RM.TRICITY = { contains: ([lat, lng]) => lat >= AREA[0][1] && lat <= AREA[1][1] && lng >= AREA[0][0] && lng <= AREA[1][0] };

  const dark = () => root.dataset.theme === 'dark';
  const STYLE = () => `https://tiles.openfreemap.org/styles/${dark() ? 'dark' : 'liberty'}`;
  const calm = () => root.classList.contains('reduce-motion') || matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // our data uses [lat, lng] arrays and {lat, lng} objects; MapLibre wants [lng, lat]
  const LL = (p) => (Array.isArray(p) ? [p[1], p[0]] : [p.lng, p.lat]);

  const SVG = {
    bus: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 17h12M6 17a2 2 0 0 1-2-2V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v9a2 2 0 0 1-2 2M6 17v3M18 17v3M4 11h16"/></svg>',
    star: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/></svg>',
    pin: '<svg class="mk-pin" width="34" height="44" viewBox="0 0 34 44"><path d="M17 43s15-14.3 15-25.5A15 15 0 0 0 2 17.5C2 28.7 17 43 17 43z" fill="#ef4444" stroke="#fff" stroke-width="2.5"/><circle cx="17" cy="17" r="6" fill="#fff"/></svg>',
  };

  // ------------------------------------------------------------- map setup
  // Calm light basemap (storyboard look): grey land, white roads, soft green parks, blue water.
  // The blue route is then the only strong colour on screen.
  const LIGHT = {
    land: '#f2f3f5', residential: '#eceef2', building: '#e3e6eb', park: '#d9eed2', wood: '#d3ead0', water: '#bcd8f5',
    road: '#ffffff', casing: '#dde1e7', major: '#ffffff', majorCasing: '#d3d8e0', label: '#6b7280', rail: '#cfd4dc',
  };
  function setPaint(map, id, prop, value) { try { map.setPaintProperty(id, prop, value); } catch (e) { /* layer lacks prop */ } }
  function tune(map) {
    // Fewer things competing with the route: no POI icons, shields, arrows, 3D buildings or country labels.
    const hide = /^(poi|building-3d|road_one_way|highway-shield|road_shield|label_country|label_state|airport)/;
    for (const layer of map.getStyle().layers) {
      const id = layer.id;
      if (hide.test(id) && !(map.rmKeepPoi && /^poi_r/.test(id))) { map.setLayoutProperty(id, 'visibility', 'none'); continue; }
      if (id === 'building') map.setLayerZoomRange(id, 14.5, 24);
      if (dark()) continue;
      if (id === 'background') setPaint(map, id, 'background-color', LIGHT.land);
      else if (id === 'landuse_residential') setPaint(map, id, 'fill-color', LIGHT.residential);
      else if (id === 'building') { setPaint(map, id, 'fill-color', LIGHT.building); setPaint(map, id, 'fill-outline-color', LIGHT.casing); }
      else if (id === 'park' || id === 'landcover_grass' || id === 'landuse_pitch') setPaint(map, id, 'fill-color', LIGHT.park);
      else if (id === 'landcover_wood') setPaint(map, id, 'fill-color', LIGHT.wood);
      else if (id === 'water') setPaint(map, id, 'fill-color', LIGHT.water);
      else if (/^(road|bridge|tunnel)_/.test(id) && layer.type === 'line') {
        if (/rail/.test(id)) setPaint(map, id, 'line-color', LIGHT.rail);
        else if (/casing/.test(id)) setPaint(map, id, 'line-color', /motorway|trunk|primary/.test(id) ? LIGHT.majorCasing : LIGHT.casing);
        else if (!/path|pedestrian|area/.test(id)) setPaint(map, id, 'line-color', /motorway|trunk|primary/.test(id) ? LIGHT.major : LIGHT.road);
      } else if (layer.type === 'symbol' && /^(highway-name|label_)/.test(id)) {
        setPaint(map, id, 'text-color', LIGHT.label);
        setPaint(map, id, 'text-halo-color', '#ffffff');
      }
    }
  }

  RM.makeMap = function (id, onStyle, opts = {}) {
    const el = document.getElementById(id);
    if (!el || !window.maplibregl) return null;
    const map = new maplibregl.Map({
      container: el, style: STYLE(), center: [76.77, 30.71], zoom: 11.5,
      minZoom: 10, maxZoom: 18, maxBounds: FENCE,
      dragRotate: false, pitchWithRotate: false, touchPitch: false,
      attributionControl: { compact: true },
      pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
      fadeDuration: 0,
      refreshExpiredTiles: false,
      maxTileCacheSize: 300,
    });
    map.scrollZoom.setWheelZoomRate(1 / 300);
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.rmMarkers = [];
    map.rmDraw = [];
    map.rmKeepPoi = !!opts.keepPoi;
    map.on('style.load', () => { tune(map); onStyle && onStyle(map); map.rmDraw.forEach((f) => f(map)); });
    window.addEventListener('rm:theme', () => map.setStyle(STYLE()));
    return map;
  };

  RM.fit = function (map, coords, extra = {}) {
    if (!coords.length) return;
    const b = coords.reduce((bb, c) => bb.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]));
    const panel = innerWidth >= 960 ? document.querySelector('.mapui-panel') : null;
    const left = panel ? panel.getBoundingClientRect().right + 40 : 40;
    const padding = innerWidth >= 960 ? { top: 70, bottom: 70, left, right: 80 } : { top: 70, bottom: 50, left: 40, right: 40 };
    map.fitBounds(b, { padding, maxZoom: 15.5, duration: calm() ? 0 : 700, ...extra });
  };

  function marker(map, lnglat, html, anchor = 'center', cls = '') {
    const el = document.createElement('div');
    el.className = 'mk ' + cls;
    el.innerHTML = html;
    const m = new maplibregl.Marker({ element: el, anchor }).setLngLat(lnglat).addTo(map);
    map.rmMarkers.push(m);
    return m;
  }
  const card = (text, tone = 'right') => `<span class="mk-card ${tone}">${esc(text)}</span>`;

  // Hide label cards that would overlap a more important one (earlier = more important).
  function declutter(map) {
    const kept = [];
    map.rmMarkers.forEach((m) => {
      const c = m.getElement().querySelector('.mk-card');
      if (!c) return;
      c.classList.remove('is-hidden');
      const r = c.getBoundingClientRect();
      if (kept.some((k) => r.left < k.right + 4 && r.right > k.left - 4 && r.top < k.bottom + 2 && r.bottom > k.top - 2)) c.classList.add('is-hidden');
      else kept.push(r);
    });
  }
  function autoDeclutter(map) {
    const run = () => declutter(map);
    map.on('moveend', run);
    map.once('idle', run);
  }

  // Draw an overlay now (if the style is ready) and again after every style change (theme switch).
  function overlay(map, fn) {
    map.rmDraw.push(fn);
    if (map.isStyleLoaded()) fn(map);
  }
  function addOrSet(map, id, data) {
    const src = map.getSource(id);
    if (src) src.setData(data); else map.addSource(id, { type: 'geojson', data });
  }
  function routeLayers(map, src) {
    const before = undefined; // route always draws on top of the basemap (both themes)
    const casing = dark() ? '#0b0d12' : '#ffffff';
    const add = (spec, beforeId) => { if (!map.getLayer(spec.id)) map.addLayer(spec, beforeId); };
    add({ id: src + '-walk', type: 'line', source: src, filter: ['==', ['get', 'kind'], 'walk'],
      layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': C.walk, 'line-width': 4.5, 'line-dasharray': [0.1, 2] } }, before);
    add({ id: src + '-casing', type: 'line', source: src, filter: ['==', ['get', 'kind'], 'bus'],
      layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': casing, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 7, 15, 13] } }, before);
    add({ id: src + '-bus', type: 'line', source: src, filter: ['==', ['get', 'kind'], 'bus'],
      layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 4, 15, 7.5] } }, before);
    add({ id: src + '-stops', type: 'circle', source: src, filter: ['==', ['get', 'kind'], 'stop'], minzoom: 11.5,
      paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11.5, 2.5, 15, 5.5], 'circle-color': casing,
        'circle-stroke-color': ['get', 'color'], 'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 11.5, 1.5, 15, 3] } });
  }

  // ------------------------------------------------------------- journeys
  function journeyGeo(data) {
    const feats = [], coords = [];
    let bi = 0;
    data.legs.forEach((leg) => {
      if (leg.type === 'via') return;
      if (leg.type === 'bus') {
        leg.color = BUS_COLORS[bi++ % BUS_COLORS.length];
        const line = (leg.line && leg.line.length > 1 ? leg.line : [leg.start, leg.end]).map(LL);
        feats.push({ type: 'Feature', properties: { kind: 'bus', color: leg.color }, geometry: { type: 'LineString', coordinates: line } });
        (leg.stops || []).forEach((p) => feats.push({ type: 'Feature', properties: { kind: 'stop', color: leg.color }, geometry: { type: 'Point', coordinates: LL(p) } }));
        coords.push(...line);
      } else {
        const line = [LL(leg.start), LL(leg.end)];
        feats.push({ type: 'Feature', properties: { kind: 'walk' }, geometry: { type: 'LineString', coordinates: line } });
        coords.push(...line);
      }
    });
    return { geo: { type: 'FeatureCollection', features: feats }, coords };
  }

  function journeyMarkers(map, data) {
    const legs = data.legs;
    const last = legs[legs.length - 1];
    // most important first: declutter keeps earlier cards
    marker(map, LL(last.end), SVG.pin + card(data.dest ? data.dest.name : 'Destination'), 'bottom', 'mk-dest');
    marker(map, LL(legs[0].start), '<span class="mk-origin"></span>' + card(data.origin ? data.origin.name : 'Start'));
    let seenBus = false;
    legs.forEach((leg, i) => {
      if (leg.type === 'via') { marker(map, LL(leg.start), `<span class="mk-via">${SVG.star}</span>` + card(leg.start.name)); return; }
      if (leg.type !== 'bus') return;
      marker(map, LL(leg.start), `<span class="mk-board" style="--c:${leg.color}">${SVG.bus}</span>` + card(seenBus ? `Change to ${leg.route}` : `Board ${leg.route}`));
      seenBus = true;
      const next = legs[i + 1];
      if (!next || next.type !== 'bus') marker(map, LL(leg.end), '<span class="mk-off"></span>' + card('Get off', 'left'));
    });
  }

  function drawJourney(map, data) {
    const { geo, coords } = journeyGeo(data);
    overlay(map, (m) => { addOrSet(m, 'rm-j', geo); routeLayers(m, 'rm-j'); });
    journeyMarkers(map, data);
    autoDeclutter(map);
    return coords;
  }

  RM.youAt = function (map, lnglat) {
    if (!map.rmYou) {
      const el = document.createElement('div');
      el.className = 'mk';
      el.innerHTML = '<span class="mk-you"><i></i></span>';
      map.rmYou = new maplibregl.Marker({ element: el }).setLngLat(lnglat).addTo(map);
    }
    map.rmYou.setLngLat(lnglat);
  };

  function locateButton(map) {
    document.querySelectorAll('[data-locate]').forEach((b) => b.addEventListener('click', async () => {
      try {
        const pos = await RM.geolocate();
        const p = [pos.coords.longitude, pos.coords.latitude];
        RM.youAt(map, p);
        if (RM.TRICITY.contains([p[1], p[0]])) map.easeTo({ center: p, zoom: 15.5, duration: calm() ? 0 : 600 });
        else RM.toast?.("You're outside Chandigarh, Mohali and Panchkula");
      } catch (err) { RM.toast?.(err.message); }
    }));
  }

  RM.routesMap = function (data) {
    const map = RM.makeMap('routes-map');
    if (!map) return;
    if (data.legs && data.legs.length) {
      const coords = drawJourney(map, data);
      RM.fit(map, coords, { duration: 0 });
    } else {
      marker(map, LL(data.origin), '<span class="mk-origin"></span>' + card(data.origin.name));
      marker(map, LL(data.dest), SVG.pin + card(data.dest.name), 'bottom', 'mk-dest');
      RM.fit(map, [LL(data.origin), LL(data.dest)], { duration: 0 });
      autoDeclutter(map);
    }
    locateButton(map);
  };

  RM.journeyMap = function (data, { live = false } = {}) {
    const map = RM.makeMap('journey-map');
    if (!map) return;
    const coords = drawJourney(map, data);
    RM.fit(map, coords, { duration: 0 });
    document.querySelectorAll('[data-fit]').forEach((b) => b.addEventListener('click', () => RM.fit(map, coords)));
    locateButton(map);
    if (!live) return;

    // Scheduled bus position: waits at the boarding stop until departure, then moves along the route.
    const loaded = Date.now();
    const nowMin = () => data.now + (Date.now() - loaded) / 60000;
    const bus = data.legs.find((l) => l.type === 'bus');
    if (bus && bus.line && bus.line.length > 1) {
      const line = bus.line.map(LL);
      const seg = line.map((p, i) => (i ? dist(line[i - 1], p) : 0));
      const total = seg.reduce((a, b) => a + b, 0);
      const along = (f) => {
        let d = total * Math.min(1, Math.max(0, f));
        for (let i = 1; i < line.length; i++) {
          if (d <= seg[i]) { const t = seg[i] ? d / seg[i] : 0; return [line[i - 1][0] + (line[i][0] - line[i - 1][0]) * t, line[i - 1][1] + (line[i][1] - line[i - 1][1]) * t]; }
          d -= seg[i];
        }
        return line[line.length - 1];
      };
      const el = document.createElement('div');
      el.className = 'mk mk-live';
      el.innerHTML = '<span class="mk-bubble" data-bubble></span><span class="mk-bus">' + SVG.bus + '</span>';
      const busMarker = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat(LL(bus.start)).addTo(map);
      const tick = () => {
        const t = nowMin();
        const bubble = el.querySelector('[data-bubble]');
        const minsEl = document.querySelector('[data-live-mins]');
        const title = document.querySelector('[data-live-title]');
        if (t < bus.depart) {
          busMarker.setLngLat(LL(bus.start));
          const m = Math.max(0, Math.round(bus.depart - t));
          bubble.innerHTML = m ? `Arriving in<br><b>${m} min</b>` : '<b>Arriving now</b>';
          if (minsEl) minsEl.textContent = `${m} min`;
        } else if (t < bus.arrive) {
          busMarker.setLngLat(along((t - bus.depart) / Math.max(1, bus.arrive - bus.depart)));
          const m = Math.round(bus.arrive - t);
          bubble.innerHTML = `<b>${m} min</b> to your stop`;
          if (title) title.innerHTML = `On the bus · <span data-live-mins>${m} min</span> left`;
        } else {
          busMarker.setLngLat(LL(bus.end));
          bubble.innerHTML = '<b>At your stop</b>';
          if (title) title.textContent = 'Bus has reached your stop';
        }
      };
      tick();
      setInterval(tick, 15000);
    }

    // "Get off" alert using live location
    const legs = data.legs.filter((l) => l.type !== 'via');
    const key = 'yb.live.' + location.pathname;
    let ti = +(sessionStorage.getItem(key) || 0), watchId = null;
    const btns = document.querySelectorAll('[data-live-toggle]');
    function render(d) {
      const leg = legs[ti];
      const stage = leg.type === 'bus' ? 1 : ti === legs.length - 1 && ti > 0 ? 2 : 0;
      document.querySelectorAll('[data-node]').forEach((n) => n.classList.toggle('on', +n.dataset.node <= stage));
      document.querySelectorAll('[data-bar]').forEach((b) => b.classList.toggle('done', +b.dataset.bar < stage));
      const sub = document.querySelector('[data-live-sub]');
      if (!sub || d == null) return;
      const fmt = d < 1000 ? `${Math.round(d / 10) * 10} m` : `${(d / 1000).toFixed(1)} km`;
      if (leg.type === 'walk') sub.textContent = `Walk to ${leg.end.name} · ${fmt}`;
      else if (d < 500) { sub.textContent = `Get ready: ${leg.end.name} is next`; if (navigator.vibrate) navigator.vibrate([150, 80, 150]); }
      else sub.textContent = `${fmt} to ${leg.end.name}`;
    }
    function update(pos) {
      const p = [pos.coords.longitude, pos.coords.latitude];
      RM.youAt(map, p);
      while (ti < legs.length - 1 && dist(p, LL(legs[ti].end)) < 60) ti++;
      sessionStorage.setItem(key, ti);
      render(dist(p, LL(legs[ti].end)));
    }
    btns.forEach((btn) => btn.addEventListener('click', async () => {
      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId); watchId = null;
        btns.forEach((b) => b.setAttribute('aria-pressed', 'false'));
        RM.toast?.('Alert off');
        return;
      }
      try {
        const first = await RM.geolocate();
        update(first);
        watchId = navigator.geolocation.watchPosition(update, () => {}, { enableHighAccuracy: true, maximumAge: 5000 });
        btns.forEach((b) => b.setAttribute('aria-pressed', 'true'));
        RM.toast?.("Alert on: we'll tell you before your stop");
      } catch (err) { RM.toast?.(err.message); }
    }));
  };

  // metres between two [lng, lat]
  function dist(a, b) {
    const R = 6371000, r = Math.PI / 180;
    const dLat = (b[1] - a[1]) * r, dLng = (b[0] - a[0]) * r;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  // ------------------------------------------------------------- stops, lines, explore
  RM.nearbyMap = function (here, stops, buses = []) {
    const map = RM.makeMap('nearby-map');
    if (!map) return;
    const me = [here.lng, here.lat];
    RM.youAt(map, me);
    const coords = [me], shown = new Set();
    buses.forEach((b) => {
      if (shown.has(b.stop.id) || shown.size >= 4) return;
      shown.add(b.stop.id);
      const p = [b.stop.lng, b.stop.lat];
      coords.push(p);
      const m = marker(map, p, `<span class="mk-bus sm">${SVG.bus}</span>` +
        `<span class="mk-card right"><b>Route ${esc(b.route)}</b><small>${b.mins <= 0 ? 'now' : b.mins + ' min away'}</small></span>`);
      m.getElement().addEventListener('click', () => { location.href = `/stop/${encodeURIComponent(b.stop.id)}`; });
    });
    stops.forEach((s) => {
      if (shown.has(s.id)) return;
      const p = [s.lng, s.lat];
      coords.push(p);
      const m = marker(map, p, '<span class="mk-stopdot"></span>');
      m.getElement().title = s.name;
      m.getElement().addEventListener('click', () => { location.href = `/stop/${encodeURIComponent(s.id)}`; });
    });
    RM.fit(map, coords, { duration: 0, maxZoom: 16 });
    autoDeclutter(map);
    document.querySelectorAll('[data-locate]').forEach((b) => b.addEventListener('click', () => map.easeTo({ center: me, zoom: 16 })));
  };

  RM.stopMap = function (stop, lines) {
    const p = [stop.lng, stop.lat];
    const geo = { type: 'FeatureCollection', features: lines.map((l) => ({ type: 'Feature', properties: { kind: 'bus', color: C.blue },
      geometry: { type: 'LineString', coordinates: l.line.map(LL) } })) };
    const map = RM.makeMap('stop-map');
    if (!map) return;
    overlay(map, (m) => {
      addOrSet(m, 'rm-s', geo);
      if (!m.getLayer('rm-s-bus')) m.addLayer({ id: 'rm-s-bus', type: 'line', source: 'rm-s', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': C.blue, 'line-width': 4, 'line-opacity': 0.35 } });
    });
    marker(map, p, `<span class="mk-bus">${SVG.bus}</span>` + card(stop.name));
    map.jumpTo({ center: p, zoom: 15 });
  };

  RM.lineMap = function (no, shape, stops) {
    const line = shape.map(LL);
    const geo = { type: 'FeatureCollection', features: [
      { type: 'Feature', properties: { kind: 'bus', color: C.blue }, geometry: { type: 'LineString', coordinates: line } },
      ...stops.map((s) => ({ type: 'Feature', properties: { kind: 'stop', color: C.blue, id: s.id, name: s.name }, geometry: { type: 'Point', coordinates: [s.lng, s.lat] } })),
    ] };
    const map = RM.makeMap('line-map');
    if (!map) return;
    overlay(map, (m) => { addOrSet(m, 'rm-l', geo); routeLayers(m, 'rm-l'); });
    const a = stops[0], z = stops[stops.length - 1];
    marker(map, [a.lng, a.lat], '<span class="mk-origin"></span>' + card(a.name));
    if (z.id !== a.id) marker(map, [z.lng, z.lat], SVG.pin + card(z.name), 'bottom', 'mk-dest');
    const popup = new maplibregl.Popup({ closeButton: false, offset: 12, className: 'mk-pop' });
    map.on('click', 'rm-l-stops', (e) => {
      const f = e.features[0];
      popup.setLngLat(f.geometry.coordinates).setHTML(`<a href="/stop/${encodeURIComponent(f.properties.id)}">${esc(f.properties.name)} ›</a>`).addTo(map);
    });
    map.on('mouseenter', 'rm-l-stops', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'rm-l-stops', () => { map.getCanvas().style.cursor = ''; });
    RM.fit(map, line, { duration: 0 });
    autoDeclutter(map);
  };

  RM.exploreMap = function (origin, places, fares, times, outPlaces, kind, routesUrl, fromId) {
    const map = RM.makeMap('explore-map');
    if (!map || !origin) return;
    const go = (p) => { location.href = `${routesUrl}?from=${encodeURIComponent(fromId)}&to=place:${p.id}&mode=${kind === 'budget' ? 'cheapest' : 'fastest'}`; };
    const coords = [LL(origin)];
    marker(map, LL(origin), '<span class="mk-origin"></span>' + card(origin.name));
    places.forEach((p, i) => {
      coords.push(LL(p));
      const txt = kind === 'budget' ? (fares[i] ? `₹${fares[i]}` : 'Free') : `${times[i]} min`;
      const m = marker(map, LL(p), `<span class="mk-reach"></span><span class="mk-card right"><b>${esc(p.name)}</b><small class="ok">${esc(txt)}</small></span>`);
      m.getElement().addEventListener('click', () => go(p));
    });
    outPlaces.forEach((p) => {
      const m = marker(map, LL(p), '<span class="mk-stopdot off"></span>');
      m.getElement().title = p.name;
    });
    RM.fit(map, coords, { duration: 0, maxZoom: 13.5 });
    autoDeclutter(map);
  };

  // ------------------------------------------------------------- ride (auto / cab / bike taxi)
  RM.rideMap = function (data, id = 'journey-map') {
    const map = RM.makeMap(id);
    if (!map) return;
    const a = LL(data.origin), b = LL(data.dest);
    overlay(map, (m) => {
      addOrSet(m, 'rm-ride', { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [a, b] } });
      if (!m.getLayer('rm-ride')) m.addLayer({ id: 'rm-ride', type: 'line', source: 'rm-ride', layout: { 'line-cap': 'round' },
        paint: { 'line-color': dark() ? '#e5e7eb' : '#111827', 'line-width': 4, 'line-opacity': 0.55, 'line-dasharray': [2, 1.5] } });
    });
    marker(map, a, '<span class="mk-origin"></span>' + card(data.origin.name));
    marker(map, b, SVG.pin + card(data.dest.name), 'bottom', 'mk-dest');
    RM.fit(map, [a, b], { duration: 0 });
    autoDeclutter(map);
  };

  // ------------------------------------------------------------- choose a place on the map
  RM.pickMap = function (start) {
    const box = document.querySelector('[data-pick]');
    const map = RM.makeMap('pick-map', null, { keepPoi: true });
    if (!map || !box) return;
    const nameEl = box.querySelector('[data-pick-name]'), subEl = box.querySelector('[data-pick-sub]');
    const btn = box.querySelector('[data-pick-confirm]'), ret = box.dataset.ret;
    let current = null, skipReverse = false, timer, reqNo = 0;
    const clean = (t) => String(t || '').replace(/\|/g, ' ').trim();
    const poiId = (lng, lat, name, sub) => `poi:${lat.toFixed(5)},${lng.toFixed(5)}|${clean(name)}|${clean(sub)}`;
    const show = (name, sub, id) => { nameEl.textContent = name; subEl.textContent = sub || ' '; current = id; btn.disabled = false; };
    if (start) map.jumpTo({ center: LL(start), zoom: 15.5 });
    else map.jumpTo({ center: [76.78, 30.735], zoom: 13.5 });

    map.on('movestart', () => { btn.disabled = true; if (!skipReverse) { nameEl.textContent = 'Finding this place…'; subEl.textContent = ' '; } });
    map.on('moveend', () => {
      if (skipReverse) { skipReverse = false; return; }
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const c = map.getCenter(), my = ++reqNo;
        try {
          const r = await fetch(`/api/reverse?lat=${c.lat.toFixed(5)}&lng=${c.lng.toFixed(5)}`).then((x) => x.json());
          if (my === reqNo) show(r.name, r.sub, r.id);
        } catch { if (my === reqNo) show('Dropped pin', 'Chosen on map', poiId(c.lng, c.lat, 'Dropped pin', 'Chosen on map')); }
      }, 300);
    });
    // tap a shop / restaurant / salon on the map to pick it by name
    map.on('click', (e) => {
      const layers = map.getStyle().layers.filter((l) => /^poi_r/.test(l.id)).map((l) => l.id);
      const f = map.queryRenderedFeatures(e.point, { layers }).find((x) => x.properties.name);
      const lngLat = f ? f.geometry.coordinates : [e.lngLat.lng, e.lngLat.lat];
      if (f) {
        const kind = String(f.properties.subclass || f.properties.class || 'Place').replace(/_/g, ' ');
        skipReverse = true;
        show(f.properties.name, kind.charAt(0).toUpperCase() + kind.slice(1), poiId(lngLat[0], lngLat[1], f.properties.name, kind));
      }
      map.easeTo({ center: lngLat, duration: calm() ? 0 : 400 });
    });
    map.on('mousemove', (e) => {
      const layers = map.getStyle().layers.filter((l) => /^poi_r/.test(l.id)).map((l) => l.id);
      map.getCanvas().style.cursor = map.queryRenderedFeatures(e.point, { layers }).length ? 'pointer' : '';
    });
    btn.addEventListener('click', () => { if (current) location.href = ret.replace('__PT__', encodeURIComponent(current)); });
    document.querySelector('[data-locate]')?.addEventListener('click', async () => {
      try {
        const pos = await RM.geolocate();
        const p = [pos.coords.longitude, pos.coords.latitude];
        RM.youAt(map, p);
        if (RM.TRICITY.contains([p[1], p[0]])) map.easeTo({ center: p, zoom: 16.5, duration: calm() ? 0 : 600 });
        else RM.toast?.("You're outside Chandigarh, Mohali and Panchkula");
      } catch (err) { RM.toast?.(err.message); }
    });
    map.once('idle', () => map.fire('moveend'));
  };

  // ------------------------------------------------------------- geolocation
  RM.geolocate = function () {
    return new Promise((resolve, reject) => {
      if (!('geolocation' in navigator)) return reject(new Error('This browser cannot share your location.'));
      if (!window.isSecureContext) return reject(new Error('Location needs https:// or localhost.'));
      navigator.geolocation.getCurrentPosition(resolve, (err) => {
        reject(new Error({
          1: 'Location is blocked. Allow it in your browser settings.',
          2: "Couldn't find your position. Try again outdoors.",
          3: 'Finding your location took too long. Try again.',
        }[err.code] || 'Could not get your location.'));
      }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
    });
  };
})();
