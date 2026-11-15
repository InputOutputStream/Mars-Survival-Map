#!/usr/bin/env python3
"""Downloads ONE year of the MCS column dust climatology (55 MB) and describes it, so the loader can be written against
its real layout.

  python scripts/inspect_dust.py            # default: Mars Year 29 kriged daily maps (complete coverage, 3 x 3 degrees)
  python scripts/inspect_dust.py --file dustscenario_MY29_v2-0.nc

Data: Montabone et al. 2015 (Icarus 251:65-95, doi:10.1016/j.icarus.2014.12.034) and Montabone et al. 2020
(JGR Planets, doi:10.1029/2019JE006111), "Mars Climate Database dust climatology", LMD / Open University / SSI.
Column dust optical depth at 9.3 micron (absorption) normalised to 610 Pa, built from NASA's MRO Mars Climate Sounder
(and earlier TES/THEMIS) observations. Open, no login. Licence CC BY-SA 3.0 (credit, and share derivatives alike).
Source page: https://www-mars.lmd.jussieu.fr/mars/dust_climatology/    Paste the output back.
"""
import argparse, sys
from pathlib import Path
import numpy as np
import requests

BASE = "https://www-mars.lmd.jussieu.fr/mars/dust_climatology/dataset_v2/"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--file", default="dustscenario_MY29_v2-0.nc")
    a = ap.parse_args()
    dest = Path(__file__).resolve().parents[1] / "data" / "globe" / a.file
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print("downloading", BASE + a.file, "(about 55 MB)")
        with requests.get(BASE + a.file, stream=True, timeout=300, headers={"User-Agent": "mars-survival-map (NASA Space Apps 2026, Red Circle team)"}) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20): f.write(chunk)
            if "content-length" in r.headers and tmp.stat().st_size != int(r.headers["content-length"]):
                sys.exit(f"truncated download ({tmp.stat().st_size} of {r.headers['content-length']} bytes): run again")
            tmp.rename(dest)
    try:
        import netCDF4
    except ImportError:
        sys.exit("pip install netCDF4   then run again")
    ds = netCDF4.Dataset(dest)
    print(dest, dest.stat().st_size, "bytes")
    print("\nglobal attributes:", {k: str(ds.getncattr(k))[:300] for k in ds.ncattrs()})
    print("dimensions:", {k: len(v) for k, v in ds.dimensions.items()})
    for name, v in ds.variables.items():
        line = f"\n{name}  dims={v.dimensions} shape={v.shape} dtype={v.dtype} attrs={ {k: str(v.getncattr(k))[:200] for k in v.ncattrs()} }"
        if v.dtype.kind in "fiu" and v.size:
            x = np.ma.filled(v[:].astype(float), np.nan)
            line += f"\n    min {np.nanmin(x):.4g}  max {np.nanmax(x):.4g}  mean {np.nanmean(x):.4g}  nan {np.isnan(x).mean():.1%}"
            if x.ndim == 1: line += f"  first {x[:6]}  last {x[-3:]}"
        print(line)


if __name__ == "__main__":
    main()
