# From globe to site: DTM guide → map of a Martian "town"

Goal: an area of 2 to 20 km, with slope, roughness, hazard, routes and a 3D view, built from NASA products.

## 1. Choose the site
- Browse **Mars Trek** (https://trek.nasa.gov/mars/) to find where a **HiRISE DTM** exists: coverage is
  patchy (sites of scientific interest, landing candidates). Jezero, Gale and former candidate sites are well covered.
- Note the DTM's **observation identifiers**; the orthoimage must come from the **same stereo pair** (otherwise it will not overlay).
- Fill in the record in the toolkit (`catalogue/`, rows T02, T05, T06) with `scripts/update_catalog_status.py`.

## 2. Download (sparingly, and with verification)
- Use the toolkit (`catalogue/`, `scripts/hash_files.py`); on the code side: `python -m mars_survival scrape fetch-ode FILE.jsonl --dry-run`
  prints the URLs and sizes BEFORE downloading. Downloads are resumed, verified (size) and logged
  (`data/raw/downloads.jsonl`: URL, sha256, date).
- Keep the originals untouched in `data/raw/`; work only on copies.

## 3. Convert (GDAL, or QGIS ▸ Export)
```bash
gdalinfo my_dtm.IMG                        # read CRS, pixel size, nodata, units (metres?)
gdal_translate -of GTiff my_dtm.IMG dtm.tif
gdal_translate -projwin XMIN YMAX XMAX YMIN -of AAIGrid dtm.tif site.asc   # crop + format readable without rasterio
```
To check in `gdalinfo`: (1) the elevation is really in **metres** (`scale`/`offset` of the PDS label), (2) the **pixel size** in metres
(pass it as `--px-m` if the CRS is geographic), (3) the **nodata** value (`--nodata`).

## 4. Analyse
```bash
python -m mars_survival site --dem site.asc --px-m 1 --lat 18.4 --lon 77.5 --name "My site" --route 300,300,3000,2500
python -m mars_survival serve        # http://localhost:8000/  (site)  and /globe.html
```
A 1 m/px DTM over 5 km = 25 million pixels: too heavy for the browser and slow for Python Dijkstra.
**Resample to 5–10 m/px** for the analysis (`gdal_translate -tr 5 5 -r average ...`); keep the 1 m/px for small areas of interest.

## 5. Blender
File ▸ Import ▸ Wavefront (.obj) → `web/data/site/terrain.obj` (Z up, 1 unit = 1 m, texture `texture.png`).
Alternative: subdivided plane + *Displace* modifier with `heightmap16.png`; the real amplitude is `zmax − zmin` (in `site.json`).
The layers (`slope.png`, `hazard.png`, `roughness.png`) are aligned pixel for pixel with the texture: use them as additional textures.
*(The Blender import could not be tested here; the OBJ was validated structurally: face indices, UVs, vertex count.)*

## 6. What the map does not tell you
The hazard classes are a **model** (thresholds = hypotheses). No cast shadows, energy, radio visibility, ground type
(sand, load-bearing dust) or DTM uncertainty. A lack of data is not a lack of hazard.
