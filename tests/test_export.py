import numpy as np

from mars_survival import export
from mars_survival.schema import Grid


def test_top_sites_respect_min_separation_and_order():
    g = Grid(res_deg=2.0)
    score = np.random.default_rng(1).uniform(0, 1, g.shape)
    cov = np.ones(g.shape)
    lim = np.zeros(g.shape, dtype=int)
    sites = export.top_sites(score, lim, ["temp_mean_k"], cov, g, n=10, min_sep_deg=10.0)
    assert len(sites) == 10
    assert [s["score"] for s in sites] == sorted((s["score"] for s in sites), reverse=True)
    for i, a in enumerate(sites):
        for b in sites[i + 1:]:
            d = export._angdist_deg(a["lat"], a["lon"], b["lat"], b["lon"])
            assert d >= 10.0 - 1e-6


def test_colorize_transparent_for_nan_and_grey_for_excluded():
    s = np.array([[np.nan, 0.5], [1.0, 0.0]])
    ex = np.array([[False, False], [False, True]])
    rgba = export.colorize(s, ex)
    assert rgba[0, 0, 3] == 0
    assert tuple(rgba[1, 1]) == (40, 40, 40, 200)
    assert rgba[1, 0, 1] > rgba[1, 0, 0]  # score 1 -> vert dominant
