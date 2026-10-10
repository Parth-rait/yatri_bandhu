/* Yatri Bandhu page behaviour: theme, search, location, small form helpers, usability-test logger. */
(function () {
  'use strict';
  const RM = (window.RM = window.RM || {});
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
    del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
  };

  // ---------------------------------------------------------------- toast
  let toastTimer;
  RM.toast = function (msg) {
    const t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 3500);
  };

  // ---------------------------------------------------------------- theme (light / dark / auto)
  const sysDark = () => matchMedia('(prefers-color-scheme: dark)').matches;
  function setTheme(choice) {
    const theme = choice === 'system' ? (sysDark() ? 'dark' : 'light') : choice;
    const changed = document.documentElement.dataset.theme !== theme;
    document.documentElement.dataset.theme = theme;
    if (changed) window.dispatchEvent(new Event('rm:theme'));
    document.cookie = choice === 'system' ? 'theme=; path=/; max-age=0; SameSite=Lax'
      : `theme=${choice}; path=/; max-age=31536000; SameSite=Lax`;
    syncThemeButtons(choice);
  }
  function syncThemeButtons(choice) {
    const saved = choice || (document.cookie.match(/(?:^|; )theme=(light|dark)/) || [])[1] || 'system';
    $$('[data-set-theme]').forEach((b) => b.setAttribute('aria-current', String(b.dataset.setTheme === saved)));
    $$('[data-set-theme]').forEach((b) => { if (b.dataset.setTheme !== saved) b.removeAttribute('aria-current'); });
    $$('[data-theme-toggle]').forEach((b) => b.setAttribute('aria-label',
      document.documentElement.dataset.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'));
  }

  // ---------------------------------------------------------------- colours: badges + itinerary rails match the map
  function paint(root = document) {
    $$('.line-badge[data-route]', root).forEach((b) => b.style.setProperty('--rc', RM.routeColor(b.dataset.route)));
    $$('[data-route-color]', root).forEach((el) => el.style.setProperty('--lc', RM.routeColor(el.dataset.routeColor)));
    $$('[data-line-color]', root).forEach((el) => el.style.setProperty('--line-color', RM.routeColor(el.dataset.lineColor)));
  }

  // ---------------------------------------------------------------- search page (live results)
  const ICONS = {
    stop: '<path d="M12 11v10M9 21h6"/><rect x="5" y="3" width="14" height="8" rx="2"/><path d="M9 7h6"/>',
    pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    cap: '<path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>',
    bag: '<path d="M5 8h14l-1 13H6L5 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    bus: '<path d="M6 17h12M6 17a2 2 0 0 1-2-2V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v9a2 2 0 0 1-2 2M6 17v3M18 17v3M4 11h16"/>',
    train: '<rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 11h14M8 21l2-4M16 21l-2-4"/>',
    hospital: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M12 8v8M8 12h8"/>',
    tree: '<path d="M12 22v-6M12 2 5 12h4l-3 4h12l-3-4h4L12 2z"/>',
    food: '<path d="M7 2v9M5 2v5a2 2 0 0 0 4 0V2M7 11v11M17 2c-2 2-3 5-3 8h3v12"/>',
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    plane: '<path d="M21 15.5 13 11V5.5a1.5 1.5 0 0 0-3 0V11l-8 4.5V17l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-4.5l8 2.5z"/>',
    route: '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h7"/>',
    building: '<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M10 21v-3h4v3"/>',
  };
  const svg = (n) => `<svg class="ic" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n] || ICONS.pin}</svg>`;

  function initSearch(form) {
    const input = $('[data-search-input]', form);
    const clear = $('[data-search-clear]', form);
    const out = $('[data-search-results]');
    const ret = form.dataset.ret, kind = form.dataset.kind;
    const initial = out.innerHTML;
    const fill = (id) => ret.replace('__PT__', encodeURIComponent(id).replace(/%3A/g, ':').replace(/%2C/g, ','));
    let timer, n = 0;
    input.addEventListener('input', () => {
      clear.hidden = !input.value;
      clearTimeout(timer);
      const q = input.value.trim();
      const cats = $('[data-cats]'); if (cats) cats.hidden = !!q;
      if (!q) { out.innerHTML = initial; bindGeo(); return; }
      timer = setTimeout(async () => {
        const my = ++n;
        const row = (r) => `<a class="row" href="${esc(fill(r.id))}"><span class="row-ic">${svg(r.icon)}</span><span class="row-txt"><b>${esc(r.name)}</b><small>${esc(r.sub)}</small></span></a>`;
        const render = (res, places) => {
          if (my !== n) return;
          let html = res.length ? `<div class="list">${res.map(row).join('')}</div>` : '';
          if (places && places.length) html += `<h2 style="margin:18px 0 6px">Places</h2><div class="list">${places.map(row).join('')}</div>`;
          if (!html) html = places ? '<p class="muted" style="padding:12px 4px">No results</p>' : '<p class="muted" style="padding:12px 4px">Searching…</p>';
          out.innerHTML = `<section class="section" style="margin-top:8px">${html}</section>`;
        };
        try {
          const local = fetch(`/api/search?kind=${kind}&q=${encodeURIComponent(q)}`).then((r) => r.json());
          const places = kind === 'stops' || q.length < 2 ? Promise.resolve([])
            : fetch(`/api/places?q=${encodeURIComponent(q)}&lat=${form.dataset.lat}&lng=${form.dataset.lng}`).then((r) => r.json()).catch(() => []);
          const res = await local;
          render(res, null);
          render(res, await places);
        } catch { /* offline: the form still works by pressing Enter */ }
      }, 120);
    });
    clear.addEventListener('click', () => { input.value = ''; input.dispatchEvent(new Event('input')); input.focus(); });
    function bindGeo() {
      $('[data-geo-pick]')?.addEventListener('click', async () => {
        const status = $('[data-geo-status]');
        status.textContent = 'Finding you…';
        try {
          const pos = await RM.geolocate();
          location.href = fill(`geo:${pos.coords.latitude.toFixed(5)},${pos.coords.longitude.toFixed(5)}`);
        } catch (err) { status.textContent = err.message; }
      });
    }
    bindGeo();
  }

  // ---------------------------------------------------------------- lines list filter
  function initLines(box) {
    const q = $('[data-lines-q]', box);
    const rows = $$('[data-lines-list] > a');
    const empty = $('[data-lines-empty]');
    const apply = () => {
      const t = q.value.trim().toLowerCase();
      let shown = 0;
      rows.forEach((r) => { const ok = !t || r.dataset.search.includes(t); r.hidden = !ok; if (ok) shown++; });
      empty.hidden = shown > 0;
    };
    q.addEventListener('input', apply);
    apply();
  }

  // ---------------------------------------------------------------- forms
  function initForms() {
    // drop empty fields from GET forms so links stay short
    $$('form[method=get]').forEach((f) => f.addEventListener('submit', () => {
      const off = $$('input,select', f).filter((i) => i.name && !i.value && !i.disabled);
      off.forEach((i) => { i.disabled = true; });
      setTimeout(() => off.forEach((i) => { i.disabled = false; }), 0);
    }));
    $$('[data-autosubmit]').forEach((i) => i.addEventListener('change', () => i.form.requestSubmit()));
    $$('[data-kind]').forEach((i) => i.addEventListener('change', () => {
      $$('input[name=value]', i.form).forEach((v) => { v.checked = false; });
      i.form.requestSubmit();
    }));

    const pf = $('[data-plan-form]');
    if (pf) {
      const time = $('[data-when-time]', pf), wrap = $('[data-when-time-wrap]', pf);
      $('[data-when-now]', pf).addEventListener('change', () => { time.disabled = true; wrap.hidden = true; });
      $('[data-when-later]', pf).addEventListener('change', () => {
        time.disabled = false; wrap.hidden = false;
        if (!time.value) time.value = new Date(Date.now() + 30 * 60000).toTimeString().slice(0, 5);
        time.focus();
      });
      pf.addEventListener('submit', async (e) => {
        $$('input[name=when]', pf).forEach((w) => { w.disabled = true; });
        const remember = $('[data-remember]', pf);
        if (remember.checked) {
          e.preventDefault();
          await fetch('/remember-priority', { method: 'POST', body: new URLSearchParams({ mode: $('input[name=mode]:checked', pf).value }) }).catch(() => {});
          remember.checked = false;
          pf.submit();
        }
      });
    }

    const fb = $('[data-feedback]');
    if (fb) {
      const issues = $('[data-issues]', fb);
      issues.hidden = true;
      $$('[data-acc]', fb).forEach((r) => r.addEventListener('change', () => { issues.hidden = r.value !== 'no'; }));
    }

    $$('[data-find-nearby]').forEach((b) => b.addEventListener('click', async () => {
      const err = $('[data-nearby-error]');
      const old = b.innerHTML;
      b.disabled = true; b.textContent = 'Finding you…';
      try {
        const pos = await RM.geolocate();
        location.href = `/nearby?lat=${pos.coords.latitude.toFixed(5)}&lng=${pos.coords.longitude.toFixed(5)}`;
      } catch (e) {
        if (err) { err.textContent = e.message; err.hidden = false; } else RM.toast(e.message);
        b.disabled = false; b.innerHTML = old;
      }
    }));
  }

  // ---------------------------------------------------------------- usability-test logger
  const SKEY = 'rm.study';
  function studyBar() {
    const bar = $('#study-bar');
    let s = store.get(SKEY, null);
    if (!bar || !s) return;
    s.path.push(location.pathname + location.search);
    store.set(SKEY, s);
    bar.hidden = false;
    bar.innerHTML = `<span class="sb-task"><b>${esc(s.task)}</b> ${esc(s.text)}</span>
      <span class="sb-time">0:00</span>
      <button type="button" data-sb="error" title="Observer: participant made an error">+ error <b>${s.errors}</b></button>
      <button type="button" data-sb="done">Done</button><button type="button" data-sb="quit">Gave up</button>`;
    const timeEl = $('.sb-time', bar);
    const tick = () => { const sec = Math.round((Date.now() - s.start) / 1000); timeEl.textContent = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`; };
    tick();
    const iv = setInterval(tick, 1000);
    document.addEventListener('click', (e) => {
      if (e.target.closest('#study-bar')) return;
      s = store.get(SKEY, s); s.clicks++; store.set(SKEY, s);
    }, true);
    bar.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-sb],[data-conf]');
      if (!b) return;
      s = store.get(SKEY, s);
      if (b.dataset.sb === 'error') { s.errors++; store.set(SKEY, s); $('b', b).textContent = s.errors; return; }
      if (b.dataset.sb) {
        clearInterval(iv);
        s.outcome = b.dataset.sb === 'done' ? 'completed' : 'gave up';
        s.seconds = (Date.now() - s.start) / 1000;
        store.set(SKEY, s);
        bar.innerHTML = `<span class="sb-task"><b>How sure are you that you got it right?</b> 1 = not at all, 5 = completely</span>
          ${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-conf="${n}">${n}</button>`).join('')}`;
        return;
      }
      await fetch('/api/study', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...s, confidence: +b.dataset.conf }) }).catch(() => {});
      store.del(SKEY);
      location.href = '/study';
    });
  }
  function initStudyStart() {
    const f = $('[data-study-start]');
    if (!f) return;
    f.addEventListener('submit', (e) => {
      e.preventDefault();
      const task = $('input[name=task]:checked', f);
      store.set(SKEY, { participant: $('#participant', f).value.trim(), task: task.value, text: task.dataset.text,
        start: Date.now(), clicks: 0, errors: 0, path: [] });
      location.href = '/app';
    });
  }

  // ---------------------------------------------------------------- boot
  // splash screen: once per session, long enough to read the name
  function splash() {
    const el = $('[data-splash]');
    if (!el) return;
    try { if (sessionStorage.getItem('yb.splash')) { el.remove(); return; } sessionStorage.setItem('yb.splash', '1'); } catch { /* ignore */ }
    setTimeout(() => { el.classList.add('done'); setTimeout(() => el.remove(), 500); }, 1300);
  }

  // Home: start trips from where you are (if you allowed location)
  function autoLocate() {
    const home = $('[data-auto-locate]');
    if (!home || new URLSearchParams(location.search).get('from')) return;
    try { if (sessionStorage.getItem('yb.located')) return; sessionStorage.setItem('yb.located', '1'); } catch { /* ignore */ }
    RM.geolocate().then((pos) => {
      const p = [pos.coords.latitude, pos.coords.longitude];
      if (RM.TRICITY && !RM.TRICITY.contains(p)) return;
      location.replace(`/app?from=geo:${p[0].toFixed(5)},${p[1].toFixed(5)}`);
    }).catch(() => {});
  }

  // Onboarding: ask the browser for location permission
  function initLocationAsk() {
    const b = $('[data-ask-location]');
    if (!b) return;
    b.addEventListener('click', async () => {
      const f = b.form;
      b.disabled = true;
      b.textContent = 'Waiting for permission…';
      // If the browser prompt is ignored or closed, don't hang: carry on without location after 8 s.
      const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('No answer, continuing without location')), 8000));
      try { await Promise.race([RM.geolocate(), timeout]); f.use_location.value = '1'; }
      catch (err) { f.use_location.value = '0'; RM.toast(err.message); await new Promise((r) => setTimeout(r, 1200)); }
      f.submit();
    });
  }

  // Booking: passenger steppers and live total
  function initBooking() {
    const f = $('[data-book]');
    if (!f) return;
    const total = $('[data-total]', f);
    const update = () => {
      let sum = 0;
      $$('.stepper', f).forEach((st) => { sum += (+$('input', st).value || 0) * (+st.dataset.price || 0); });
      total.textContent = `₹${sum}`;
    };
    $$('.stepper', f).forEach((st) => st.addEventListener('click', (e) => {
      const b = e.target.closest('[data-step]');
      if (!b) return;
      const inp = $('input', st);
      inp.value = Math.max(0, Math.min(9, (+inp.value || 0) + +b.dataset.step));
      update();
    }));
    update();
  }

  // Share trip: copy link / native share sheet
  function initShare() {
    const link = $('[data-share-link]');
    if (!link) return;
    $('[data-copy]')?.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(link.value); RM.toast('Link copied'); }
      catch { link.select(); document.execCommand('copy'); RM.toast('Link copied'); }
    });
    const ns = $('[data-native-share]');
    if (ns) {
      if (!navigator.share) ns.hidden = true;
      ns.addEventListener('click', () => navigator.share({ title: ns.dataset.title, url: link.value }).catch(() => {}));
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initBooking();
    initShare();
    splash();
    autoLocate();
    initLocationAsk();
    paint();
    syncThemeButtons();
    $$('[data-theme-toggle]').forEach((b) => b.addEventListener('click', () =>
      setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark')));
    $$('[data-set-theme]').forEach((b) => b.addEventListener('click', () => setTheme(b.dataset.setTheme)));
    const sf = $('[data-search]');
    if (sf) initSearch(sf);
    const lines = $('[data-lines]');
    if (lines) initLines(lines);
    initForms();
    initStudyStart();
    studyBar();
  });
})();
