"""End-to-end build chain on a SYNTHETIC FIXTURE (labelled as a test: never presented as Mars)."""
import importlib.util, json
from pathlib import Path
import numpy as np
from mars_survival import site as S

p = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bj", p / "scripts" / "build_jezero.py"); bj = importlib.util.module_from_spec(spec); spec.loader.exec_module(bj)


def test_block_mean_handles_nan():
    a = np.array([[1, 3, np.nan, np.nan], [5, 7, np.nan, np.nan]], dtype=np.float32)
    b = bj.block_mean(a, 2)
    assert b[0, 0] == 4.0 and np.isnan(b[0, 1])


def test_meda_params_ignore_short_sols():
    hm = {str(h): 190.0 + 40 * np.cos((h - 14) / 24 * 2 * np.pi) for h in range(24)}
    meda = {"sols": {"1": {"air_temp_K": {"hourly_mean": {"16": 250.0}}}, "100": {"air_temp_K": {"hourly_mean": hm}}}}
    t = bj.meda_temperature_params(meda)
    assert t["sols_used"] == [100] and abs(t["diurnal_k"] - 80.0) < 0.5


def test_end_to_end_fixture(tmp_path):
    s = S.synthetic_site(size=200, px_m=2.0, seed=2)
    np.save(tmp_path / "dem.npy", s.dem)
    json.dump({"source_url": "TEST", "px_m": 2.0, "center_lat": 18.4, "center_lon": 77.5, "shape": [200, 200]}, open(tmp_path / "dem.json", "w"))
    hm = {str(h): 200.0 + 35 * np.cos((h - 14) / 24 * 2 * np.pi) for h in range(24)}
    json.dump({"source": "TEST", "units": {}, "sols": {"100": {"air_temp_K": {"hourly_mean": hm}}}}, open(tmp_path / "meda.json", "w"))
    out = tmp_path / "site"
    prov = bj.build(tmp_path / "dem.npy", tmp_path / "dem.json", tmp_path / "meda.json", out, max_dim=100, test_fixture=True)
    meta = json.load(open(out / "site.json"))
    assert meta["synthetic"] is True and meta["width"] == 100 and prov["dem"]["downsample_factor"] == 2
    assert (out / "dem16.bin").exists() and (out / "rough16.bin").exists() and meta["pack"]["err_z_m"] < 0.05 and (out / "provenance.json").exists()
    assert meta["eva"]["plans"][0]["diurnal_k"] == prov["meda"]["diurnal_k"]
