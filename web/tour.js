// tour.js - a guided tour shared by both viewers.
// startTour(steps, TT): steps = [{ sel, title, text, before? }]. `sel` is a CSS selector of what to highlight (no element = centred card).
// `before()` may open a panel or switch a mode so the target is visible. TT = makeT('tour') for the button labels.
(function () {
  const css = document.createElement('style');
  css.textContent = `
  #tour-shield { position: fixed; inset: 0; z-index: 9000; }
  #tour-ring { position: fixed; z-index: 9001; border-radius: 12px; pointer-events: none; box-shadow: 0 0 0 9999px rgba(27,37,64,.58), 0 0 0 3px #f0bf2b inset; transition: all .22s ease; }
  #tour-card { position: fixed; z-index: 9002; width: min(340px, calc(100vw - 24px)); background: #fff; color: #1b2540; border-radius: 16px; padding: 16px 18px 14px;
    box-shadow: 0 14px 40px rgba(20,28,50,.35); font: 400 13.5px/1.5 var(--sans, system-ui); }
  #tour-card h3 { margin: 0 0 6px; font: 700 16px var(--display, var(--sans, system-ui)); }
  #tour-card p { margin: 0 0 14px; color: #4b5670; }
  #tour-card .tn { display: flex; align-items: center; gap: 8px; }
  #tour-card .tn .c { flex: 1; font-size: 12px; color: #7b869c; }
  #tour-card button { font: 600 13px var(--sans, system-ui); border-radius: 18px; padding: 7px 15px; cursor: pointer; border: 1px solid #dde2ea; background: #fff; color: #1b2540; }
  #tour-card button.go { background: #4a9a2f; border-color: #4a9a2f; color: #fff; }
  #tour-card button.sk { border: 0; background: none; color: #7b869c; padding: 7px 4px; }
  #tour-card button:disabled { opacity: .4; cursor: default; }
  #tour-card .dots { display: flex; gap: 4px; margin: 0 0 10px; } #tour-card .dots i { height: 4px; flex: 1; border-radius: 2px; background: #dde2ea; } #tour-card .dots i.on { background: #2f9be0; }
  .tourbtn { width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--line, #dde2ea); background: #fff; color: #1b2540; font: 700 16px var(--sans, system-ui); cursor: pointer; box-shadow: 0 1px 4px rgba(20,28,50,.2); }
  `;
  document.head.appendChild(css);

  window.startTour = function (steps, TT) {
    if (document.getElementById('tour-shield')) return;
    const shield = document.createElement('div'); shield.id = 'tour-shield';
    const ring = document.createElement('div'); ring.id = 'tour-ring';
    const card = document.createElement('div'); card.id = 'tour-card'; card.setAttribute('role', 'dialog'); card.setAttribute('aria-live', 'polite');
    document.body.append(shield, ring, card);
    let i = 0;
    const place = () => {
      const s = steps[i];
      const el = s.sel ? document.querySelector(s.sel) : null;
      const r = el ? el.getBoundingClientRect() : null;
      const ok = r && r.width > 4 && r.height > 4;
      if (ok) {
        const p = 6; ring.style.display = 'block';
        ring.style.left = (r.left - p) + 'px'; ring.style.top = (r.top - p) + 'px';
        ring.style.width = (r.width + 2 * p) + 'px'; ring.style.height = (r.height + 2 * p) + 'px';
      } else { ring.style.display = 'block'; ring.style.left = ring.style.top = '50%'; ring.style.width = ring.style.height = '0px'; }
      const cw = card.offsetWidth, ch = card.offsetHeight, W = innerWidth, H = innerHeight, g = 14;
      let x, y;
      if (!ok) { x = (W - cw) / 2; y = (H - ch) / 2; }
      else if (r.right + g + cw < W) { x = r.right + g; y = r.top; }          // to the right
      else if (r.left - g - cw > 0) { x = r.left - g - cw; y = r.top; }        // to the left
      else if (r.bottom + g + ch < H) { x = Math.max(12, Math.min(r.left, W - cw - 12)); y = r.bottom + g; }
      else { x = Math.max(12, Math.min(r.left, W - cw - 12)); y = Math.max(12, r.top - g - ch); }
      card.style.left = Math.max(12, Math.min(x, W - cw - 12)) + 'px';
      card.style.top = Math.max(12, Math.min(y, H - ch - 12)) + 'px';
    };
    const show = () => {
      const s = steps[i];
      if (s.before) s.before();
      card.innerHTML = `<div class="dots">${steps.map((_, k) => `<i class="${k <= i ? 'on' : ''}"></i>`).join('')}</div>
        <h3></h3><p></p>
        <div class="tn"><button class="sk" data-a="skip"></button><span class="c"></span><button data-a="back"></button><button class="go" data-a="next"></button></div>`;
      card.querySelector('h3').textContent = s.title; card.querySelector('p').textContent = s.text;
      card.querySelector('.sk').textContent = TT('skip'); card.querySelector('.c').textContent = TT('stepof', i + 1, steps.length);
      const b = card.querySelector('[data-a=back]'); b.textContent = TT('back'); b.disabled = i === 0;
      card.querySelector('[data-a=next]').textContent = i === steps.length - 1 ? TT('done') : TT('next');
      const el = s.sel ? document.querySelector(s.sel) : null;
      if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      setTimeout(place, 300);            // after panels have slid open and scrolled
      place();
    };
    const close = () => { removeEventListener('keydown', key); removeEventListener('resize', place); shield.remove(); ring.remove(); card.remove(); try { localStorage.setItem('tourSeen', '1'); } catch (e) {} };
    const go = d => { if (i + d >= steps.length) return close(); i = Math.max(0, i + d); show(); };
    const key = e => { if (e.key === 'Escape') close(); else if (e.key === 'ArrowRight' || e.key === 'Enter') go(1); else if (e.key === 'ArrowLeft') go(-1); };
    card.addEventListener('click', e => { const a = e.target.dataset && e.target.dataset.a; if (a === 'next') go(1); else if (a === 'back') go(-1); else if (a === 'skip') close(); });
    addEventListener('keydown', key); addEventListener('resize', place);
    show();
    const first = card.querySelector('[data-a=next]'); if (first) first.focus();
  };
})();
