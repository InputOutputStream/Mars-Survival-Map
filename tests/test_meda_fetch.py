import importlib.util, pathlib
import requests

spec = importlib.util.spec_from_file_location("fetch_meda", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "fetch_meda.py")
fm = importlib.util.module_from_spec(spec); spec.loader.exec_module(fm)


def test_missing_sol_uses_nearest(monkeypatch, tmp_path):
    def fake(sol, kinds, out, groups):
        if sol == 391 or sol == 392:
            raise requests.exceptions.HTTPError("404")
        return [tmp_path / f"sol_{sol:04d}_PS.csv"]
    monkeypatch.setattr(fm, "fetch_sol", fake)
    used, got = fm.fetch_sol_near(391, ["PS"], tmp_path, [])
    assert used == 390 and got


def test_nothing_nearby_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(fm, "fetch_sol", lambda *a: (_ for _ in ()).throw(requests.exceptions.HTTPError("404")))
    try:
        fm.fetch_sol_near(391, ["PS"], tmp_path, [])
        assert False
    except requests.exceptions.RequestException:
        pass
