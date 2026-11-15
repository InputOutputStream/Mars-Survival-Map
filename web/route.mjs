// route.mjs - same algorithm as site.find_route (Python): 8-neighbour Dijkstra.
// Cost of a step = 3D distance × mean cost of the 2 cells + climbK × climb. Used by index.html AND tested under Node.
const N8 = [[-1,0,1],[1,0,1],[0,-1,1],[0,1,1],[-1,-1,Math.SQRT2],[-1,1,Math.SQRT2],[1,-1,Math.SQRT2],[1,1,Math.SQRT2]];

class Heap {                                   // binary min-heap on (key, value)
  constructor() { this.k = []; this.v = []; }
  get size() { return this.k.length; }
  push(key, val) {
    const k = this.k, v = this.v; let i = k.length; k.push(key); v.push(val);
    while (i > 0) { const p = (i - 1) >> 1; if (k[p] <= key) break; k[i] = k[p]; v[i] = v[p]; i = p; }
    k[i] = key; v[i] = val;
  }
  pop() {
    const k = this.k, v = this.v, topK = k[0], topV = v[0], lastK = k.pop(), lastV = v.pop(), n = k.length;
    if (n > 0) {
      let i = 0;
      for (;;) {
        let c = 2 * i + 1; if (c >= n) break;
        if (c + 1 < n && k[c + 1] < k[c]) c++;
        if (k[c] >= lastK) break;
        k[i] = k[c]; v[i] = v[c]; i = c;
      }
      k[i] = lastK; v[i] = lastV;
    }
    return [topK, topV];
  }
}

export function findRoute({ dem, cost, w, h, px, climbK = 8, speedKmh = 2 }, start, goal) {
  const inb = ([r, c]) => r >= 0 && r < h && c >= 0 && c < w;
  if (!inb(start) || !inb(goal)) throw new Error('hors du site');
  const S = start[0] * w + start[1], G = goal[0] * w + goal[1];
  if (!Number.isFinite(cost[S]) || !Number.isFinite(cost[G])) return null;
  const dist = new Float64Array(w * h).fill(Infinity), prev = new Int32Array(w * h).fill(-1);
  dist[S] = 0;
  const heap = new Heap(); heap.push(0, S);
  while (heap.size) {
    const [d, u] = heap.pop();
    if (d > dist[u]) continue;
    if (u === G) break;
    const r = (u / w) | 0, c = u - r * w;
    for (const [dr, dc, f] of N8) {
      const rr = r + dr, cc = c + dc;
      if (rr < 0 || rr >= h || cc < 0 || cc >= w) continue;
      const q = rr * w + cc, cb = cost[q];
      if (!Number.isFinite(cb)) continue;
      const dz = dem[q] - dem[u];
      const nd = d + Math.hypot(f * px, dz) * 0.5 * (cost[u] + cb) + climbK * Math.max(dz, 0);
      if (nd < dist[q]) { dist[q] = nd; prev[q] = u; heap.push(nd, q); }
    }
  }
  if (!Number.isFinite(dist[G])) return null;
  const path = [];
  for (let u = G; u !== -1; u = prev[u]) path.push([(u / w) | 0, u % w]);
  path.reverse();
  return { path, cost: dist[G], ...routeStats({ dem, cost, w, px, speedKmh }, path) };
}

export function routeStats({ dem, cost, w, px, speedKmh = 2 }, path) {
  let len = 0, asc = 0, desc = 0, maxS = 0, tw = 0, sw = 0, T = 0;
  const prof = [dem[path[0][0] * w + path[0][1]]], pd = [0];
  for (let i = 1; i < path.length; i++) {
    const [r0, c0] = path[i - 1], [r1, c1] = path[i];
    const a = r0 * w + c0, b = r1 * w + c1;
    const flat = Math.hypot(r1 - r0, c1 - c0) * px, dz = dem[b] - dem[a], seg = Math.hypot(flat, dz);
    len += seg; if (dz > 0) asc += dz; else desc -= dz;
    const sl = Math.atan2(Math.abs(dz), Math.max(flat, 1e-9)) * 180 / Math.PI;
    maxS = Math.max(maxS, sl); sw += sl * seg; T += seg * 0.5 * (cost[a] + cost[b]);
    prof.push(dem[b]); pd.push(len);
  }
  const [r0, c0] = path[0], [r1, c1] = path[path.length - 1];
  return { length_m: len, straight_m: Math.hypot((r1 - r0) * px, (c1 - c0) * px), ascent_m: asc, descent_m: desc,
           max_slope_deg: maxS, mean_slope_deg: len > 0 ? sw / len : 0, time_h: T / (speedKmh * 1000),
           profile_m: prof, profile_dist_m: pd };
}

// ---- Minimum-energy route (mirror of src/mars_survival/traverse.py + physics.py; parity tested under Node) ----
const COEF = [280.5, -58.7, -76.8, 51.9, 19.6, 2.5], G_EARTH = 9.80665, GRADE_RANGE = 0.45;
export const minettiCw = i => ((((COEF[0] * i + COEF[1]) * i + COEF[2]) * i + COEF[3]) * i + COEF[4]) * i + COEF[5];
export function walkingCost(i, g, levelScale) { const l = minettiCw(0); return l * levelScale + (minettiCw(i) - l) * (g / G_EARTH); }
export const optimalSpeedKmh = g => 5.5 * Math.sqrt(g / G_EARTH);

export function stepCost(grade, len, mult, W) {
  if (Math.abs(grade) > GRADE_RANGE) return [Infinity, Infinity];
  const c = walkingCost(grade, W.g, W.levelScale), v = Math.min(optimalSpeedKmh(W.g) / 3.6, W.powerW / (c * W.massKg));
  return [W.massKg * c * len * mult, len * mult / (v * (W.timeScale || 1))];   // timeScale: user pace / model level-ground pace (1 = model pace)
}

// Fast step cost: same arithmetic as stepCost, but no array allocation and the walker constants are computed once.
const DR = [-1, 1, 0, 0, -1, -1, 1, 1], DC = [0, 0, -1, 1, -1, 1, -1, 1], DF = [1, 1, 1, 1, Math.SQRT2, Math.SQRT2, Math.SQRT2, Math.SQRT2];
let _E = 0, _T = 0;
function kOf(W) {
  const l0 = minettiCw(0); let cmin = Infinity; for (let i = -GRADE_RANGE; i <= GRADE_RANGE + 1e-9; i += 0.001) cmin = Math.min(cmin, walkingCost(i, W.g, W.levelScale));
  return { l0, a: l0 * W.levelScale, s: W.g / G_EARTH, vo: optimalSpeedKmh(W.g) / 3.6, P: W.powerW, m: W.massKg, cmin, ts: W.timeScale || 1 };
}
function stepFast(grade, len, mult, K) {
  if (grade > GRADE_RANGE || grade < -GRADE_RANGE) { _E = _T = Infinity; return; }
  const c = K.a + (minettiCw(grade) - K.l0) * K.s, v = Math.min(K.vo, K.P / (c * K.m));
  _E = K.m * c * len * mult; _T = len * mult / (v * K.ts);
}

// Point-to-point search: A* with a straight-line lower bound (energy >= m * cmin * distance, time >= distance / v_opt, since terrain
// multipliers are >= 1). The bound is consistent, so the route and its cost are the same as Dijkstra's, found by visiting far fewer cells.
export function findRouteEnergy({ dem, tmult, w, h, px, walker: W, objective = 'energy' }, start, goal) {
  const k = objective === 'energy' ? 0 : 1, S = start[0] * w + start[1], G = goal[0] * w + goal[1], K = kOf(W);
  if (!Number.isFinite(tmult[S]) || !Number.isFinite(tmult[G])) return null;
  const gr = goal[0], gc = goal[1], hk = (k === 0 ? K.m * K.cmin : 1 / (K.vo * K.ts)) * px * 0.999999;
  const H = (r, c) => hk * Math.hypot(r - gr, c - gc);
  const dist = new Float64Array(w * h).fill(Infinity), prev = new Int32Array(w * h).fill(-1);
  dist[S] = 0; const heap = new Heap(); heap.push(H(start[0], start[1]), S);
  while (heap.size) {
    const [f, u] = heap.pop(), r = (u / w) | 0, c = u - r * w, d = dist[u];
    if (f > d + H(r, c) + 1e-9) continue; if (u === G) break;
    for (let n = 0; n < 8; n++) {
      const rr = r + DR[n], cc = c + DC[n]; if (rr < 0 || rr >= h || cc < 0 || cc >= w) continue;
      const q = rr * w + cc, tq = tmult[q]; if (!Number.isFinite(tq)) continue;
      const flat = DF[n] * px, dz = dem[q] - dem[u];
      stepFast(dz / flat, Math.sqrt(flat * flat + dz * dz), 0.5 * (tmult[u] + tq), K);
      const cost = k === 0 ? _E : _T;
      if (d + cost < dist[q]) { dist[q] = d + cost; prev[q] = u; heap.push(d + cost + H(rr, cc), q); }
    }
  }
  if (!Number.isFinite(dist[G])) return null;
  const path = []; for (let u = G; u !== -1; u = prev[u]) path.push([(u / w) | 0, u % w]); path.reverse();
  let E = 0, T = 0, L = 0;
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1][0] * w + path[i - 1][1], b = path[i][0] * w + path[i][1];
    const flat = Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]) * px, dz = dem[b] - dem[a];
    const [e, t] = stepCost(dz / flat, Math.hypot(flat, dz), 0.5 * (tmult[a] + tmult[b]), W);
    E += e; T += t; L += Math.hypot(flat, dz);
  }
  return { path, energy_j: E, time_h: T / 3600, length_m: L, mean_power_w: T ? E / T : 0 };
}

// One-to-all least-energy field (Dijkstra). `reverse = false`: cost of walking FROM src to every cell.
// `reverse = true`: cost of walking from every cell BACK TO src (uphill and downhill swap, so it is not the same number).
// E = energy in J, T = walking time in s along that least-energy path.
export function costField({ dem, tmult, w, h, px, walker: W }, S, reverse = false) {
  const K = kOf(W), n = w * h, E = new Float64Array(n).fill(Infinity), T = new Float64Array(n).fill(Infinity);
  if (!Number.isFinite(tmult[S])) return { E, T };
  E[S] = 0; T[S] = 0; const heap = new Heap(); heap.push(0, S);
  while (heap.size) {
    const [d, u] = heap.pop(); if (d > E[u]) continue;
    const r = (u / w) | 0, c = u - r * w;
    for (let n = 0; n < 8; n++) {
      const rr = r + DR[n], cc = c + DC[n]; if (rr < 0 || rr >= h || cc < 0 || cc >= w) continue;
      const q = rr * w + cc, tq = tmult[q]; if (!Number.isFinite(tq)) continue;
      const flat = DF[n] * px, dz = reverse ? dem[u] - dem[q] : dem[q] - dem[u];
      stepFast(dz / flat, Math.sqrt(flat * flat + dz * dz), 0.5 * (tmult[u] + tq), K);
      if (!Number.isFinite(_E)) continue;
      if (d + _E < E[q]) { E[q] = d + _E; T[q] = T[u] + _T; heap.push(d + _E, q); }
    }
  }
  return { E, T };
}
