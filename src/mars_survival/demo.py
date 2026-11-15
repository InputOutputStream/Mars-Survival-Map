"""demo.py - SYNTHETIC layers to test the whole chain without downloading any data."""
from __future__ import annotations

import numpy as np

from .schema import Grid


def synthetic_layers(grid: Grid, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    lat, lon = np.meshgrid(grid.lats(), grid.lons(), indexing="ij")
    elev = (2500 * np.sin(np.deg2rad(lon) * 2) * np.cos(np.deg2rad(lat)) - 1500
            + rng.normal(0, 250, lat.shape))
    layers = {
        "elevation_m": elev,
        "slope_deg": np.abs(rng.normal(5, 6, lat.shape)),
        "temp_mean_k": 235 - 0.65 * np.abs(lat) + rng.normal(0, 2, lat.shape),
        "temp_diurnal_k": 95 - 0.4 * np.abs(lat),
        "water_ice_depth_m": np.where(np.abs(lat) > 40, rng.uniform(0.0, 1.5, lat.shape),
                                      rng.uniform(3, 20, lat.shape)),
        "weh_wt_pct": np.clip(2 + 0.5 * np.maximum(np.abs(lat) - 30, 0) + rng.normal(0, 2, lat.shape), 0, 40),
        "rock_abundance_frac": np.clip(rng.normal(0.08, 0.04, lat.shape), 0, 0.4),
        "dust_tau": rng.uniform(0.3, 1.2, lat.shape),
        "resource_minerals_idx": np.clip(rng.normal(0.3, 0.25, lat.shape), 0, 1),
    }
    layers["slope_deg"][0, 0] = np.nan  # partially missing layer, to test coverage
    return {k: v.astype(np.float32) for k, v in layers.items()}
