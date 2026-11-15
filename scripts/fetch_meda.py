#!/usr/bin/env python3
"""Downloads calibrated MEDA files (Mars 2020, Jezero) from the PDS Atmospheres node, per sol.

Structure observed in a browser on 2026-11-06:
  BASE/data_calibrated_env/sol_0000_0089/sol_0001/WE__0001___..._CAL_PS_..._P02.CSV   (PS=pressure, ATS=air temperature,
  TIRS=ground/sky IR, RHS=humidity, RDS=radiation/dust, ENG=engineering)
The sol groups have varying widths (0000_0089, 0090_0179, 0180_0299, then 120 sols): we read the listings.

  python scripts/fetch_meda.py --inspect 100                  # downloads sol 100, prints the header and 3 lines of PS/ATS
  python scripts/fetch_meda.py --sols 1 1800 --every 20 --kinds PS ATS --out data/meda
"""
import argparse, re, sys, time
from pathlib import Path
import requests

BASE = "https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/data_calibrated_env/"
UA = "MarsSurvivalMap/0.2 (NASA Space Apps 2026, Red Circle)"
S = requests.Session(); S.headers["User-Agent"] = UA


def get(url, tries=6):
    """GET with retries (the server sometimes closes the connection: RemoteDisconnected seen on 2026-11-06)."""
    for k in range(1, tries + 1):
        try:
            r = S.get(url, timeout=120); r.raise_for_status(); return r
        except requests.exceptions.RequestException as e:
            if getattr(getattr(e, "response", None), "status_code", None) == 404 or k == tries: raise      # a 404 is final: do not retry
            time.sleep(3 * k)


def links(url):
    r = get(url)
    return re.findall(r'href="([^"?/][^"]*)"', r.text)


def group_dir(sol, groups):
    for g in groups:
        m = re.fullmatch(r"sol_(\d{4})_(\d{4})/", g)
        if m and int(m[1]) <= sol <= int(m[2]):
            return g
    raise LookupError(f"no group for sol {sol}")


def fetch_sol(sol, kinds, out, groups):
    d = f"{BASE}{group_dir(sol, groups)}sol_{sol:04d}/"
    got = []
    for name in links(d):
        if name.upper().endswith((".CSV", ".XML")) and any(f"_CAL_{k}_" in name for k in kinds):
            dest = out / f"sol_{sol:04d}_{name.split('_CAL_')[1].split('_')[0]}{Path(name).suffix.lower()}"
            if not dest.exists():
                dest.write_bytes(get(d + name).content); time.sleep(1.0)
            got.append(dest)
    return got


def fetch_sol_near(sol, kinds, out, groups, spread=3):
    """Some sol folders are not on the server (404, e.g. sol 391 on 2026-11-10). Try the closest sols instead (+1, -1, +2, -2 ...) and
    say which one was used: one sol more or less barely changes a mean temperature, but the file name keeps the real sol."""
    last = None
    for d in [0] + [x for k in range(1, spread + 1) for x in (k, -k)]:
        try:
            got = fetch_sol(sol + d, kinds, out, groups)
        except (requests.exceptions.RequestException, LookupError) as e:
            last = e; continue
        if got:
            return sol + d, got
    raise last or LookupError(f"no data near sol {sol}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", type=int); ap.add_argument("--sols", type=int, nargs=2)
    ap.add_argument("--every", type=int, default=20); ap.add_argument("--kinds", nargs="+", default=["PS", "ATS"])
    ap.add_argument("--out", default="data/meda")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    groups = links(BASE)
    if a.inspect is not None:
        for f in fetch_sol(a.inspect, a.kinds, out, groups):
            print("==", f.name); print("".join(f.read_text().splitlines(True)[:4]))
        sys.exit()
    for sol in range(a.sols[0], a.sols[1] + 1, a.every):
        try:
            used, got = fetch_sol_near(sol, a.kinds, out, groups)
            print(sol, f"(not on the server, used sol {used})" if used != sol else "", [p.name for p in got])
        except Exception as e: print(sol, "failed:", e)
