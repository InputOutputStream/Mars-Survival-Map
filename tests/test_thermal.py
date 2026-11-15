import numpy as np
from mars_survival import thermal as T
from mars_survival.schema import Grid


def test_global_mean_insolation_matches_analytic_value():
    # Area-weighted global mean of the year-averaged insolation is S_mean/4 / sqrt(1 - e^2) (exact for any obliquity).
    g = Grid(0.25); lat = g.lats(); w = np.cos(np.deg2rad(lat))
    q = T.annual_mean_insolation(lat)
    got = (q * w).sum() / w.sum()
    assert abs(got - T.S_MEAN / 4 / np.sqrt(1 - T.ECC**2)) < 0.5


def test_symmetric_and_decreasing_with_latitude():
    t = T.mean_surface_temperature(np.array([0., 20., 40., 60., 80., -20., -40., -60., -80.]))
    assert abs(t[3] - t[7]) < 0.5 and abs(t[1] - t[5]) < 0.5      # annual mean is north-south symmetric
    assert t[0] > t[1] > t[2] > t[3] > t[4]


def test_sanity_against_nasa_values():
    # Compared with numbers that are NOT used in the model: NASA Fact Sheet mean ~214 K, MEDA Jezero air mean 221.7 K
    # (sols 31-1771, median of channels). We only require the right ballpark (the model ignores the atmosphere).
    g = Grid(); lat = g.lats(); w = np.cos(np.deg2rad(lat))
    t = T.mean_surface_temperature(lat)
    assert 205 < (t * w).sum() / w.sum() < 222
    assert 212 < float(T.mean_surface_temperature(np.array([18.4]))[0]) < 226


def test_never_below_co2_frost_point():
    assert T.mean_surface_temperature(np.array([89.9, -89.9])).min() >= T.CO2_FROST_K
