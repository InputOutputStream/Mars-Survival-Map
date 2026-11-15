#!/usr/bin/env python3
"""
survival_schema.py - data schema and "survivability" scoring per grid cell.

Principle
  1. Equirectangular grid (planetocentric lat/lon, east positive).
  2. Each raw layer is converted to a 0..1 score (1 = favourable) by a ramp.
  3. Hard constraints: excluded cells (slope, elevation...) -> score 0.
  4. Overall score = weighted GEOMETRIC mean: one catastrophic factor drags everything
     down (a lack of water is not compensated by pleasant temperatures).
  5. The "limiting factor" (layer with the minimum score) is kept to explain the map.
  6. Missing layers: ignored for the cell, and the coverage is recorded.

The thresholds are starting HYPOTHESES to be calibrated against the literature / your team.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
import numpy as np

MARS_RADIUS_M = 3_396_190.0  # MOLA reference radius
P0_PA = 610.0                # reference pressure at the datum (order of magnitude)
SCALE_HEIGHT_M = 11_100.0    # atmospheric scale height (approx.)
FLOOR = 0.02                 # floor for the log (avoids log(0))


def ramp(x, lo, hi):
    """0 at lo, 1 at hi, linear in between (lo<hi). For 'less is better', use 1-ramp."""
    return np.clip((np.asarray(x, dtype=float) - lo) / (hi - lo), 0.0, 1.0)


# --------------------------------------------------------------------------- grid
@dataclass(frozen=True)
class Grid:
    res_deg: float = 0.5

    @property
    def shape(self) -> tuple[int, int]:
        return int(180 / self.res_deg), int(360 / self.res_deg)

    def lats(self) -> np.ndarray:
        return 90 - self.res_deg * (np.arange(self.shape[0]) + 0.5)

    def lons(self) -> np.ndarray:
        return -180 + self.res_deg * (np.arange(self.shape[1]) + 0.5)

    def cell_area_m2(self) -> np.ndarray:
        lat = np.deg2rad(self.lats())
        half = np.deg2rad(self.res_deg) / 2
        band = MARS_RADIUS_M**2 * np.deg2rad(self.res_deg) * (np.sin(lat + half) - np.sin(lat - half))
        return np.repeat(band[:, None], self.shape[1], axis=1)


# --------------------------------------------------------------------------- layers
@dataclass(frozen=True)
class Layer:
    """A raw variable -> 0..1 score by linear ramp (lo -> 0, hi -> 1; `invert`: less = better)."""
    key: str
    label: str
    unit: str
    source: str                                   # originating PDS/NASA dataset
    lo: float
    hi: float
    invert: bool
    weights: dict[str, float]                     # weight per profile
    label_en: str = ""
    exclude_gt: float | None = None               # hard constraint: raw > threshold -> cell excluded
    exclude_profiles: tuple[str, ...] = ()        # profiles where the exclusion applies

    def score(self, x: np.ndarray) -> np.ndarray:
        r = ramp(x, self.lo, self.hi)
        return 1.0 - r if self.invert else r

    def exclude(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(x, dtype=float) > self.exclude_gt

    def describe(self) -> dict:
        """Serializable version (for the web viewer: "how is this layer scored?")."""
        return {"key": self.key, "label": self.label, "label_en": self.label_en or self.label, "unit": self.unit,
                "source": self.source, "lo": self.lo, "hi": self.hi, "invert": self.invert,
                "weights": self.weights, "exclude_gt": self.exclude_gt, "exclude_profiles": list(self.exclude_profiles)}


_B = ("habitat", "landing")
LAYERS: list[Layer] = [
    Layer("water_ice_depth_m", "Profondeur de glace d'eau", "m", "SWIM / SHARAD / Odyssey GRS", 0.0, 5.0, True,
          {"habitat": 3.0, "landing": 0.5}, "Water-ice depth"),
    Layer("weh_wt_pct", "Hydrogène équivalent eau", "wt %", "Odyssey GRS (neutrons)", 2.0, 30.0, False,
          {"habitat": 1.5, "landing": 0.2}, "Water-equivalent hydrogen"),
    Layer("epithermal_cps", "Flux de neutrons épithermiques (proxy hydrogène)", "counts/s", "Odyssey GRS ns_epithermal (Feldman 2002)",
          0.0, 1.0, True, {"habitat": 1.5, "landing": 0.2}, "Epithermal neutron flux (hydrogen proxy, less flux = more hydrogen)"),
    Layer("temp_mean_k", "Température moyenne annuelle", "K", "MRO MCS / THEMIS / MEDA", 170.0, 260.0, False,
          {"habitat": 2.0, "landing": 1.0}, "Mean annual temperature"),
    Layer("temp_diurnal_k", "Amplitude thermique jour/nuit", "K", "THEMIS / REMS / MEDA", 40.0, 110.0, True,
          {"habitat": 1.0, "landing": 0.5}, "Day/night temperature swing"),
    Layer("radiation_msv_day", "Dose de rayonnement", "mSv/day", "MSL RAD + derived from elevation", 0.2, 1.0, True,
          {"habitat": 2.5, "landing": 0.5}, "Radiation dose"),
    Layer("pressure_pa", "Pression atmosphérique", "Pa", "derived from MOLA + MCS", 300.0, 1200.0, False,
          {"habitat": 1.0, "landing": 1.5}, "Atmospheric pressure"),
    Layer("slope_deg", "Pente", "°", "MOLA / HiRISE DTM", 2.0, 15.0, True,
          {"habitat": 1.0, "landing": 3.0}, "Slope", exclude_gt=25.0, exclude_profiles=_B),
    Layer("elevation_m", "Altitude MOLA", "m", "MGS MOLA", 0.0, 2000.0, True,
          {"habitat": 0.0, "landing": 2.0}, "MOLA elevation", exclude_gt=2000.0, exclude_profiles=("landing",)),
    Layer("thermal_inertia_tiu", "Inertie thermique (nuit)", "tiu", "MGS TES (Putzig & Mellon 2007)", 100.0, 300.0, False,
          {"habitat": 0.5, "landing": 1.5}, "Thermal inertia (night): low = loose dust, high = firm ground"),
    Layer("rock_abundance_frac", "Abondance de rochers", "fraction", "THEMIS / TES", 0.05, 0.20, True,
          {"habitat": 0.5, "landing": 2.5}, "Rock abundance"),
    Layer("dust_tau", "Opacité poussière", "tau", "MRO MCS / MEDA", 0.3, 1.5, True,
          {"habitat": 1.0, "landing": 0.5}, "Dust opacity"),
    Layer("resource_minerals_idx", "Minéraux hydratés/ressources", "index 0-1", "CRISM", 0.0, 1.0, False,
          {"habitat": 1.0, "landing": 0.0}, "Hydrated minerals / resources"),
]
PROFILES = ("habitat", "landing")


# --------------------------------------------------------------------------- derivations
def derive_from_elevation(elev_m: np.ndarray) -> dict[str, np.ndarray]:
    """Pressure and radiation dose approximated from elevation (to be replaced by measurements)."""
    pressure = P0_PA * np.exp(-elev_m / SCALE_HEIGHT_M)
    # ~0.67 mSv/day measured at Gale (~ -4.4 km, ~850 Pa); the dose drops as the air column increases.
    dose = 0.67 * (pressure / 850.0) ** -0.25
    return {"pressure_pa": pressure, "radiation_msv_day": dose}


# --------------------------------------------------------------------------- scoring
def compute(data: dict[str, np.ndarray], profile: str = "habitat", min_coverage: float = 0.5,
            layers: list[Layer] | None = None):
    """Returns a dict: score (H,W), limiting (H,W) index, coverage, excluded, layer_scores."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    layers = LAYERS if layers is None else layers
    used = [L for L in layers if L.key in data and L.weights.get(profile, 0) > 0]
    if not used:
        raise ValueError("no usable layer")
    shape = data[used[0].key].shape

    scores = np.stack([L.score(data[L.key]) for L in used])            # (n,H,W), NaN preserved
    w = np.array([L.weights[profile] for L in used])[:, None, None]
    valid = ~np.isnan(scores)

    num = np.nansum(w * np.log(np.maximum(np.where(valid, scores, 1.0), FLOOR)), axis=0)
    den = (w * valid).sum(axis=0)
    total = np.where(den > 0, np.exp(num / np.where(den > 0, den, 1.0)), np.nan)

    coverage = den / w.sum()
    total = np.where(coverage >= min_coverage, total, np.nan)

    excluded = np.zeros(shape, dtype=bool)
    for L in layers:
        if L.exclude_gt is not None and L.key in data and profile in L.exclude_profiles:
            excluded |= np.nan_to_num(L.exclude(data[L.key]), nan=False).astype(bool)
    total = np.where(excluded, 0.0, total)

    limiting = np.nanargmin(np.where(valid, scores, np.inf), axis=0)
    return {
        "score": total, "excluded": excluded, "coverage": coverage,
        "limiting_idx": limiting, "limiting_keys": [L.key for L in used],
        "layer_scores": {L.key: scores[i] for i, L in enumerate(used)},
    }


# --------------------------------------------------------------------------- configuration & sensitivity
def apply_overrides(cfg: dict, layers: list[Layer] | None = None) -> list[Layer]:
    """Applies config/scoring.json: {"layers": {"slope_deg": {"lo":2,"hi":15,"weights":{"landing":4},"exclude_gt":22}}}.
    Any unknown key raises an error (no silent typos)."""
    out = []
    spec = dict(cfg.get("layers", {}))
    for L in (LAYERS if layers is None else layers):
        o = spec.pop(L.key, None)
        if o:
            bad = set(o) - {"lo", "hi", "invert", "weights", "exclude_gt", "exclude_profiles"}
            if bad:
                raise ValueError(f"{L.key} : unknown keys {sorted(bad)}")
            o = dict(o)
            if "weights" in o:
                unknown = set(o["weights"]) - set(PROFILES)
                if unknown:
                    raise ValueError(f"{L.key} : unknown profiles {sorted(unknown)}")
                o["weights"] = {**L.weights, **o["weights"]}
            if "exclude_profiles" in o:
                o["exclude_profiles"] = tuple(o["exclude_profiles"])
            L = replace(L, **o)
            if not L.lo < L.hi:
                raise ValueError(f"{L.key} : lo must be < hi")
        out.append(L)
    if spec:
        raise ValueError(f"unknown layers in the scoring config: {sorted(spec)}")
    return out


def weight_sensitivity(data: dict[str, np.ndarray], profile: str = "habitat", layers: list[Layer] | None = None,
                       top_frac: float = 0.02, factors: tuple[float, ...] = (0.5, 2.0)) -> list[dict]:
    """For each layer: its weight is multiplied by 0.5 then 2, and we measure how much the set of the
    `top_frac` best cells changes (mean Jaccard index; 1 = no change). Layers with a low Jaccard
    are those whose weight (an assumption!) drives the result: to be calibrated first."""
    layers = LAYERS if layers is None else layers

    def top(ls):
        s = compute(data, profile, layers=ls)["score"]
        v = np.where(np.isfinite(s), s, -np.inf).ravel()
        n = max(1, int(top_frac * np.isfinite(s).sum()))
        return set(np.argpartition(v, -n)[-n:].tolist())

    base = top(layers)
    rows = []
    for L in layers:
        w = L.weights.get(profile, 0.0)
        if L.key not in data or w <= 0:
            continue
        js = []
        for f in factors:
            alt = [replace(M, weights={**M.weights, profile: w * f}) if M.key == L.key else M for M in layers]
            t = top(alt)
            js.append(len(base & t) / len(base | t))
        rows.append({"layer": L.key, "weight": w, "jaccard_mean": round(float(np.mean(js)), 3),
                     "jaccard_min": round(float(min(js)), 3)})
    return sorted(rows, key=lambda r: r["jaccard_mean"])


# --------------------------------------------------------------------------- SQLite storage
DDL = """
CREATE TABLE IF NOT EXISTS grid_meta(
  id INTEGER PRIMARY KEY CHECK (id=1), res_deg REAL NOT NULL, radius_m REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS layer_def(
  key TEXT PRIMARY KEY, label TEXT, unit TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS source_file(
  id INTEGER PRIMARY KEY, url TEXT UNIQUE, product_id TEXT, sha256 TEXT, fetched_at TEXT, layer_key TEXT REFERENCES layer_def(key));
CREATE TABLE IF NOT EXISTS cell(
  row INTEGER, col INTEGER, lat REAL NOT NULL, lon REAL NOT NULL, area_m2 REAL NOT NULL, PRIMARY KEY(row, col));
CREATE TABLE IF NOT EXISTS cell_value(
  row INTEGER, col INTEGER, layer_key TEXT REFERENCES layer_def(key), raw REAL, score REAL, source_id INTEGER REFERENCES source_file(id),
  PRIMARY KEY(row, col, layer_key));
CREATE TABLE IF NOT EXISTS cell_score(
  row INTEGER, col INTEGER, profile TEXT, score REAL, coverage REAL, excluded INTEGER, limiting_layer TEXT, computed_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(row, col, profile));
CREATE INDEX IF NOT EXISTS idx_score ON cell_score(profile, score DESC);
"""


def init_db(path: str, grid: Grid = Grid()) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript(DDL)
    db.execute("INSERT OR REPLACE INTO grid_meta(id,res_deg,radius_m) VALUES(1,?,?)", (grid.res_deg, MARS_RADIUS_M))
    db.executemany("INSERT OR REPLACE INTO layer_def VALUES(?,?,?,?)", [(L.key, L.label, L.unit, L.source) for L in LAYERS])
    db.commit()
    return db


