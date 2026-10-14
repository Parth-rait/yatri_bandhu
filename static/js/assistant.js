/* Bandhu, the in-app buddy.
 * A small sheet with one short line from Bandhu, a "Where to?" box with live suggestions,
 * and big tiles that act on the screen you're on (track, book, sort, share, SOS…).
 * Understanding is simple on-device rules (no AI service, no cost). To plug in an AI model later,
 * replace `answer()` with a call to your backend that returns a line, a mood and tiles.
 */
(function () {
  'use strict';
  const sheet = document.querySelector('[data-bandhu-sheet]');
  const fab = document.querySelector('[data-bandhu-open]');
  if (!sheet || !fab) return;
  const $ = (s, el = document) => el.querySelector(s);
  const panel = $('[data-bandhu-panel]', sheet);
  const me = $('[data-bandhu-me] .bandhu', sheet);
  const lineEl = $('[data-bandhu-line]', sheet);
  const tilesEl = $('[data-bandhu-tiles]', sheet);
  const form = $('[data-bandhu-form]', sheet);
  const input = $('input', form);
  const peek = $('[data-bandhu-peek]');
  const page = document.body.dataset.endpoint;
  const { from = 'place:plaksha', name = '', trip = '', tripTo = '' } = sheet.dataset;
  const calm = document.documentElement.classList.contains('reduce-motion');
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const buzz = (ms = 8) => { try { navigator.vibrate?.(ms); } catch (e) { /* not supported */ } };
  const wait = (ms) => new Promise((r) => setTimeout(r, calm ? 0 : ms));
  const hour = new Date().getHours();
  const late = hour >= 21 || hour < 5;

  // ---------------------------------------------------------------- personality: moods, hop, typing, eyes
  const MOODS = ['happy', 'wave', 'think', 'worry', 'love'];
  let moodTimer;
  function mood(m, hold = 2600) {
    [me, $('.bandhu', fab)].forEach((svg) => { svg.classList.remove(...MOODS.map((x) => 'mood-' + x)); if (m) svg.classList.add('mood-' + m); });
    clearTimeout(moodTimer);
    if (m && hold) moodTimer = setTimeout(() => mood(''), hold);
  }
  function hop(el = me) { el.classList.remove('hop'); void el.getBoundingClientRect(); el.classList.add('hop'); }
  let typeRun = 0;
  async function speak(text, m = '', hold) {
    const run = ++typeRun;
    mood(m, hold);
    if (m === 'happy' || m === 'wave' || m === 'love') hop();
    if (calm) { lineEl.textContent = text; return; }
    lineEl.textContent = '';
    for (const ch of Array.from(text)) {
      if (run !== typeRun) return;
      lineEl.textContent += ch;
      await new Promise((r) => setTimeout(r, 16));
    }
  }
  // eyes follow your finger / pointer
  let raf = 0, px = 0, py = 0;
  function look() {
    raf = 0;
    document.querySelectorAll('.bandhu-fab .bandhu-look, [data-bandhu-me] .bandhu-look').forEach((g) => {
      const r = g.closest('svg').getBoundingClientRect();
      if (!r.width) return;
      const dx = px - (r.left + r.width / 2), dy = py - (r.top + r.height * 0.45), d = Math.hypot(dx, dy) || 1;
      const k = Math.min(3, d / 60);
      g.style.transform = `translate(${(dx / d) * k}px, ${(dy / d) * k}px)`;
    });
  }
  if (!calm) window.addEventListener('pointermove', (e) => { px = e.clientX; py = e.clientY; if (!raf) raf = requestAnimationFrame(look); }, { passive: true });

  // ---------------------------------------------------------------- tiles: big buttons that do things
  const urlWith = (path, params) => {
    const u = new URL(location.href);
    u.pathname = path;
    Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
    return u.pathname + u.search;
  };
  function pageTiles() {
    const out = [];
    const add = (t) => { if (!t.sel || $(t.sel)) out.push(t); };
    if (trip && page !== 'trip_live') add({ e: '🚌', label: 'My trip', sub: tripTo, href: trip, hot: true });
    if (page === 'routes') {
      add({ e: '💰', label: 'Cheapest', href: urlWith('/routes', { mode: 'cheapest' }) });
      add({ e: '⚡', label: 'Fastest', href: urlWith('/routes', { mode: 'fastest' }) });
      add({ e: '🔁', label: 'Round trip', sel: '.tripkind a[href*="trip=round"]:not([aria-current])' });
      add({ e: '🛺', label: 'Auto or cab', sel: '.modes a[href*="by=ride"]:not([aria-current])' });
    } else if (page === 'journey') {
      add({ e: '👀', label: 'Track bus', sel: '.sticky-cta button[type=submit]', hot: true });
      add({ e: '🎟️', label: 'Book ticket', sel: '.sticky-cta a[href*="/book"]' });
      add({ e: '🛺', label: 'Ride instead', href: urlWith('/routes', { by: 'ride' }) });
    } else if (page === 'trip_live') {
      add({ e: '🔔', label: 'Remind me', sub: 'before my stop', sel: '[data-live-toggle][aria-pressed="false"]', hot: true });
      add({ e: '🎯', label: 'Follow bus', sel: '[data-follow-bus]' });
      add({ e: '💌', label: 'Share trip', sel: 'a[href*="/share"]' });
      add({ e: '🚨', label: 'SOS 112', href: 'tel:112', danger: true });
    }
    [{ e: '📍', label: 'Near me', href: '/nearby' }, { e: '⭐', label: 'Saved', href: '/saved' },
     { e: '🎟️', label: 'Fares', href: '/passes' }, { e: '🛟', label: 'Safety', say: 'safety' }]
      .forEach((t) => { if (out.length < 4 && !out.some((o) => o.label === t.label)) out.push(t); });
    return out.slice(0, 4);
  }
  let tileFns = [];
  function tiles(list, wide = false) {
    tileFns = list;
    tilesEl.classList.toggle('wide', wide);
    tilesEl.innerHTML = list.map((t, i) => {
      const cls = `bandhu-tile${t.hot ? ' hot' : ''}${t.danger ? ' danger' : ''}`;
      const body = `<span class="bt-e" aria-hidden="true">${t.e}</span><span class="bt-t"><b>${esc(t.label)}</b>${t.sub ? `<small>${esc(t.sub)}</small>` : ''}</span>`;
      return t.href
        ? `<a class="${cls}" style="--i:${i}" href="${esc(t.href)}" data-tile="${i}">${body}</a>`
        : `<button type="button" class="${cls}" style="--i:${i}" data-tile="${i}">${body}</button>`;
    }).join('');
  }
  async function runTile(t, el) {
    buzz();
    el?.classList.add('pressed');
    if (t.say) return ask(t.say, false);
    if (t.sel) {
      speak('On it! ✨', 'happy');
      await wait(380);
      close();
      const target = $(t.sel);
      target?.scrollIntoView({ block: 'center', behavior: calm ? 'auto' : 'smooth' });
      target?.click();
      return;
    }
    if (t.go) { speak('Chalo! 🚀', 'happy'); await wait(420); location.href = t.go; }
  }
  tilesEl.addEventListener('click', (e) => {
    const el = e.target.closest('[data-tile]');
    if (!el) return;
    const t = tileFns[+el.dataset.tile];
    if (t.href) { buzz(); return; }    // plain link: let the browser follow it
    e.preventDefault();
    runTile(t, el);
  });

  // ---------------------------------------------------------------- places: live suggestions while you type
  async function places(text) {
    const [local, far] = await Promise.all([
      fetch(`/api/search?q=${encodeURIComponent(text)}`).then((r) => r.json()).catch(() => []),
      fetch(`/api/places?q=${encodeURIComponent(text)}`).then((r) => r.json()).catch(() => []),
    ]);
    const word = text.toLowerCase().split(' ')[0];
    const onTopic = far.filter((h) => h.name.toLowerCase().includes(word));
    const seen = new Set();
    return local.concat(onTopic.length ? onTopic : far)
      .filter((h) => !seen.has(h.name.toLowerCase()) && seen.add(h.name.toLowerCase())).slice(0, 4);
  }
  const placeTiles = (hits) => hits.map((h, i) => ({ e: i ? '📍' : '🚌', label: h.name, sub: h.sub || '', hot: !i,
    go: `/routes?from=${encodeURIComponent(from)}&to=${encodeURIComponent(h.id)}` }));
  async function goTo(text) {
    speak('Hmm, let me look…', 'think', 0);
    const hits = await places(text);
    if (!hits.length) {
      speak(`Can't find "${text}" 😅`, 'worry');
      return tiles([{ e: '🔎', label: 'Search', href: `/search?q=${encodeURIComponent(text)}` }, ...pageTiles().slice(0, 3)]);
    }
    speak(hits.length > 1 ? 'Chalo! Which one? 👇' : 'Found it! Tap to go 👇', 'happy');
    tiles(placeTiles(hits), true);
  }

  // ---------------------------------------------------------------- understanding (simple rules), short replies
  const has = (q, ...words) => words.some((w) => new RegExp(`(^|\\W)${w}`).test(q));
  const QUESTION = /\?|^(where|what|how|when|which|who|is|can|do|does|show|help|book|track|my|i |take|go )|\b(fare|price|cost|ticket|pass|safe|sos|cab|auto|taxi|uber|ola|rapido|electric|near|nearest|save|tour|thank|joke|hi|hello|hey|namaste|round)\b/;
  async function answer(raw) {
    const q = raw.toLowerCase().trim();
    const dest = q.match(/(?:take me to|go to|get to|way to|route to|bus to|reach|going to|travel to|directions to|how (?:do i|to) (?:get|go) to)\s+(.+)/);
    if (dest) return goTo(dest[1].replace(/[?.!]+$/, ''));
    if (has(q, 'where is my bus', 'my bus', 'my trip', 'track')) {
      if (page === 'journey' && $('.sticky-cta button[type=submit]')) return runTile({ sel: '.sticky-cta button[type=submit]' });
      if (!trip) { speak('No trip yet. Where to? 🚌', 'think'); input.focus(); return tiles(pageTiles()); }
      speak('On its way! Opening… 🚌', 'happy'); await wait(650); location.href = trip; return;
    }
    if (has(q, 'near', 'nearest', 'closest', 'bus stop')) { speak('Buses around you 📍', 'happy'); await wait(650); location.href = '/nearby'; return; }
    if (has(q, 'fare', 'price', 'cost', 'how much', 'ticket', 'pass', 'student')) {
      speak('₹10 · ₹20 · ₹25 by distance. Pass ₹350/mo 🎓', 'happy', 0);
      return tiles([{ e: '🎓', label: 'Student pass', href: '/passes', hot: true }, { e: '🎟️', label: 'My tickets', href: '/tickets' }]);
    }
    if (has(q, 'safe', 'sos', 'emergency', 'help me', 'police', 'women', 'night', 'scared', 'unsafe', 'follow')) {
      speak('I\'ve got you. One tap to call 🛟', 'worry', 0);
      return tiles([{ e: '🚨', label: 'Call 112', sub: 'Police', href: 'tel:112', danger: true }, { e: '📞', label: 'Call 1091', sub: 'Women helpline', href: 'tel:1091' }]
        .concat(trip ? [{ e: '💌', label: 'Share my trip', href: trip.replace(/\/?$/, '') + '/share' }] : []));
    }
    if (has(q, 'cab', 'auto', 'taxi', 'uber', 'ola', 'rapido', 'ride')) {
      if ($('.modes a[href*="by=ride"]:not([aria-current])')) return runTile({ sel: '.modes a[href*="by=ride"]:not([aria-current])' });
      speak('Where to? I\'ll compare rides 🛺', 'think'); input.focus(); return;
    }
    if (has(q, 'round', 'return', 'come back')) {
      if ($('.tripkind a[href*="trip=round"]')) return runTile({ sel: '.tripkind a[href*="trip=round"]' });
      speak('Pick a place, then tap Round trip 🔁', 'think'); input.focus(); return;
    }
    if (has(q, 'electric', 'green', 'eco', 'co2', 'pollution')) {
      speak('⚡ 23A, 206, 202, 239, 6 and 7 go electric!', 'love', 0);
      return tiles([{ e: '⚡', label: 'All routes', href: '/lines/all', hot: true }]);
    }
    if (has(q, 'save', 'favourite', 'favorite', 'home', 'work')) { speak('Your places ⭐', 'happy'); await wait(650); location.href = '/saved'; return; }
    if (has(q, 'tour', 'guide', 'how to use', 'teach', 'show me around')) { speak('Follow me! 🧭', 'wave'); await wait(600); close(); window.RM?.replayGuide?.(); return; }
    if (has(q, 'joke', 'funny', 'bored')) return speak(['I never miss a bus… I am one 🚌', 'Traffic? I just honk and smile 😄', 'Sector 17 se pyaar hai, traffic se nahi 😅'][Math.floor(Math.random() * 3)], 'happy');
    if (has(q, 'who are you', 'your name', 'bandhu')) return speak('Bandhu! Your bus buddy 🚌💙', 'wave');
    if (/\b(hi|hello|hey|namaste)\b/.test(q)) return speak(`Namaste${name ? ' ' + name : ''}! 🙏`, 'wave');
    if (has(q, 'thank', 'love', 'nice', 'great', 'cute')) return speak('Aww, anytime! 💙', 'love');
    if (q.split(/\s+/).length <= 4 && !q.includes('?')) return goTo(q);
    speak('Didn\'t get that 😅 Try a place!', 'think');
    tiles(pageTiles());
  }
  async function ask(text, clear = true) {
    if (clear) input.value = '';
    speak('Hmm…', 'think', 0);
    await wait(320);
    await answer(text);
  }

  // live suggestions while typing a place
  let typeTimer, typedFor = '';
  input.addEventListener('input', () => {
    clearTimeout(typeTimer);
    const v = input.value.trim();
    if (!v) { speak(openLine()); return tiles(pageTiles()); }
    if (v.length < 2 || QUESTION.test(v.toLowerCase())) return;
    typeTimer = setTimeout(async () => {
      typedFor = v;
      mood('think', 0);
      const hits = await places(v);
      if (typedFor !== v || input.value.trim() !== v) return;
      mood(hits.length ? 'happy' : 'worry');
      if (hits.length) tiles(placeTiles(hits), true);
    }, 260);
  });
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const v = input.value.trim();
    if (!v) return;
    clearTimeout(typeTimer);
    input.blur();
    buzz();
    ask(v);
  });

  // ---------------------------------------------------------------- open / close / drag down
  const LINES = {
    app_home: hour < 12 ? 'Subah ki bus? Kahan chalein? ☀️' : 'Kahan chalein? 🚌',
    routes: 'Top one\'s my pick 👆',
    journey: 'Ready when you are!',
    trip_live: 'I\'m watching your bus 👀',
    nearby: 'Buses around you 📍',
    lines: 'Any route number, just ask!',
    saved: 'Your favourite spots ⭐',
  };
  const openLine = () => (late ? 'Late ride? I\'m right here 🌙' : LINES[page] || 'How can I help? 😊');
  let greeted = false;
  try { greeted = !!sessionStorage.getItem('yb.bandhu.hi'); } catch (e) { /* private mode */ }
  function open() {
    hidePeek();
    buzz(10);
    sheet.hidden = false;
    sheet.classList.remove('closing');
    panel.style.transform = '';
    document.body.classList.add('bandhu-open');
    tiles(pageTiles());
    if (!greeted) {
      greeted = true;
      try { sessionStorage.setItem('yb.bandhu.hi', '1'); } catch (e) { /* private mode */ }
      speak(`${hour < 12 ? 'Good morning' : hour < 17 ? 'Hey' : 'Good evening'}${name ? ', ' + name : ''}! 👋`, 'wave');
      setTimeout(() => { if (!sheet.hidden && !input.value) speak(openLine()); }, calm ? 0 : 1700);
    } else speak(openLine(), 'happy');
    if (matchMedia('(pointer: fine)').matches) setTimeout(() => input.focus(), 60);
  }
  function close() {
    if (sheet.hidden) return;
    sheet.classList.add('closing');
    document.body.classList.remove('bandhu-open');
    setTimeout(() => { sheet.hidden = true; sheet.classList.remove('closing'); panel.style.transform = ''; input.value = ''; }, calm ? 0 : 200);
    hop($('.bandhu', fab));
  }
  fab.addEventListener('click', open);
  me.addEventListener('click', () => { buzz(); hop(); mood(['happy', 'love', 'wave'][Math.floor(Math.random() * 3)]); });
  sheet.querySelectorAll('[data-bandhu-close]').forEach((b) => b.addEventListener('click', close));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !sheet.hidden) close(); });

  // swipe the sheet down to close (phones)
  const drag = $('[data-bandhu-drag]', sheet);
  let y0 = null, dy = 0;
  drag.addEventListener('pointerdown', (e) => {
    if (e.target.closest('button, a, input') || matchMedia('(min-width: 960px)').matches) return;
    y0 = e.clientY; dy = 0; panel.style.transition = 'none'; drag.setPointerCapture(e.pointerId);
  });
  drag.addEventListener('pointermove', (e) => {
    if (y0 === null) return;
    dy = Math.max(0, e.clientY - y0);
    panel.style.transform = `translateY(${dy}px)`;
  });
  const endDrag = () => {
    if (y0 === null) return;
    y0 = null; panel.style.transition = '';
    if (dy > 90) close(); else panel.style.transform = '';
  };
  drag.addEventListener('pointerup', endDrag);
  drag.addEventListener('pointercancel', endDrag);

  // ---------------------------------------------------------------- peek: one short nudge per screen per visit
  let peekTimer;
  function hidePeek() { clearTimeout(peekTimer); peek.classList.remove('show'); peek.hidden = true; }
  function peekText() {
    if (trip && page !== 'trip_live') return 'Your bus is on the way 👀';
    if (page === 'routes') { const p = $('.opt.best .green')?.textContent; if (p) return `Best one's ${p} 👆`; }
    if (page === 'journey') return 'Tap Track, I\'ll watch it 👀';
    if (page === 'trip_live') return 'Tap me for SOS or share 🛟';
    if (late) return 'Late ride? I\'m here 🌙';
    if (page === 'app_home') return hour < 12 ? 'Subah ki bus? ☀️' : 'Kahan chalein? 🚌';
    return null;
  }
  setTimeout(() => {
    const text = peekText();
    if (!text || !sheet.hidden || document.querySelector('.guide-card')) return;
    const key = `yb.peek.${page}.${text}`;
    try { if (sessionStorage.getItem(key)) return; sessionStorage.setItem(key, '1'); } catch (e) { return; }
    peek.textContent = text;
    peek.hidden = false;
    requestAnimationFrame(() => peek.classList.add('show'));
    mood('wave', 2400);
    hop($('.bandhu', fab));
    peekTimer = setTimeout(hidePeek, 5200);
  }, calm ? 600 : 1400);
  peek.addEventListener('click', open);
})();
