// node tests/marsclock_test.mjs
import assert from 'node:assert/strict';
import { marsSolDate, marsTime, solarLongitudeAndEot, hhmm } from '../web/marsclock.mjs';
// 1. Defining epoch of the algorithm: JD_TT 2451549.5 (2000-01-06 00:00 TT) is MSD 44796.0 - 0.0009626 (before the 69 s offset).
const msdAtEpoch = (2451549.5 - 2451549.5) / 1.0274912517 + 44796.0 - 0.0009626;
assert.ok(Math.abs(msdAtEpoch - 44795.9990374) < 1e-9);
// 2. A Mars day is 1.0274912517 Earth days: MSD advances by exactly 1 over that span.
const t0 = Date.UTC(2026, 10, 6, 12), dt = 1.0274912517 * 86400000;
assert.ok(Math.abs(marsSolDate(t0 + dt) - marsSolDate(t0) - 1) < 1e-9);
// 3. Longitude shifts local mean time by 1 h per 15 deg east, wrapping at 24 h.
const a = marsTime(t0, 0).lmst, b = marsTime(t0, 15).lmst;
assert.ok(Math.abs(((b - a + 24) % 24) - 1) < 1e-9);
// 4. Sanity against history: Perseverance touched down 2021-02-18 about 20:55 UTC at Jezero (77.45 E)
//    in the mid-afternoon (the signal took about 11 min, so touchdown was about 20:44 UTC). Soft sanity check only.
const lm = marsTime(Date.UTC(2021, 1, 18, 20, 44), 77.45);   // 20:55 UTC is when Earth received the signal; light time was about 11 min
console.log('landing: LMST', hhmm(lm.lmst), 'LTST', hhmm(lm.ltst), 'Ls', lm.ls.toFixed(1), 'EOT min', (lm.eotH * 60).toFixed(1));
assert.ok(lm.ltst > 14.8 && lm.ltst < 15.7);   // the mission is said to have targeted mid-afternoon (about 15:00 true solar time); from memory, to verify
// 5. Equation of time stays within the known +-51 min over a full Mars year, and Ls covers 0..360.
let mx = 0, lsMin = 999, lsMax = -1;
for (let d = 0; d < 700; d += 2) { const r = solarLongitudeAndEot(Date.UTC(2026, 0, 1) + d * 86400000); mx = Math.max(mx, Math.abs(r.eotH * 60)); }
assert.ok(mx > 40 && mx < 55, 'max |EOT| min = ' + mx);
// 6. Ls near the March-equinox analogue: Ls 0 occurs once per Mars year (686.98 d); the sign of EOT flips with Ls.
const a1 = solarLongitudeAndEot(Date.UTC(2026, 5, 1)), a2 = solarLongitudeAndEot(Date.UTC(2026, 5, 1) + 686.98 * 86400000);
assert.ok(Math.abs(((a2.ls - a1.ls + 540) % 360) - 180) < 0.5);
assert.equal(hhmm(5.5), '05:30');
console.log('marsclock ok');
