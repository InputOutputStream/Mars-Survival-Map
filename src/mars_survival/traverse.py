"""
traverse.py - MINIMUM-ENERGY walking route (EVA): replaces the arbitrary "slope²" cost with the physics.py model.

Step between two neighbouring cells (ground distance d, elevation change dz, local grade i = dz/d, signed, in the walking direction):
    energy    E = m · Cw_Mars(i) · L · M      [J],   L = sqrt(d² + dz²),  M = mean of the terrain multiplier of the 2 cells
    speed     v = min(v_opt(g), P / (Cw_Mars(i) · m))     [m/s]   (H5: v_opt ∝ sqrt(g); P = sustained metabolic power)
    duration  t = L · M / v
Forbidden if |i| > 0.45 (limit of the Minetti 2002 measurements: we do not extrapolate) or if the terrain is impassable.

TERRAIN MULTIPLIER  M(r) = 1 + (r / r0)²,  r0 = 0.25 m   -   TEAM ASSUMPTION, no Martian NASA source.
  Purpose   : walking on uneven ground costs more energy and time than on smooth ground (side steps, shorter footholds,
              rebalancing, stepping over obstacles); without this term the route would ignore boulder fields and dunes.
  Intuition : r = standard deviation of the detrended relief in a window (site.roughness), in metres. Quadratic form because
              (i) M = 1 as r -> 0 (smooth ground: the Minetti model applies as is, measured on a treadmill);
              (ii) the effect is negligible as long as the irregularities are small compared with the length of a step (~0.5-1 m),
              then grows faster and faster as they approach the size of a step; (iii) a single parameter r0: the r
              where the cost doubles (M(r0) = 2).
  Anchoring : TERRESTRIAL terrain coefficients from Soule & Goldman (1972) J Appl Physiol 32(5):706-708, reused in
              Pandolf, Givoni & Goldman (1977) J Appl Physiol 43(4):577-581 (values read via Wikipedia "Pandolf equation",
              to be verified in the papers): paved road 1.0; dirt road 1.1; light brush 1.2; dense brush 1.5;
              swamp 1.8; loose sand 2.1; soft snow 15/25/35 cm: 2.5/3.3/4.1. Our values: M(0.10 m) = 1.16 ~ dirt/
              light brush; M(0.25 m) = 2.0 ~ swamp/loose sand; M(0.43 m) = 4.4: beyond that, NO measurement serves as an
              anchor: M then acts as an avoidance penalty, not as a measured energy. The energy displayed for a
              route crossing such sectors is therefore unreliable (probably overestimated).
  Limits    : (1) these coefficients are terrestrial (other soils, other gravity); (2) the HiRISE DTM at ~1 m/pixel does not see
              boulders of a few tens of cm: r measures metre-scale undulations, not the roughness underfoot;
              a boulder map (HiRISE image, rock abundance) would be the right data; (3) r0 and the quadratic form are to be
              recalibrated against measurements (rover traversability, analogue trials). To be replaced as soon as a source exists.
m (suit + equipment) and P are user INPUTS; the default values are assumptions, not measurements
(default P ≈ Apollo 16, 1112 BTU/h = 326 W in a suit on the Moon, NASA MSC M72-6).
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np

from . import physics as P

SQRT2 = math.sqrt(2.0)
_NEIGH = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
          (-1, -1, SQRT2), (-1, 1, SQRT2), (1, -1, SQRT2), (1, 1, SQRT2)]


@dataclass
class Walker:
    mass_kg: float = 170.0                     # ASSUMPTION: astronaut + suit + equipment (user input)
    power_w: float = P.APOLLO16_W["traverse_cdr"]
    g: float = P.G_MARS
    level_scale: float = P.LEVEL_SCALE_MARS
    rough_ref_m: float = 0.25                  # r0: roughness where the cost doubles. TEAM ASSUMPTION (see module header)
    rough_max_m: float = 1.50                  # beyond: impassable on foot. TEAM ASSUMPTION, no source
    time_scale: float = 1.0                    # user pace / model level-ground pace; scales durations only (energy per metre does not depend on speed)

    @property
    def v_opt_ms(self) -> float:
        return P.optimal_speed_kmh(self.g) / 3.6


def terrain_multiplier(rough: np.ndarray, w: Walker = Walker()) -> np.ndarray:
    m = 1.0 + (rough / w.rough_ref_m) ** 2
    return np.where(rough > w.rough_max_m, np.inf, m).astype(np.float32)


def step_cost(grade: float, length_m: float, mult: float, w: Walker) -> tuple[float, float]:
    """(energy J, duration s) of one step; (inf, inf) if the grade leaves the measured range."""
    if abs(grade) > P.GRADE_RANGE:
        return math.inf, math.inf
    c = P.walking_cost(grade, w.g, w.level_scale)
    v = min(w.v_opt_ms, w.power_w / (c * w.mass_kg))
    return w.mass_kg * c * length_m * mult, length_m * mult / (v * w.time_scale)


def find_route_energy(dem, tmult, px_m, start, goal, w: Walker = Walker(), objective: str = "energy") -> dict | None:
    """8-neighbour Dijkstra minimizing energy (objective='energy') or duration ('time'). Returns None if there is no route."""
    h, wd = dem.shape
    if not (0 <= start[0] < h and 0 <= start[1] < wd and 0 <= goal[0] < h and 0 <= goal[1] < wd):
        raise ValueError("start or goal outside the site")
    if not np.isfinite(tmult[start]) or not np.isfinite(tmult[goal]):
        return None
    k = 0 if objective == "energy" else 1
    dist = np.full((h, wd), np.inf)
    prev = np.full((h, wd), -1, dtype=np.int64)
    dist[start] = 0.0
    heap = [(0.0, start[0], start[1])]
    while heap:
        d, r, c = heapq.heappop(heap)
        if d > dist[r, c]:
            continue
        if (r, c) == goal:
            break
        for dr, dc, f in _NEIGH:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < h and 0 <= cc < wd) or not np.isfinite(tmult[rr, cc]):
                continue
            flat = f * px_m
            dz = float(dem[rr, cc] - dem[r, c])
            cost = step_cost(dz / flat, math.hypot(flat, dz), 0.5 * (float(tmult[r, c]) + float(tmult[rr, cc])), w)[k]
            if cost < dist[rr, cc] - d:
                dist[rr, cc] = d + cost
                prev[rr, cc] = r * wd + c
                heapq.heappush(heap, (d + cost, rr, cc))
    if not np.isfinite(dist[goal]):
        return None
    path, cur = [], goal[0] * wd + goal[1]
    while cur != -1:
        path.append((cur // wd, cur % wd))
        cur = int(prev[cur // wd, cur % wd])
    path.reverse()
    E = T = L = 0.0
    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        flat = math.hypot(r1 - r0, c1 - c0) * px_m
        dz = float(dem[r1, c1] - dem[r0, c0])
        e, t = step_cost(dz / flat, math.hypot(flat, dz), 0.5 * (float(tmult[r0, c0]) + float(tmult[r1, c1])), w)
        E += e; T += t; L += math.hypot(flat, dz)
    return {"path": path, "energy_j": E, "energy_kwh": E / 3.6e6, "time_h": T / 3600.0, "length_m": L,
            "mean_power_w": E / T if T else 0.0, "objective": objective}
