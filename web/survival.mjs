// survival.mjs - the safety calculations of the site map. Pure functions (no DOM), tested under Node.
export const MARS_R = 3389500;                 // m, mean radius (NASA Mars Fact Sheet)
export const SOL_H = 1.0274912517;            // Earth hours in one Mars solar hour

// ---- Return to shelter: where can a person go and still get back within the consumables? ----
// fwd = costField(shelter -> cell), back = costField(cell -> shelter, reverse). Both limits must hold; the stricter one "binds".
export function reachField(fwd, back, { tMaxS, eMaxJ }) {
  const n = fwd.E.length, used = new Float32Array(n).fill(Infinity), bind = new Uint8Array(n);   // bind: 1 = time, 2 = energy
  let maxOneWay = 0, count = 0;
  for (let i = 0; i < n; i++) {
    const T = fwd.T[i] + back.T[i], E = fwd.E[i] + back.E[i]; if (!Number.isFinite(T) || !Number.isFinite(E)) continue;
    const ft = T / tMaxS, fe = E / eMaxJ; used[i] = Math.max(ft, fe); bind[i] = ft >= fe ? 1 : 2;
    if (used[i] <= 1) count++;
  }
  return { used, bind, count };
}

// ---- Line of sight from the shelter antenna ----
// Straight line between antenna (hAnt above ground at src) and receiver (hRx above ground at the cell), with Mars' curvature.
export function viewshed({ dem, w, h, px }, src, hAnt, hRx, maxM = Infinity) {
  const [r0, c0] = src, z0 = dem[r0 * w + c0] + hAnt, out = new Uint8Array(w * h), k2 = 1 / (2 * MARS_R);
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
    const dr = r - r0, dc = c - c0, steps = Math.max(Math.abs(dr), Math.abs(dc)), dist = Math.hypot(dr, dc) * px;
    if (steps === 0) { out[r * w + c] = 1; continue; } if (dist > maxM) continue;
    const tgt = (dem[r * w + c] + hRx - dist * dist * k2 - z0) / dist; let ok = true;
    for (let k = 1; k < steps; k++) {
      const rr = Math.round(r0 + dr * k / steps), cc = Math.round(c0 + dc * k / steps), d = Math.hypot(rr - r0, cc - c0) * px;
      if ((dem[rr * w + cc] - d * d * k2 - z0) / d > tgt) { ok = false; break; }
    }
    out[r * w + c] = ok ? 1 : 0;
  }
  return out;
}

// ---- Sun and shadows ----
export function sunPosition(latDeg, declDeg, hour) {          // hour = local true solar time (0-24); az from north, clockwise
  const R = Math.PI / 180, phi = latDeg * R, dl = declDeg * R, H = (hour - 12) * 15 * R;
  const el = Math.asin(Math.sin(phi) * Math.sin(dl) + Math.cos(phi) * Math.cos(dl) * Math.cos(H));
  const az = Math.atan2(-Math.cos(dl) * Math.sin(H), Math.sin(dl) * Math.cos(phi) - Math.cos(dl) * Math.sin(phi) * Math.cos(H));
  return { el: el / R, az: (az / R + 360) % 360 };
}
export function shadowMask({ dem, w, h, px }, azDeg, elDeg) {   // 1 = in shadow. Night (sun below the horizon) = all 1.
  const out = new Uint8Array(w * h); if (elDeg <= 0) return out.fill(1);
  let zmax = -Infinity; for (let i = 0; i < dem.length; i++) if (dem[i] > zmax) zmax = dem[i];
  const a = azDeg * Math.PI / 180, dc = Math.sin(a), dr = -Math.cos(a), tn = Math.tan(elDeg * Math.PI / 180);
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
    const z0 = dem[r * w + c]; let sh = 0;
    for (let k = 1; ; k++) {
      const rr = Math.round(r + dr * k), cc = Math.round(c + dc * k); if (rr < 0 || rr >= h || cc < 0 || cc >= w) break;
      const rise = k * px * tn; if (z0 + rise > zmax) break;
      if (dem[rr * w + cc] > z0 + rise + 0.05) { sh = 1; break; }
    }
    out[r * w + c] = sh;
  }
  return out;
}

// ---- Time budget of a walk: sunset and cold ----
// plan = one entry of site.json eva.plans (hourly sun elevation and air temperature, limits). Hours are local solar hours.
const at = (plan, key, hr) => { const t = ((hr % 24) + 24) % 24, i = Math.floor(t), j = (i + 1) % 24, f = t - i, H = plan.hourly;
  const a = H[i][key], b = H[j][key]; return a + (b - a) * f; };
export function timeBudget(plan, startH, durH) {
  const lim = plan.limits, step = 0.05, n = Math.max(1, Math.ceil(durH / step));
  let dark = 0, low = 0, cold = 0, minT = Infinity, minAt = startH, sunset = null, prev = at(plan, 'sun_elev_deg', startH);
  for (let k = 0; k <= n; k++) {
    const t = startH + Math.min(durH, k * step), el = at(plan, 'sun_elev_deg', t), tc = at(plan, 'temp_c', t), dt = k === 0 ? 0 : step;
    if (el < 0) dark += dt; if (el < lim.min_sun_elev_deg) low += dt; if (tc < lim.t_min_c) cold += dt;
    if (tc < minT) { minT = tc; minAt = t; } if (sunset === null && prev >= 0 && el < 0) sunset = t; prev = el;
  }
  const bad = (s) => { for (let t = s; t <= s + durH + 1e-9; t += step) if (at(plan, 'sun_elev_deg', t) < lim.min_sun_elev_deg || at(plan, 'temp_c', t) < lim.t_min_c) return true; return false; };
  const safe = []; let open = null;
  for (let s = 0; s < 24 + 1e-9; s += 0.1) { const ok = !bad(s); if (ok && open === null) open = s; if (!ok && open !== null) { safe.push([open, s - 0.1]); open = null; } }
  if (open !== null) safe.push([open, 24]);
  const status = (dark > 0 || cold > 0) ? 'danger' : low > 0 ? 'caution' : 'ok';
  return { startH, endH: startH + durH, status, darkH: dark, lowH: low, coldH: cold, minTempC: minT, minTempAtH: minAt, sunsetH: sunset, safeStarts: safe };
}
