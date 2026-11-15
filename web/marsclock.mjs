// Mars time from Earth time. Algorithm: Allison & McEwen 2000, "A post-Pathfinder evaluation of
// areocentric solar coordinates with improved timing recipes for Mars seasonal/diurnal climate studies",
// Planetary and Space Science 48, 215-235 (the "Mars24" algorithm, NASA GISS).
//   JD_TT = JD_UT + (TAI-UTC + 32.184 s) / 86400
//   MSD   = (JD_TT - 2451549.5 + k) / 1.0274912517 + 44796.0 - 0.0009626      (k = 0, the 2000 update of the paper)
//   MTC   = 24 h * MSD (mod 1)               Mars Coordinated Time = mean solar time at the Martian prime meridian
//   LMST  = MTC + east_longitude / 15        local MEAN solar time
//   LTST  = LMST + EOT                       local TRUE solar time (the Sun's actual position: noon = Sun highest)
// Equation of time (same paper, eqs. 15-20), with dt = JD_TT - 2451545.0:
//   M      = 19.3871 + 0.52402075 dt                                  mean anomaly (deg)
//   a_FMS  = 270.3871 + 0.524038496 dt                                fictitious mean Sun angle (deg)
//   PBS    = sum_i A_i cos(0.985626 dt / tau_i + phi_i)               planetary perturbations (7 terms, deg)
//   nu - M = (10.691 + 3.0e-7 dt) sin M + 0.623 sin 2M + 0.050 sin 3M + 0.005 sin 4M + 0.0005 sin 5M + PBS
//   Ls     = a_FMS + (nu - M)                                         areocentric solar longitude (season)
//   EOT    = 2.861 sin 2Ls - 0.071 sin 4Ls + 0.002 sin 6Ls - (nu - M)   (deg; /15 gives hours)
// Intuition: Mars' orbit is much more eccentric than Earth's (0.093), so the Sun runs ahead of or behind a
// uniform clock by up to about 50 min over the year. TAI-UTC is 37 s since 2017-01-01 and no later leap second
// is assumed (value to re-check).
// The mean Mars day lasts 1.0274912517 Earth days = 24 h 39 m 35.2 s.
export const TAI_MINUS_UTC_S = 37;
export const MARS_DAY_EARTH_DAYS = 1.0274912517;

export function julianDateUT(ms) { return ms / 86400000 + 2440587.5; }
export function marsSolDate(ms) {
  const jdTT = julianDateUT(ms) + (TAI_MINUS_UTC_S + 32.184) / 86400;
  return (jdTT - 2451549.5) / MARS_DAY_EARTH_DAYS + 44796.0 - 0.0009626;
}
const RAD = Math.PI / 180;
const PBS_A = [0.0071, 0.0057, 0.0039, 0.0037, 0.0021, 0.0020, 0.0018];
const PBS_TAU = [2.2353, 2.7543, 1.1177, 15.7866, 2.1354, 2.4694, 32.8493];
const PBS_PHI = [49.409, 168.173, 191.837, 21.736, 15.704, 95.528, 49.095];
export function solarLongitudeAndEot(ms) {
  const dt = julianDateUT(ms) + (TAI_MINUS_UTC_S + 32.184) / 86400 - 2451545.0;
  const M = 19.3871 + 0.52402075 * dt, aFMS = 270.3871 + 0.524038496 * dt;
  let pbs = 0; for (let i = 0; i < 7; i++) pbs += PBS_A[i] * Math.cos((0.985626 * dt / PBS_TAU[i] + PBS_PHI[i]) * RAD);
  const nuM = (10.691 + 3.0e-7 * dt) * Math.sin(M * RAD) + 0.623 * Math.sin(2 * M * RAD) + 0.050 * Math.sin(3 * M * RAD) + 0.005 * Math.sin(4 * M * RAD) + 0.0005 * Math.sin(5 * M * RAD) + pbs;
  const ls = (((aFMS + nuM) % 360) + 360) % 360;
  const eotDeg = 2.861 * Math.sin(2 * ls * RAD) - 0.071 * Math.sin(4 * ls * RAD) + 0.002 * Math.sin(6 * ls * RAD) - nuM;
  return { ls, eotH: eotDeg / 15 };
}
export function marsTime(ms, eastLonDeg) {
  const msd = marsSolDate(ms), mtc = ((msd % 1) + 1) % 1 * 24;
  const lmst = (((mtc + eastLonDeg / 15) % 24) + 24) % 24;
  const { ls, eotH } = solarLongitudeAndEot(ms);
  const ltst = (((lmst + eotH) % 24) + 24) % 24;
  return { msd, mtc, lmst, ltst, ls, eotH };
}
export function hhmm(h) { const m = Math.floor(h * 60 + 1e-9), hh = Math.floor(m / 60) % 24; return String(hh).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); }
