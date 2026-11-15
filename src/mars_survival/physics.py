"""
physics.py - energy cost of walking on a slope, scaled to Martian gravity.

SOURCES (see docs/SOURCES.md):
  [M02] Minetti, Moia, Roi, Susta, Ferretti (2002) J Appl Physiol 93:1039-1046, doi:10.1152/japplphysiol.01177.2001.
        Treadmill measurements, 10 men (mountain athletes, 61.2 kg), grades -0.45..+0.45, EARTH gravity, no load.
        Published polynomial (Fig. 1): Cw(i) = 280.5 i^5 - 58.7 i^4 - 76.8 i^3 + 51.9 i^2 + 19.6 i + 2.5   [J/(kg·m)], R²=0.999.
        Beyond +0.15: mechanical lifting work ~ g·sin(atan|i|) with efficiency 0.243 (walking, uphill); Eq. (1).
  [C00] Cavagna, Willems, Heglund (2000) J Physiol 528:657-668 "The role of gravity in human walking: pendular energy
        exchange, external work and optimal speed". Force platform in a parabolic-flight aircraft, 3 men, simulated
        gravities 0.4 / 1.0 / 1.5 g (measured acceleration 3.90 m/s² at "0.4 g"). Results used: minimum W_ext 0.30 J/(kg·m)
        at 4.5 km/h (1 g) and 0.15 at 2.5 km/h (0.4 g); maximum pendular recovery at 5.5 km/h (1 g), 3.5 km/h (0.4 g),
        ~6.5 km/h (1.5 g); maximum step length ~1 m; speed range ~half that on Earth at 0.4 g.
  [A16] Kubis et al. (1972) Apollo 16 Time and Motion Study, NASA MSC M72-6, NTRS 19730008098 : metabolic power
        of astronauts in a suit on the Moon: walking ~3.0 ft/s: 1112-1185 BTU/h; carrying a 41 lb load: up to 2300 BTU/h.

ASSUMPTIONS (to be displayed as-is in the interface):
  H1 the "slope" component of the cost (Cw(i) - Cw(0)) is dominated by the lifting work m·g·Δh: it is therefore scaled by
     g_Mars/g_Earth. This is an approximation (efficiency assumed constant, unloaded athletes, Earth).
  H2 the "level terrain" component is scaled by level_scale = 0.75 (see [C00] below). Derivation:
     total cost = external work + internal work; at ~3 km/h on Earth, internal ≈ external (Willems 1995, cited in [C00]);
     at 0.4 g the minimum external work is HALF that at 1 g (0.15 vs 0.30 J/(kg·m)); internal work is assumed
     unchanged ([C00]: "about the same or decreases"). Hence (0.5+1)/(1+1) = 0.75, i.e. -25 %, which [C00] relates to the
     metabolic measurements in reduced gravity. Assumption: g_Mars/g_Earth = 0.38 is treated like the experimental 0.4 g;
     internal work might drop a little: 0.75 is therefore rather an upper bound. Pressurized suit not included.
  H3 Martian ground (sand, regolith) costs more than a treadmill: not modelled here (see Zamparo 1992, sand, cited in [M02]).
"""
from __future__ import annotations

import math

G_EARTH = 9.80665      # m/s²
G_MARS = 3.71          # m/s² (NASA Mars Fact Sheet: to be re-verified in the documentation, not re-read here)
BTU_PER_H_TO_W = 0.29307107
GRADE_RANGE = 0.45     # validity range measured by [M02]

# [C00]: W_ext(0.4 g)/W_ext(1 g) = 0.15/0.30; internal work ≈ external work on Earth at ~3 km/h and assumed constant (H2).
WEXT_RATIO_04G = 0.15 / 0.30
LEVEL_SCALE_MARS = (WEXT_RATIO_04G + 1.0) / 2.0   # = 0.75
V_OPT_EARTH_KMH = 5.5   # [C00] maximum pendular recovery speed at 1 g

_COEF = (280.5, -58.7, -76.8, 51.9, 19.6, 2.5)   # i^5 .. i^0


def minetti_cw(grade: float) -> float:
    """Walking cost [J/(kg·m)] at grade `grade` (= tan θ, +uphill/-downhill), Earth. Range |i| <= 0.45."""
    if abs(grade) > GRADE_RANGE + 1e-9:
        raise ValueError(f"grade {grade:+.2f} outside the measured range (|i| <= {GRADE_RANGE})")
    i = grade
    return ((((_COEF[0] * i + _COEF[1]) * i + _COEF[2]) * i + _COEF[3]) * i + _COEF[4]) * i + _COEF[5]


def walking_cost(grade: float, g: float = G_MARS, level_scale: float = LEVEL_SCALE_MARS) -> float:
    """Cost [J/(kg·m)] with the slope component scaled by gravity (H1) and the level component by `level_scale` (H2)."""
    level = minetti_cw(0.0)
    return level * level_scale + (minetti_cw(grade) - level) * (g / G_EARTH)


def grade_from_angle(deg: float) -> float:
    return math.tan(math.radians(deg))


def energy_per_metre_j(grade: float, mass_kg: float, g: float = G_MARS, level_scale: float = LEVEL_SCALE_MARS) -> float:
    """Metabolic energy [J] for 1 m of walking (mass = body + carried equipment)."""
    return max(walking_cost(grade, g, level_scale), 0.0) * mass_kg


def speed_for_power(grade: float, power_w: float, mass_kg: float, g: float = G_MARS, level_scale: float = LEVEL_SCALE_MARS) -> float:
    """Speed [m/s] sustainable at a given metabolic power: v = P / (C·m). Steep downhill: C -> small,
    the speed blows up: it is capped at 3 m/s (arbitrary safety limit, H4)."""
    c = walking_cost(grade, g, level_scale)
    return min(power_w / (max(c, 1e-3) * mass_kg), 3.0)


def optimal_speed_kmh(g: float = G_MARS) -> float:
    """Walking speed of maximum pendular recovery. Assumption H5: v ∝ sqrt(g) (constant Froude number).
    Check against [C00]: 0.4 g -> 3.48 km/h (measured 3.5); 1.5 g -> 6.7 km/h (measured ~6.5). Mars (0.378 g) -> ~3.4 km/h."""
    return V_OPT_EARTH_KMH * math.sqrt(g / G_EARTH)


def btu_per_h_to_w(btu_h: float) -> float:
    return btu_h * BTU_PER_H_TO_W


# MEASURED values (Apollo 16, pressurized suit, Moon) converted to watts: calibration milestones, not limits.
APOLLO16_W = {
    "traverse_cdr": btu_per_h_to_w(1112),
    "traverse_lmp": btu_per_h_to_w(1185),
    "load_carry_peak": btu_per_h_to_w(2300),
    "lrv_riding_avg_eva1": btu_per_h_to_w(633),
}
