/* Bandhu's first-trip guide.
 * - Short tips that point at real buttons, one or two per screen, across the first trip.
 * - Never blocks the app: you can tap anything while a tip is showing.
 * - "Skip tour" on every tip; Esc also skips. Shown once per person; replay from Help.
 */
(function () {
  'use strict';
  const body = document.body;
  if (!body || body.dataset.guide !== '1') return;                 // only after onboarding
  const KEY = 'yb.guide.' + (body.dataset.uid || 'anon');
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch { return null; } };
  const save = (s) => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode */ } };
  // Replay from Help (defined first, so it works even after the tour was skipped or finished)
  window.RM = window.RM || {};
  window.RM.replayGuide = () => { save({ status: 'active', seen: {} }); location.href = '/app'; };

  const STEPS = {
    app_home: [
      { t: '.searchbox', text: "Hi, I'm Bandhu! Tap here and type where you're going, like Sector 17." },
      { t: '.hw', text: 'Save Home and Work here. Your usual trips become one tap.' },
    ],
    routes: [
      { t: '.opt.best', text: 'This is the best bus for you. Time is on the right, the fare is in green.' },
      { t: '.modes', text: 'Want to compare? Switch to Auto or Cab, or plan a round trip just below.' },
    ],
    journey: [
      { t: '.stl', text: "Here are all your stops with times. I'll tell you which one is yours." },
      { t: '.sticky-cta .btn-primary', text: "Tap Track This Bus when you leave, and I'll follow it with you." },
    ],
    trip_live: [
      { t: '.mapui-map', text: 'Watch your bus come to your stop, right here on the map.' },
      { t: '[data-live-toggle].square', text: "Tap the bell and I'll remind you before your stop." },
      { t: '.safety-actions', text: "Help is always one tap away. That's the tour! Replay me anytime from Help.", last: true },
    ],
  };

  let state = load();
  if (!state) { state = { status: 'active', seen: {} }; save(state); }
  if (state.status !== 'active') return;
  const page = body.dataset.endpoint;
  const steps = (STEPS[page] || []).filter((s) => document.querySelector(s.t));
  if (!steps.length || state.seen[page]) return;

  const tpl = document.getElementById('bandhu-tpl');
  const reduce = document.documentElement.classList.contains('reduce-motion') || matchMedia('(prefers-reduced-motion: reduce)').matches;
  let i = 0, spot, card;

  function finish(status) {
    state.seen[page] = true;
    if (status) state.status = status;
    save(state);
    spot?.remove(); card?.remove();
    document.removeEventListener('keydown', onKey);
    window.removeEventListener('resize', place);
  }
  function onKey(e) { if (e.key === 'Escape') finish('skipped'); }

  function place() {
    const step = steps[i], el = document.querySelector(step.t);
    if (!el) return;
    const r = el.getBoundingClientRect(), pad = 8;
    Object.assign(spot.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px` });
    const cw = Math.min(340, innerWidth - 24), ch = card.offsetHeight;
    const below = r.top + r.height / 2 < innerHeight / 2;
    let top = below ? r.bottom + pad + 12 : r.top - pad - 12 - ch;
    top = Math.max(12, Math.min(innerHeight - ch - 84, top));
    const left = Math.max(12, Math.min(innerWidth - cw - 12, r.left + r.width / 2 - cw / 2));
    Object.assign(card.style, { left: `${left}px`, top: `${top}px`, width: `${cw}px` });
    card.classList.toggle('from-below', !below);
  }

  function show() {
    const step = steps[i], el = document.querySelector(step.t);
    el.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
    const isLast = i === steps.length - 1;
    card.querySelector('[data-g-text]').textContent = step.text;
    card.querySelector('[data-g-count]').textContent = steps.length > 1 ? `${i + 1} / ${steps.length}` : '';
    card.querySelector('[data-g-next]').textContent = step.last ? 'Done' : isLast ? 'Got it' : 'Next';
    card.classList.remove('pop'); void card.offsetWidth; card.classList.add('pop');
    setTimeout(place, reduce ? 0 : 320);
    card.querySelector('[data-g-next]').focus({ preventScroll: true });
  }

  function start() {
    spot = document.createElement('div');
    spot.className = 'guide-spot';
    card = document.createElement('div');
    card.className = 'guide-card';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-live', 'polite');
    card.setAttribute('aria-label', 'Bandhu tip');
    card.innerHTML = `<div class="guide-mascot">${tpl ? tpl.innerHTML : ''}</div>
      <div class="guide-body"><p data-g-text></p>
        <div class="guide-actions"><button type="button" class="link guide-skip" data-g-skip>Skip tour</button>
          <span class="guide-count" data-g-count></span>
          <button type="button" class="btn btn-primary btn-sm" data-g-next>Next</button></div></div>`;
    document.body.append(spot, card);
    card.querySelector('[data-g-skip]').addEventListener('click', () => finish('skipped'));
    card.querySelector('[data-g-next]').addEventListener('click', () => {
      if (steps[i].last) return finish('done');
      if (i < steps.length - 1) { i++; show(); } else finish();
    });
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, { passive: true });
    show();
  }
  // let the page (and splash) settle first
  setTimeout(start, sessionStorage.getItem('yb.splash') ? 700 : 1900);

})();
