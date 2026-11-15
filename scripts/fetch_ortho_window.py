#!/usr/bin/env python3
"""Photo tier: crops a window of the HiRISE orthoimage (real photograph, up to 0.25 m/px) to match a BUILT site, and writes
<site-dir>/photo.jpg + photo.json. The web map then offers a 'Photo' layer. It is a picture, not elevation: not used for routes.

  python scripts/fetch_ortho_window.py URL --inspect                       # prints size, resolution, bounds, CRS: CHECK the resolution
  python scripts/fetch_ortho_window.py URL --site-dir web/data/sites/jezero-1m

URL is read with GDAL range requests (only the window is transferred). Candidates (UA HiRISE, page https://www.uahirise.org/dtm/ESP_023524_1985):
  .../ESP_023524_1985_ESP_023379_1985/ESP_023524_1985_RED_A_01_ORTHO.JP2   (766 MB)    .../ESP_023524_1985_RED_C_01_ORTHO.JP2   (60 MB)
The page does not state their resolution: run --inspect first. Needs rasterio with the JP2 (OpenJPEG) driver; if it is missing, convert with gdal_translate.
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("--inspect", action="store_true")
ap.add_argument("--site-dir", default=str(ROOT / "web/data/site")); ap.add_argument("--max-px", type=int, default=4096)
ap.add_argument("--quality", type=int, default=82)
a = ap.parse_args()
import os
for k, v in {"GDAL_HTTP_MAX_RETRY": "8", "GDAL_HTTP_RETRY_DELAY": "2", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".JP2,.jp2"}.items(): os.environ.setdefault(k, v)
import rasterio
if a.inspect:
    with rasterio.open(a.url) as ds:
        print("size", ds.width, "x", ds.height, "| pixel size", ds.res, "| bounds", tuple(ds.bounds), "| dtype", ds.dtypes[0], "| nodata", ds.nodata)
        print(ds.crs.to_wkt() if ds.crs else "no CRS")
    sys.exit()
from PIL import Image
from mars_survival.photo import crop_photo
site = Path(a.site_dir); prov = json.loads((site / "provenance.json").read_text()); sj = json.loads((site / "site.json").read_text())
d = prov["dem"]; f = d["downsample_factor"]; shp = d["window_shape_native"]
ext = ((shp[1] // f) * f * d["native_px_m"], (shp[0] // f) * f * d["native_px_m"])          # exactly the extent of the built site
img, px, box = crop_photo(a.url, sj["center_lat"], sj["center_lon"], tuple(shp), d["native_px_m"], ext, a.max_px)
Image.fromarray(img).save(site / "photo.jpg", quality=a.quality, optimize=True)
(site / "photo.json").write_text(json.dumps({"file": "photo.jpg", "px_m": round(px, 3), "source_url": a.url, "width_px": img.shape[1], "height_px": img.shape[0],
    "note": "HiRISE orthoimage, contrast-stretched (1-99 percentile). Picture only: not used for slope, hazard or routes. Check alignment with the hillshade."}, indent=1))
print(f"photo {img.shape[1]}x{img.shape[0]} at {px:.2f} m/px -> {site/'photo.jpg'} ({(site/'photo.jpg').stat().st_size/1e6:.1f} MB)")
