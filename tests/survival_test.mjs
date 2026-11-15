// node tests/survival_test.mjs  - checks the safety calculations on shapes whose answer is known
import { costField, } from '../web/route.mjs';
import { viewshed, shadowMask, sunPosition, timeBudget, reachField, MARS_R } from '../web/survival.mjs';
let bad = 0; const ok = (c, m) => { if (!c) { bad++; console.log('FAIL', m); } else console.log('ok  ', m); };
const w = 41, h = 41, px = 2, flat = new Float32Array(w * h), tm = new Float32Array(w * h).fill(1);
const walker = { massKg: 170, powerW: 326, g: 3.71, levelScale: 0.75 };
// 1. flat field: cost grows with distance, symmetric, and a pillar blocks the view
const S = 20 * w + 20, f = costField({ dem: flat, tmult: tm, w, h, px, walker }, S), b = costField({ dem: flat, tmult: tm, w, h, px, walker }, S, true);
ok(f.E[S] === 0 && f.E[20 * w + 30] > f.E[20 * w + 25], 'energy grows with distance on flat ground');
ok(Math.abs(f.E[20 * w + 30] - b.E[20 * w + 30]) < 1e-6, 'flat ground: out and back cost the same');
// 2. a ramp: going up costs more than coming down, and the reverse field knows it
const ramp = new Float32Array(w * h); for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) ramp[r * w + c] = c * px * 0.2;   // 11.3 deg slope to the east
const fr = costField({ dem: ramp, tmult: tm, w, h, px, walker }, S), br = costField({ dem: ramp, tmult: tm, w, h, px, walker }, S, true), east = 20 * w + 30;
ok(fr.E[east] > br.E[east], 'uphill out costs more than the way back downhill');
const rf = reachField(fr, br, { tMaxS: 1e9, eMaxJ: fr.E[east] + br.E[east] + 1 }); ok(rf.used[east] < 1 && rf.used[east] > 0.99, 'reach: used fraction ~ 1 at the limit');
// 3. line of sight: flat = visible; a 20 m wall between = hidden behind it, visible beside it
const wall = new Float32Array(w * h); for (let r = 0; r < h; r++) wall[r * w + 28] = 20;
const vf = viewshed({ dem: flat, w, h, px }, [20, 5], 3, 1.8), vw = viewshed({ dem: wall, w, h, px }, [20, 5], 3, 1.8);
ok(vf[20 * w + 38] === 1, 'flat: far cell visible'); ok(vw[20 * w + 35] === 0, 'wall: cell behind the wall hidden');
ok(vw[20 * w + 20] === 1, 'wall: cell before the wall visible');
// curvature: on flat ground at 20 km a 1.8 m receiver and 3 m antenna still see each other (horizon ~ 4.7+3.5 km? -> not at 20 km)
const big = 400, d = new Float32Array(big * 3), vv = viewshed({ dem: d, w: big, h: 3, px: 50 }, [1, 0], 3, 1.8);
const horizon = Math.sqrt(2 * MARS_R * 3) + Math.sqrt(2 * MARS_R * 1.8);       // ~ 4.5 + 3.5 km
ok(vv[1 * big + Math.floor((horizon - 500) / 50)] === 1 && vv[1 * big + Math.ceil((horizon + 500) / 50)] === 0, 'curvature: visible inside the radio horizon, hidden beyond (' + Math.round(horizon) + ' m)');
// 4. sun
const noon = sunPosition(18.44, 0, 12); ok(Math.abs(noon.el - (90 - 18.44)) < 1e-6 && Math.abs(noon.az - 180) < 1e-6, 'sun at equinox noon: south, elevation 90-lat');
const am = sunPosition(18.44, 0, 8); ok(am.az < 180 && am.el > 0, 'morning sun is in the east half'); ok(sunPosition(18.44, 0, 0).el < 0, 'midnight: below horizon');
// 5. shadow: a 10 m wall, sun low in the west (az 270, el 10): shadow falls east of the wall
const sw = shadowMask({ dem: wall, w, h, px }, 270, 10), sh = i => sw[20 * w + i];
ok(sh(30) === 1 && sh(26) === 0 && sh(20) === 0, 'shadow is on the lee (east) side of the wall only');
ok(shadowMask({ dem: wall, w, h, px }, 270, -5).every(v => v === 1), 'night: everything dark');
// 6. time budget on a synthetic plan: sun above 5 deg 7-18 h, cold below -90 C after 20 h
const hourly = Array.from({ length: 24 }, (_, i) => ({ hour: i, sun_elev_deg: Math.round(70 * Math.sin((i - 6) / 12 * Math.PI) * 100) / 100, temp_c: i >= 21 || i < 4 ? -100 : -40 }));
const plan = { hourly, limits: { min_sun_elev_deg: 5, t_min_c: -90, tau_max: 3 } };
const ok1 = timeBudget(plan, 9, 4), late = timeBudget(plan, 15, 4), night = timeBudget(plan, 20, 2);
ok(ok1.status === 'ok' && late.status === 'danger' && late.sunsetH > 17 && late.sunsetH < 19, 'walk 15-19 h ends after sunset: danger, sunset found ' + (late.sunsetH && late.sunsetH.toFixed(2)));
ok(night.coldH > 0 && night.minTempC === -100, 'night walk goes below the cold limit');
ok(ok1.safeStarts.length >= 1 && ok1.safeStarts[0][0] >= 6.2 && ok1.safeStarts[0][1] <= 13.9, 'safe start window is inside the daylight');
process.exit(bad ? 1 : 0);
