import math

import pytest

from mars_survival import physics as P

# Table 2 of Minetti et al. 2002: MEASURED cost of walking (mean ± standard deviation), J/(kg·m)
TABLE2 = {-0.45: (3.46, 0.95), -0.40: (3.23, 0.59), -0.35: (2.65, 0.68), -0.30: (2.18, 0.67), -0.20: (1.30, 0.48),
          -0.10: (0.81, 0.37), 0.0: (1.64, 0.50), 0.10: (4.68, 0.34), 0.20: (8.07, 0.57), 0.30: (11.29, 0.65),
          0.35: (12.72, 0.76), 0.40: (14.75, 0.61), 0.45: (17.33, 1.11)}


def test_polynomial_reproduces_published_measurements():
    for i, (mean, sd) in TABLE2.items():
        assert abs(P.minetti_cw(i) - mean) <= max(2 * sd, 0.9), (i, P.minetti_cw(i), mean)
    assert P.minetti_cw(0.45) == pytest.approx(17.6, abs=0.1)


def test_domain_is_enforced():
    with pytest.raises(ValueError):
        P.minetti_cw(0.6)


def test_cost_minimum_is_on_gentle_downhill():
    costs = {i / 100: P.minetti_cw(i / 100) for i in range(-45, 46)}
    # [M02] measures the minimum at -0.10; its polynomial places it near -0.15: a slight internal inconsistency in the paper, so we test for broad agreement
    assert -0.20 <= min(costs, key=costs.get) <= -0.05


def test_gravity_scaling():
    for i in (-0.2, 0.0, 0.1, 0.3):
        assert P.walking_cost(i, P.G_EARTH, 1.0) == pytest.approx(P.minetti_cw(i))      # Earth = Minetti
    assert P.walking_cost(0.0, g=P.G_EARTH, level_scale=1.0) == pytest.approx(P.minetti_cw(0.0))
    assert P.walking_cost(0.3) < P.minetti_cw(0.3)                                 # uphill is cheaper on Mars
    ratio = (P.walking_cost(0.3) - P.walking_cost(0.0)) / (P.minetti_cw(0.3) - P.minetti_cw(0.0))
    assert ratio == pytest.approx(P.G_MARS / P.G_EARTH)


def test_speed_for_power_inverse_and_monotonic():
    v0 = P.speed_for_power(0.0, 300, 170)
    assert P.speed_for_power(0.2, 300, 170) < v0 < P.speed_for_power(-0.1, 300, 170) + 1e-9
    c = P.walking_cost(0.1)
    assert P.energy_per_metre_j(0.1, 170) == pytest.approx(c * 170)
    assert P.speed_for_power(0.1, 300, 170) == pytest.approx(300 / (c * 170))


def test_apollo_unit_conversion():
    assert P.APOLLO16_W["traverse_cdr"] == pytest.approx(326, abs=1)
    assert P.APOLLO16_W["load_carry_peak"] == pytest.approx(674, abs=1)
    assert P.grade_from_angle(45) == pytest.approx(1.0)


def test_level_scale_from_cavagna():
    assert P.LEVEL_SCALE_MARS == pytest.approx(0.75)
    # -25 % on level ground in Martian gravity
    assert P.walking_cost(0.0) == pytest.approx(0.75 * P.minetti_cw(0.0))


def test_optimal_speed_matches_cavagna_and_apollo():
    assert P.optimal_speed_kmh(P.G_EARTH) == pytest.approx(5.5)
    assert P.optimal_speed_kmh(0.4 * P.G_EARTH) == pytest.approx(3.5, abs=0.1)     # measured [C00]
    assert P.optimal_speed_kmh(1.5 * P.G_EARTH) == pytest.approx(6.5, abs=0.3)     # measured [C00] "possibly"
    apollo_kmh = 3.0 * 0.3048 * 3.6                                                # 3 ft/s, Apollo 16
    assert abs(P.optimal_speed_kmh() - apollo_kmh) < 0.3
