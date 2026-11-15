#!/usr/bin/env python3
"""Downloads (15 MB) and describes the MCS surface temperature file, so the loader can be written against its real layout.

  pip install netCDF4        # once
  python scripts/inspect_mcs_tsurf.py

Data: Wang & Jin 2025, "Mars Climate Sounder Surface Temperatures Corrected to 03:00 and 15:00 LTST",
Zenodo, doi:10.5281/zenodo.17947556, CC BY 4.0, open access (no login). File MCS_tsurf_corrected.nc, MD5 921ebf89ba5f1ac35d89d62f83369c27.
Surface temperatures derived from NASA's MRO Mars Climate Sounder, processed by the authors. Paste the output back.
"""
import hashlib, sys
from pathlib import Path
import numpy as np
import requests

URL = "https://zenodo.org/records/17947556/files/MCS_tsurf_corrected.nc?download=1"
MD5 = "921ebf89ba5f1ac35d89d62f83369c27"
dest = Path(__file__).resolve().parents[1] / "data" / "globe" / "MCS_tsurf_corrected.nc"


def main():
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(URL, headers={"User-Agent": "mars-survival-map (NASA Space Apps 2026, Red Circle team)"}, timeout=300)
        r.raise_for_status(); dest.write_bytes(r.content)
    b = dest.read_bytes()
    print(f"{dest}  {len(b)} bytes  md5 {hashlib.md5(b).hexdigest()}  ({'matches' if hashlib.md5(b).hexdigest() == MD5 else 'DIFFERS from'} the record)")
    try:
        import netCDF4
    except ImportError:
        sys.exit("pip install netCDF4   then run again")
    ds = netCDF4.Dataset(dest)
    print("\nglobal attributes:", {k: ds.getncattr(k) for k in ds.ncattrs()})
    print("dimensions:", {k: len(v) for k, v in ds.dimensions.items()})
    for name, v in ds.variables.items():
        a = np.ma.filled(v[:].astype(float), np.nan) if v.dtype.kind in "fiu" else None
        line = f"\n{name}  dims={v.dimensions} shape={v.shape} dtype={v.dtype} attrs={ {k: v.getncattr(k) for k in v.ncattrs()} }"
        if a is not None and a.size:
            line += f"\n    min {np.nanmin(a):.4g}  max {np.nanmax(a):.4g}  nan {np.isnan(a).mean():.1%}  first values {a.ravel()[:6]}"
            u = np.unique(a.ravel()[:200000]); line += f"\n    distinct (first 200k values): {len(u)}" + (f" -> {u[:12]}" if len(u) <= 12 else "")
        print(line)


if __name__ == "__main__":
    main()
