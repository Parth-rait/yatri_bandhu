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
  const STOP = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 17h12M6 17a2 2 0 0 1-2-2V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v9a2 2 0 0 1-2 2M6 17v3M18 17v3M4 11h16"/></svg>';

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
  RM.drawJourney = function (map, data) {
    const g = L.layerGroup();
    const bounds = L.latLngBounds([]);
    data.legs.forEach((leg) => {
      const line = leg.type === 'bus' && leg.line && leg.line.length > 1 ? leg.line : [ll(leg.start), ll(leg.end)];
      line.forEach((p) => bounds.extend(p));
      if (leg.type === 'walk') {
        L.polyline(line, { color: '#6b7280', weight: 6, opacity: 0.95, dashArray: '0.5 10', lineCap: 'round', interactive: false }).addTo(g);
      } else {
        L.polyline(line, { color: '#ffffff', weight: 12, opacity: 0.95, interactive: false }).addTo(g);
        L.polyline(line, { color: RM.routeColor(leg.route), weight: 7, interactive: false }).addTo(g);
      }
    });
    data.legs.forEach((leg, i) => {
      const c = leg.type === 'bus' ? RM.routeColor(leg.route) : '#6b7280';
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

    // Live trip: plain-language instruction for the current step.
    const legs = data.legs;
    const key = 'rm.live.' + location.pathname;
    let ti = +(sessionStorage.getItem(key) || 0);
    const $ = (s) => document.querySelector(s);
    const btn = $('[data-live-toggle]');
    function fmtDist(d) { return d < 1000 ? `${Math.round(d / 10) * 10} m` : `${(d / 1000).toFixed(1)} km`; }
    function render(d) {
      const leg = legs[ti];
      $('[data-live-step]').textContent = `Step ${ti + 1} of ${legs.length}`;
      document.querySelectorAll('[data-progress]').forEach((p) => p.classList.toggle('done', +p.dataset.progress <= ti));
      const title = $('[data-live-title]'), sub = $('[data-live-sub]');
      const lastStep = ti === legs.length - 1;
      if (leg.type === 'walk') {
        title.textContent = lastStep ? `Walk to ${data.dest.name}` : `Walk to ${leg.end.name}`;
        sub.textContent = d == null ? '' : `${fmtDist(d)} away · about ${Math.max(1, Math.round(d * 1.3 / 75))} min`;
      } else if (d != null && d < 500) {
        title.textContent = `Get ready! Your stop is next: ${leg.end.name}`;
        sub.textContent = `${fmtDist(d)} to go. Get off the bus ${leg.route} here.`;
        if (navigator.vibrate) navigator.vibrate([150, 80, 150]);
      } else {
        title.textContent = `Ride bus ${leg.route} to ${leg.end.name}`;
        sub.textContent = d == null ? '' : `${fmtDist(d)} to go`;
      }
      if (lastStep && d != null && d < 80) { title.textContent = `You've arrived at ${data.dest.name}`; sub.textContent = 'Tap “I’ve arrived” below.'; }
    }
    function update(pos) {
      const here = L.latLng(placeYou(pos, false));
      while (ti < legs.length - 1 && here.distanceTo(ll(legs[ti].end)) < 60) ti++;
      sessionStorage.setItem(key, ti);
      render(here.distanceTo(ll(legs[ti].end)));
    }
    btn?.addEventListener('click', async () => {
      const txt = btn.querySelector('span');
      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId); watchId = null;
        btn.setAttribute('aria-pressed', 'false'); txt.textContent = 'Turn on live location';
        return;
      }
      try {
        const first = await RM.geolocate();
        update(first);
        RM.move(map, [first.coords.latitude, first.coords.longitude], { zoom: 16 });
        watchId = navigator.geolocation.watchPosition(update, () => {}, { enableHighAccuracy: true, maximumAge: 5000 });
        btn.setAttribute('aria-pressed', 'true'); txt.textContent = 'Stop live location';
      } catch (err) { RM.toast?.(err.message); }
    });
  };

  // ------------------------------------------------------------- stops, lines, explore
  RM.nearbyMap = function (here, stops) {
    const map = RM.makeMap('nearby-map');
    if (!map) return;
    const b = L.latLngBounds([[here.lat, here.lng]]);
    RM.youMarker([here.lat, here.lng]).addTo(map);
    stops.forEach((s, i) => {
      b.extend([s.lat, s.lng]);
      const m = pin([s.lat, s.lng], `<span class="pin-num">${i + 1}</span>`, '')
        .bindTooltip(esc(s.name), { direction: 'top', offset: [0, -16], className: 'rm-label', permanent: i === 0 })
        .on('click', () => { location.href = `/stop/${encodeURIComponent(s.id)}`; })
        .addTo(map);
    });
    RM.move(map, b, { animate: false });
  };

  RM.stopMap = function (stop, lines) {
    const map = RM.makeMap('stop-map');
    if (!map) return;
    lines.forEach((l) => L.polyline(l.line, { color: RM.routeColor(l.route), weight: 4, opacity: 0.6, interactive: false }).addTo(map));
    pin([stop.lat, stop.lng], `<span class="pin-stop">${STOP}</span>`, '', 40).addTo(map);
    map.setView([stop.lat, stop.lng], 15, { animate: false });
  };

  RM.lineMap = function (no, shape, stops) {
    const map = RM.makeMap('line-map');
    if (!map) return;
    const c = RM.routeColor(no);
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
