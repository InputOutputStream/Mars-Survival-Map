"""
eva.py - EVA planner (Marswalk): when to go outside during a Martian sol?

GEOMETRIC part (reliable): solar declination as a function of solar longitude Ls, Sun elevation,
sunrise/sunset, day length. Classic formulas: sin δ = sin(25.19°)·sin(Ls) (circular orbit).

MODEL part (assumptions to be replaced by MEDA/REMS/MCS data):
  - temperature = day/night sinusoid (max ≈ 14:00 local solar time), from the supplied mean and amplitude;
  - attenuation of the solar flux by dust: exp(-tau / sin(elevation));
  - dust storm season: Ls 180–360 (qualitative, warm southern season).
An EVA window = hours where Sun ≥ min_sun_elev_deg AND T ≥ t_min_c AND tau ≤ tau_max.
This is NOT an operational tool; it serves to make the constraints visible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

OBLIQUITY_DEG = 25.19
SOL_HOURS_EARTH = 24.6598


@dataclass(frozen=True)
class EvaLimits:
    min_sun_elev_deg: float = 5.0
    t_min_c: float = -90.0     # assumption: suit comfort/safety limit, to be confirmed
    tau_max: float = 3.0       # beyond this: degraded visibility/energy (storm)


def declination_deg(ls_deg: float) -> float:
    return math.degrees(math.asin(math.sin(math.radians(OBLIQUITY_DEG)) * math.sin(math.radians(ls_deg))))


def sun_elevation_deg(lat_deg: float, ls_deg: float, hour: float) -> float:
    """Sun elevation (°) at local solar time `hour` (0..24, noon = 12)."""
    phi, dec = math.radians(lat_deg), math.radians(declination_deg(ls_deg))
    h = math.radians((hour - 12.0) * 15.0)
    s = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(h)
    return math.degrees(math.asin(max(-1.0, min(1.0, s))))


def daylight_hours(lat_deg: float, ls_deg: float) -> float:
    phi, dec = math.radians(lat_deg), math.radians(declination_deg(ls_deg))
    x = -math.tan(phi) * math.tan(dec)
    if x >= 1:
        return 0.0        # polar night
    if x <= -1:
        return 24.0       # polar day
    return 24.0 * math.degrees(math.acos(x)) / 180.0


def dust_season(ls_deg: float) -> bool:
    return 180.0 <= (ls_deg % 360.0) <= 360.0


def temperature_c(hour: float, mean_k: float, diurnal_k: float) -> float:
    """Air temperature near the ground (sinusoidal model; max at 14:00)."""
    return mean_k - 273.15 + (diurnal_k / 2.0) * math.cos(2 * math.pi * (hour - 14.0) / 24.0)


def sol_plan(lat_deg: float, ls_deg: float, mean_k: float = 215.0, diurnal_k: float = 80.0, tau: float = 0.5,
             limits: EvaLimits = EvaLimits(), step_h: float = 1.0) -> dict:
    """Hourly table + EVA windows for one sol."""
    rows, n = [], int(round(24 / step_h))
    for i in range(n):
        t = i * step_h
        el = sun_elevation_deg(lat_deg, ls_deg, t)
        temp = temperature_c(t, mean_k, diurnal_k)
        flux = max(0.0, math.sin(math.radians(el))) * math.exp(-tau / max(math.sin(math.radians(max(el, 0.5))), 0.05)) \
            if el > 0 else 0.0
        ok = el >= limits.min_sun_elev_deg and temp >= limits.t_min_c and tau <= limits.tau_max
        rows.append({"hour": t, "sun_elev_deg": round(el, 2), "temp_c": round(temp, 1),
                     "solar_flux_rel": round(flux, 3), "eva_ok": ok})
    windows, cur = [], None
    for r in rows:
        if r["eva_ok"] and cur is None:
            cur = r["hour"]
        if not r["eva_ok"] and cur is not None:
            windows.append((cur, r["hour"]))
            cur = None
    if cur is not None:
        windows.append((cur, 24.0))
    if len(windows) > 1 and windows[0][0] == 0.0 and windows[-1][1] == 24.0:   # window straddling midnight
        windows = [(windows[-1][0], windows[0][1] + 24.0)] + windows[1:-1]
    return {"lat": lat_deg, "ls": ls_deg, "declination_deg": round(declination_deg(ls_deg), 2),
            "daylight_h": round(daylight_hours(lat_deg, ls_deg), 2), "dust_season": dust_season(ls_deg),
            "tau": tau, "mean_k": mean_k, "diurnal_k": diurnal_k, "limits": limits.__dict__,
            "windows": [{"start_h": a, "end_h": b, "duration_h": round(b - a, 2)} for a, b in windows],
            "eva_hours": sum(r["eva_ok"] for r in rows) * step_h, "hourly": rows,
            "model_note": "Exact solar geometry; temperatures and dust = simplified model (assumptions)."}


def seasonal_plans(lat_deg: float, mean_k: float, diurnal_k: float, tau_by_season: float | None = None,
                   step_ls: int = 30) -> list[dict]:
    """One plan per Ls (0, 30, … 330). Default tau: 0.5 (off season) / 1.2 (storm season)."""
    plans = []
    for ls in range(0, 360, step_ls):
        tau = tau_by_season if tau_by_season is not None else (1.2 if dust_season(ls) else 0.5)
        plans.append(sol_plan(lat_deg, float(ls), mean_k, diurnal_k, tau))
    return plans
