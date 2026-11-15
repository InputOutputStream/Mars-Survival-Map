"""Test on a REAL MEDA file (sol 1, CAL_ATS, downloaded by the team from the PDS on 2026-11-06)."""
import importlib.util
from pathlib import Path
p = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("am", p / "scripts" / "analyse_meda.py"); am = importlib.util.module_from_spec(spec); spec.loader.exec_module(am)

def test_real_sol1_air_temperature():
    st = am.sol_stats(am.read(p / "tests/fixtures/meda_sol0001_CAL_ATS.csv", "ATS_LOCAL_TEMP"))
    assert st["n"] > 1000
    assert 100 < st["min"] < st["max"] < 330          # plausible kelvin values at the surface of Mars
    assert all(0 <= h < 25 for h in st["hourly_mean"])
