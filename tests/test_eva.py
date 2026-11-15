import pytest

from mars_survival import eva


def test_equinox_equator_basics():
    assert eva.declination_deg(0) == pytest.approx(0)
    assert eva.sun_elevation_deg(0, 0, 12) == pytest.approx(90, abs=1e-6)
    assert eva.daylight_hours(0, 0) == pytest.approx(12)
    assert eva.declination_deg(90) == pytest.approx(25.19, abs=1e-6)


def test_polar_day_and_night():
    assert eva.daylight_hours(80, 90) == 24.0      # boreal summer, polar day
    assert eva.daylight_hours(80, 270) == 0.0      # boreal winter, polar night
    assert eva.sol_plan(80, 270)["eva_hours"] == 0


def test_windows_follow_sun_and_cold_limit():
    p = eva.sol_plan(18.4, 0.0, mean_k=215, diurnal_k=80, tau=0.5)
    assert p["windows"] and all(7 <= w["start_h"] <= 12 and w["end_h"] <= 18 for w in p["windows"])
    cold = eva.sol_plan(18.4, 0.0, mean_k=150, diurnal_k=40, tau=0.5)       # too cold all day
    assert cold["eva_hours"] == 0
    storm = eva.sol_plan(18.4, 250.0, tau=5.0)
    assert storm["eva_hours"] == 0 and storm["dust_season"]


def test_seasonal_plans_cover_year():
    plans = eva.seasonal_plans(18.4, 215, 80)
    assert [p["ls"] for p in plans] == [float(x) for x in range(0, 360, 30)]
