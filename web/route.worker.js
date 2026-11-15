// Runs the heavy searches (route, one-to-all cost fields) off the main thread, so the map stays responsive on phones.
import { findRouteEnergy, costField } from './route.mjs';
import { viewshed, shadowMask } from './survival.mjs';
let G = null;
onmessage = e => {
  const m = e.data;
  if (m.op === 'init') { G = { dem: m.dem, tmult: m.tmult, w: m.w, h: m.h, px: m.px }; return; }
  try {
    if (m.op === 'route') postMessage({ id: m.id, a: findRouteEnergy({ ...G, walker: m.walker, objective: m.objective }, m.start, m.goal) });
    else if (m.op === 'los') { const out = viewshed(G, m.src, m.hAnt, m.hRx); postMessage({ id: m.id, out }, [out.buffer]); }
    else if (m.op === 'shadow') { const out = shadowMask(G, m.az, m.el); postMessage({ id: m.id, out }, [out.buffer]); }
    else if (m.op === 'field') {
      const f = costField({ ...G, walker: m.walker }, m.S, false), b = costField({ ...G, walker: m.walker }, m.S, true);
      postMessage({ id: m.id, f, b }, [f.E.buffer, f.T.buffer, b.E.buffer, b.T.buffer]);
    }
  } catch (err) { postMessage({ id: m.id, error: String(err) }); }
};
