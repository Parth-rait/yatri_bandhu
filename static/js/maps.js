/* RouteMate maps. One visual language everywhere:
 *   bus  = thick solid line in the route's colour (same colour as its number badge)
 *   walk = grey dotted line
 *   numbered circles = the numbered steps in the list under the map
 *   blue dot = you (live location)
 */
(function () {
  'use strict';
  const RM = (window.RM = window.RM || {});
  const root = document.documentElement;

  const PALETTE = ['#2563eb', '#c026d3', '#ea580c', '#0d9488', '#7c3aed', '#db2777',
                   '#0891b2', '#4d7c0f', '#b45309', '#4f46e5', '#dc2626', '#059669'];
  RM.routeColor = (no) => {
    let h = 7;
    for (const c of String(no)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return PALETTE[h % PALETTE.length];
  };
  const calm = () => root.classList.contains('reduce-motion') || matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ll = (p) => [p.lat, p.lng];
  const FLAG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg>';
  const STOP = '<svg width="18" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 17h12M6 17a2 2 0 0 1-2-2V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v9a2 2 0 0 1-2 2M6 17v3M18 17v3M4 11h16"/></svg>';

  RM.makeMap = function (id) {
    const el = document.getElementById(id);
    if (!el || !window.L) return null;
    const map = L.map(el, { zoomControl: false, attributionControl: true });
    L.control.zoom({ position: 'bottomleft' }).addTo(map);
    // Standard OSM tiles, toned down by CSS (--tiles) so the route carries the meaning.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    map.setView([30.715, 76.77], 12);
    return map;
  };

  RM.move = (map, target, opts = {}) => {
    const pad = innerWidth > 960 ? [48, 48] : [32, 32];
    if (target.getNorthEast) { if (target.isValid()) map.fitBounds(target, { padding: pad, maxZoom: 16, animate: !calm(), ...opts }); }
    else map.setView(target, opts.zoom || 16, { animate: !calm() });
  };

  function pin(latlng, html, cls, size = 30) {
    return L.marker(latlng, {
      icon: L.divIcon({ className: 'rm-pin ' + cls, html, iconSize: [size, size], iconAnchor: [size / 2, size / 2] }),
      keyboard: false,
    });
  }
  RM.youMarker = (latlng) => pin(latlng, '<span class="you-dot"></span>', '', 22);
  const destPin = (latlng) => L.marker(latlng, {
    icon: L.divIcon({ className: 'rm-pin', html: `<span class="pin-dest">${FLAG}</span>`, iconSize: [34, 34], iconAnchor: [4, 38] }),
    keyboard: false,
  });
  function label(marker, text, dir = 'right') {
    const off = { right: [16, 0], left: [-16, 0], top: [0, -16] }[dir] || [0, -16];
    marker.bindTooltip(esc(text), { permanent: true, direction: dir, offset: off, className: 'rm-label' });
    return marker;
  }

  // ------------------------------------------------------------- journeys
  const BUS_COLORS = ['#2563eb', '#7c3aed', '#0891b2'];
  RM.drawJourney = function (map, data) {
    const g = L.layerGroup();
    const bounds = L.latLngBounds([]);
    let bi = 0;
    data.legs.forEach((leg) => { if (leg.type === 'bus') leg.color = BUS_COLORS[bi++ % BUS_COLORS.length]; });
    data.legs.forEach((leg) => {
      const line = leg.type === 'bus' && leg.line && leg.line.length > 1 ? leg.line : [ll(leg.start), ll(leg.end)];
      line.forEach((p) => bounds.extend(p));
      if (leg.type === 'walk') {
        L.polyline(line, { color: '#6b7280', weight: 6, opacity: 0.95, dashArray: '0.5 10', lineCap: 'round', interactive: false }).addTo(g);
      } else {
        L.polyline(line, { color: '#ffffff', weight: 12, opacity: 0.95, interactive: false }).addTo(g);
        L.polyline(line, { color: leg.color, weight: 7, interactive: false }).addTo(g);
      }
    });
    data.legs.forEach((leg, i) => {
      const c = leg.type === 'bus' ? leg.color : '#6b7280';
      const m = pin(ll(leg.start), `<span class="pin-num" style="--c:${c}">${i + 1}</span>`, '');
      const prevBus = data.legs.slice(0, i).some((l) => l.type === 'bus');
      if (i === 0) label(m, leg.type === 'bus' ? `Board ${leg.route}` : 'Start');
      else if (leg.type === 'bus') label(m, prevBus ? `Change to ${leg.route}` : `Board ${leg.route}`);
      m.addTo(g);
      const next = data.legs[i + 1];
      if (leg.type === 'bus' && (!next || next.type === 'walk')) {
        label(pin(ll(leg.end), '<span class="pin-off"></span>', '', 18), 'Get off', 'left').addTo(g);
      }
    });
    const last = data.legs[data.legs.length - 1];
    label(destPin(ll(last.end)), data.dest ? data.dest.name : 'Destination', 'top').addTo(g);
    g.bounds = bounds;
    // Labels are drawn in priority order (destination last = most important), so when two collide
    // the less important one is hidden. Re-checked on every zoom.
    g.declutter = () => {
      const layers = [];
      g.eachLayer((l) => { if (l.getTooltip && l.getTooltip() && l.getTooltip().getElement()) layers.push(l.getTooltip().getElement()); });
      layers.reverse();
      const kept = [];
      layers.forEach((el) => {
        el.classList.remove('is-hidden');
        const r = el.getBoundingClientRect();
        const hit = kept.some((k) => r.left < k.right + 4 && r.right > k.left - 4 && r.top < k.bottom + 2 && r.bottom > k.top - 2);
        if (hit) el.classList.add('is-hidden'); else kept.push(r);
      });
    };
    return g;
  };

  RM.routesMap = function (data) {
    const map = RM.makeMap('routes-map');
    if (!map) return;
    if (data.legs && data.legs.length) {
      const g = RM.drawJourney(map, data).addTo(map);
      RM.move(map, g.bounds, { animate: false });
      map.on('zoomend moveend', g.declutter);
      setTimeout(g.declutter, 50);
    } else {
      const b = L.latLngBounds([ll(data.origin), ll(data.dest)]);
      pin(ll(data.origin), '<span class="pin-num" style="--c:#2563eb">A</span>', '').addTo(map);
      destPin(ll(data.dest)).addTo(map);
      RM.move(map, b, { animate: false });
    }
    document.querySelector('[data-locate]')?.addEventListener('click', async () => {
      try { const p = await RM.geolocate(); RM.youMarker([p.coords.latitude, p.coords.longitude]).addTo(map); RM.move(map, [p.coords.latitude, p.coords.longitude], { zoom: 15 }); }
      catch (err) { RM.toast?.(err.message); }
    });
  };

  RM.journeyMap = function (data, { live = false } = {}) {
    const map = RM.makeMap('journey-map');
    if (!map) return;
    const g = RM.drawJourney(map, data).addTo(map);
    RM.move(map, g.bounds, { animate: false });
    map.on('zoomend moveend', g.declutter);
    setTimeout(g.declutter, 50);
    document.querySelector('[data-fit]')?.addEventListener('click', () => RM.move(map, g.bounds));

    // tapping a step zooms the map to that part of the trip
    document.querySelectorAll('[data-leg]').forEach((el) => {
      const show = () => {
        const leg = data.legs[+el.dataset.leg];
        const pts = leg.type === 'bus' && leg.line ? leg.line : [ll(leg.start), ll(leg.end)];
        RM.move(map, L.latLngBounds(pts), { maxZoom: 17 });
        document.querySelectorAll('[data-leg]').forEach((s) => s.classList.toggle('is-active', s === el));
        if (innerWidth < 960) document.querySelector('.map-wrap')?.scrollIntoView({ behavior: calm() ? 'auto' : 'smooth' });
      };
      el.addEventListener('click', (e) => { if (!e.target.closest('a,summary')) show(); });
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.target.closest('a,summary')) { e.preventDefault(); show(); } });
    });

    let you = null, acc = null, watchId = null;
    function placeYou(pos, follow) {
      const p = [pos.coords.latitude, pos.coords.longitude];
      if (!you) {
        you = RM.youMarker(p).addTo(map);
        acc = L.circle(p, { radius: 50, color: '#2563eb', weight: 1, fillOpacity: 0.08, interactive: false }).addTo(map);
      }
      you.setLatLng(p); acc.setLatLng(p).setRadius(Math.min(pos.coords.accuracy, 300));
      if (follow) RM.move(map, p, { zoom: 16 });
      return p;
    }
    document.querySelector('[data-locate]')?.addEventListener('click', async () => {
      try { placeYou(await RM.geolocate(), true); } catch (err) { RM.toast?.(err.message); }
    });
    if (!live) return;

    // Scheduled bus position: waits at the boarding stop until departure, then moves along the route.
    const loaded = Date.now();
    const nowMin = () => data.now + (Date.now() - loaded) / 60000;
    const bus = data.legs.find((l) => l.type === 'bus');
    if (bus && bus.line && bus.line.length > 1) {
      const busMarker = pin(ll(bus.start), `<span class="pin-bus">${STOP}</span>`, '', 36)
        .bindTooltip('', { permanent: true, direction: 'top', offset: [0, -20], className: 'rm-bubble' }).addTo(map);
      const along = (line, f) => {
        const seg = line.map((p, i) => (i ? L.latLng(p).distanceTo(line[i - 1]) : 0));
        const total = seg.reduce((a, b) => a + b, 0);
        let d = total * f;
        for (let i = 1; i < line.length; i++) {
          if (d <= seg[i]) { const t = seg[i] ? d / seg[i] : 0; return [line[i - 1][0] + (line[i][0] - line[i - 1][0]) * t, line[i - 1][1] + (line[i][1] - line[i - 1][1]) * t]; }
          d -= seg[i];
        }
        return line[line.length - 1];
      };
      const tick = () => {
        const t = nowMin();
        const minsEl = document.querySelector('[data-live-mins]');
        let text;
        if (t < bus.depart) {
          busMarker.setLatLng(ll(bus.start));
          const m = Math.max(0, Math.round(bus.depart - t));
          text = m ? `Arriving in<br>${m} min` : 'Arriving now';
          if (minsEl) minsEl.textContent = `${m} min`;
        } else if (t < bus.arrive) {
          busMarker.setLatLng(along(bus.line, (t - bus.depart) / Math.max(1, bus.arrive - bus.depart)));
          const m = Math.round(bus.arrive - t);
          text = `${m} min to<br>your stop`;
          if (minsEl) minsEl.closest('[data-live-title]').innerHTML = `On the bus · <span data-live-mins>${m} min</span> left`;
        } else {
          busMarker.setLatLng(ll(bus.end));
          text = 'At your stop';
          const title = document.querySelector('[data-live-title]');
          if (title) title.textContent = 'Bus has reached your stop';
        }
        busMarker.setTooltipContent(text);
      };
      tick();
      setInterval(tick, 15000);
    }

    // Live trip: plain-language instruction for the current step.
    const legs = data.legs;
    const key = 'rm.live.' + location.pathname;
    let ti = +(sessionStorage.getItem(key) || 0);
    const $ = (s) => document.querySelector(s);
    const btns = document.querySelectorAll('[data-live-toggle]');
    function fmtDist(d) { return d < 1000 ? `${Math.round(d / 10) * 10} m` : `${(d / 1000).toFixed(1)} km`; }
    function render(d) {
      const leg = legs[ti];
      document.querySelectorAll('[data-node]').forEach((n) => n.classList.toggle('on', +n.dataset.node <= (leg.type === 'bus' ? 1 : ti === legs.length - 1 && ti > 0 ? 2 : 0)));
      document.querySelectorAll('[data-bar]').forEach((b) => b.classList.toggle('done', +b.dataset.bar < (leg.type === 'bus' ? 1 : ti === legs.length - 1 && ti > 0 ? 2 : 0)));
      const sub = $('[data-live-sub]');
      if (!sub || d == null) return;
      const fmt = d < 1000 ? `${Math.round(d / 10) * 10} m` : `${(d / 1000).toFixed(1)} km`;
      if (leg.type === 'walk') sub.textContent = `Walk to ${leg.end.name} · ${fmt}`;
      else if (d < 500) { sub.textContent = `Get ready: ${leg.end.name} is next`; if (navigator.vibrate) navigator.vibrate([150, 80, 150]); }
      else sub.textContent = `${fmt} to ${leg.end.name}`;
    }
    function update(pos) {
      const here = L.latLng(placeYou(pos, false));
      while (ti < legs.length - 1 && here.distanceTo(ll(legs[ti].end)) < 60) ti++;
      sessionStorage.setItem(key, ti);
      render(here.distanceTo(ll(legs[ti].end)));
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
        RM.move(map, [first.coords.latitude, first.coords.longitude], { zoom: 16 });
        watchId = navigator.geolocation.watchPosition(update, () => {}, { enableHighAccuracy: true, maximumAge: 5000 });
        btns.forEach((b) => b.setAttribute('aria-pressed', 'true'));
        RM.toast?.("Alert on: we'll tell you before your stop");
      } catch (err) { RM.toast?.(err.message); }
    }));
  };

  // ------------------------------------------------------------- stops, lines, explore
  RM.nearbyMap = function (here, stops, buses = []) {
    const map = RM.makeMap('nearby-map');
    if (!map) return;
    const b = L.latLngBounds([[here.lat, here.lng]]);
    RM.youMarker([here.lat, here.lng]).addTo(map);
    L.circle([here.lat, here.lng], { radius: 250, color: '#2563eb', weight: 0, fillOpacity: 0.08, interactive: false }).addTo(map);
    const shown = new Set();
    buses.forEach((bus) => {
      if (shown.has(bus.stop.id) || shown.size >= 3) return;
      shown.add(bus.stop.id);
      b.extend([bus.stop.lat, bus.stop.lng]);
      pin([bus.stop.lat, bus.stop.lng], `<span class="pin-bus">${STOP}</span>`, '', 36)
        .bindTooltip(`<b>Route ${esc(bus.route)}</b><br>${bus.mins <= 0 ? 'now' : bus.mins + ' min away'}`, { permanent: true, direction: 'top', offset: [0, -20], className: 'rm-label' })
        .on('click', () => { location.href = `/stop/${encodeURIComponent(bus.stop.id)}`; })
        .addTo(map);
    });
    stops.forEach((s) => {
      if (shown.has(s.id)) return;
      b.extend([s.lat, s.lng]);
      pin([s.lat, s.lng], '<span class="pin-dot" style="--c:#2563eb"></span>', '', 14)
        .bindTooltip(esc(s.name), { direction: 'top', className: 'rm-label' })
        .on('click', () => { location.href = `/stop/${encodeURIComponent(s.id)}`; }).addTo(map);
    });
    RM.move(map, b, { animate: false });
  };

  RM.stopMap = function (stop, lines) {
    const map = RM.makeMap('stop-map');
    if (!map) return;
    lines.forEach((l) => L.polyline(l.line, { color: '#2563eb', weight: 4, opacity: 0.35, interactive: false }).addTo(map));
    pin([stop.lat, stop.lng], `<span class="pin-stop">${STOP}</span>`, '', 40).addTo(map);
    map.setView([stop.lat, stop.lng], 15, { animate: false });
  };

  RM.lineMap = function (no, shape, stops) {
    const map = RM.makeMap('line-map');
    if (!map) return;
    const c = '#2563eb';
    L.polyline(shape, { color: '#fff', weight: 11, interactive: false }).addTo(map);
    const line = L.polyline(shape, { color: c, weight: 6, interactive: false }).addTo(map);
    stops.forEach((s, i) => {
      const end = i === 0 || i === stops.length - 1;
      const m = pin([s.lat, s.lng], `<span class="pin-dot" style="--c:${c}"></span>`, '', 14)
        .bindTooltip(esc(s.name), { direction: 'top', offset: [0, -10], className: 'rm-label', permanent: end })
        .on('click', () => { location.href = `/stop/${encodeURIComponent(s.id)}`; });
      m.addTo(map);
    });
    RM.move(map, line.getBounds(), { animate: false });
  };

  RM.exploreMap = function (origin, places, fares, times, outPlaces, kind, routesUrl, fromId) {
    const map = RM.makeMap('explore-map');
    if (!map || !origin) return;
    const b = L.latLngBounds([ll(origin)]);
    label(pin(ll(origin), '<span class="pin-num" style="--c:#0f7a57">A</span>', ''), origin.name, 'top').addTo(map);
    outPlaces.forEach((p) => {
      L.circleMarker(ll(p), { radius: 5, color: '#fff', weight: 2, fillColor: '#9aa1b2', fillOpacity: 1 })
        .bindTooltip(esc(p.name), { direction: 'top', className: 'rm-label' }).addTo(map);
    });
    const go = (p) => { location.href = `${routesUrl}?from=${encodeURIComponent(fromId)}&to=place:${p.id}&mode=${kind === 'budget' ? 'cheapest' : 'fastest'}`; };
    places.forEach((p) => {
      b.extend(ll(p));
      L.circleMarker(ll(p), { radius: 7, color: '#fff', weight: 2, fillColor: '#0f7a57', fillOpacity: 1 })
        .bindTooltip(esc(p.name), { direction: 'top', className: 'rm-label' }).on('click', () => go(p)).addTo(map);
    });
    // Price/time tags only where they have room, so clusters stay readable.
    const chips = L.layerGroup().addTo(map);
    function layout() {
      chips.clearLayers();
      const taken = [];
      places.forEach((p, i) => {
        const pt = map.latLngToContainerPoint(ll(p));
        if (taken.some((q) => Math.abs(q.x - pt.x) < 72 && Math.abs(q.y - pt.y) < 28)) return;
        taken.push(pt);
        const txt = kind === 'budget' ? (fares[i] ? `₹${fares[i]}` : 'Free') : `${times[i]} min`;
        pin(ll(p), `<span class="pin-chip">${esc(txt)}</span>`, 'pin-chip-wrap', 0).on('click', () => go(p)).addTo(chips);
      });
    }
    RM.move(map, b, { animate: false, maxZoom: 14 });
    layout();
    map.on('zoomend', layout);
  };

  // ------------------------------------------------------------- geolocation
  RM.geolocate = function () {
    return new Promise((resolve, reject) => {
      if (!('geolocation' in navigator)) return reject(new Error('This browser cannot share your location. Search for a place instead.'));
      if (!window.isSecureContext) return reject(new Error('Location only works on https:// or localhost. Search for a place instead.'));
      navigator.geolocation.getCurrentPosition(resolve, (err) => {
        reject(new Error({
          1: 'Location is blocked. Allow it for this site in your browser settings, or search for a place.',
          2: "Couldn't find your position. Try again outdoors, or search for a place.",
          3: 'Finding your location took too long. Try again, or search for a place.',
        }[err.code] || 'Could not get your location.'));
      }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
    });
  };
})();
