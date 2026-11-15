"""
thermal.py - annual mean surface temperature from an energy balance (a PHYSICS MODEL, not a measurement).

Idea. Sunlight absorbed by the ground over a Mars year, averaged, must leave as thermal radiation. If the ground stores
heat well (high thermal inertia), the temperature stays close to that of the year-averaged absorbed flux:

    T = ( (1 - A) * <Q> / (eps * sigma) ) ** 0.25

where <Q> is the year-averaged, day-averaged insolation at the latitude. Insolation depends on the orbit:
 - distance: S(r) = S_mean * (a / r)^2, S_mean = 586.2 W/m2 at the semi-major axis a (NASA Mars Fact Sheet);
 - declination from the obliquity (25.19 deg): sin(delta) = sin(obliquity) * sin(Ls);
 - orbit shape (eccentricity 0.0935): equal TIME steps (uniform mean anomaly), true anomaly nu = Ls - Ls_perihelion.
 Daily-mean insolation at latitude phi:  Q = S/pi * (h0 sin(phi) sin(delta) + cos(phi) cos(delta) sin(h0)),
 with sunrise hour angle h0 = arccos(-tan(phi) tan(delta)) (0 in polar night, pi in polar day).

What the model ignores, and what that does to the answer:
 - the atmosphere (greenhouse effect warms, winds move heat from warm to cold latitudes);
 - heat storage is assumed perfect, so this is an UPPER estimate (the true mean of T is lower than the T of the mean flux);
 - albedo is one global number, the Bond albedo; real albedo varies (0.1 to 0.3 or more);
 - CO2 frost: where the model goes below the CO2 frost point it is held there (frost condenses and releases heat);
 - elevation, slope, shadows.
 Expect errors of the order of 10 K. It is a stand-in until a measured or reanalysed temperature map (e.g. MACDA from
 MGS/TES) is loaded, and the viewer labels it "Physics model".

Inputs (NASA Mars Fact Sheet, https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html, read 2026-11-07):
 solar irradiance 586.2 W/m2, Bond albedo 0.250, eccentricity 0.0935, obliquity 25.19 deg.
 Not on that page, taken from Allison & McEwen 2000 (the Mars24 paper): Ls of perihelion about 251 deg (to verify).
 Not from NASA: emissivity 1.0 (blackbody, our simplest choice); CO2 frost point 148 K (about 6 mbar; standard physics,
 the exact figure should be sourced).
"""
from __future__ import annotations

import numpy as np

SIGMA = 5.670374419e-8          # Stefan-Boltzmann constant, W m-2 K-4 (CODATA 2018)
S_MEAN = 586.2                  # W/m2 at the semi-major axis (NASA Mars Fact Sheet)
ECC = 0.0935
OBLIQUITY_DEG = 25.19
LS_PERIHELION_DEG = 251.0
BOND_ALBEDO = 0.25
EMISSIVITY = 1.0
CO2_FROST_K = 148.0


def _orbit_samples(n: int = 720):
    """Equal-time samples of the orbit -> (Ls in radians, (a/r)^2)."""
    M = (np.arange(n) + 0.5) / n * 2 * np.pi
    E = M.copy()
    for _ in range(30):                                   # Kepler: E - e sin E = M
        E = E - (E - ECC * np.sin(E) - M) / (1 - ECC * np.cos(E))
    nu = 2 * np.arctan2(np.sqrt(1 + ECC) * np.sin(E / 2), np.sqrt(1 - ECC) * np.cos(E / 2))
    ls = nu + np.deg2rad(LS_PERIHELION_DEG)
    r_over_a = (1 - ECC**2) / (1 + ECC * np.cos(nu))
    return ls, r_over_a**-2


def annual_mean_insolation(lat_deg, n: int = 720) -> np.ndarray:
    """Year-averaged, day-averaged sunlight reaching the top of the ground, W/m2, at each latitude."""
    phi = np.deg2rad(np.asarray(lat_deg, dtype=float))[..., None]
    ls, dist = _orbit_samples(n)
    delta = np.arcsin(np.sin(np.deg2rad(OBLIQUITY_DEG)) * np.sin(ls))
    x = np.clip(-np.tan(phi) * np.tan(delta), -1.0, 1.0)
    h0 = np.arccos(x)
    q = S_MEAN * dist / np.pi * (h0 * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(h0))
    return q.mean(axis=-1)


def mean_surface_temperature(lat_deg, albedo: float = BOND_ALBEDO, emissivity: float = EMISSIVITY) -> np.ndarray:
    q = annual_mean_insolation(lat_deg)
    t = ((1 - albedo) * q / (emissivity * SIGMA)) ** 0.25
    return np.maximum(t, CO2_FROST_K)
