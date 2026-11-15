#!/usr/bin/env python3
"""
scraper.py - "polite" collection of Mars data for the survival map.

Sources: NASA API (rover photos), PDS Geosciences ODE (REST), PDS API (search),
          direct download of archive files (resume + sha256).

Usage:
  python -m mars_survival scrape layers                         # useful layers + sources
  python -m mars_survival scrape ode-types                      # list ODE instruments/products
  python -m mars_survival scrape ode --ihid MGS --iid MOLA --pt MEGDR --limit 100
  python -m mars_survival scrape ode --ihid MRO --iid CRISM --pt TRDR \
         --bbox -20 20 280 320 --limit 200              # minlat maxlat westlon eastlon
  python -m mars_survival scrape pds 'lid like "urn:nasa:pds:mro*"' --limit 50
  python -m mars_survival scrape manifest curiosity
  python -m mars_survival scrape photos perseverance --sol 100 --camera NAVCAM --max-pages 2
  python -m mars_survival scrape fetch-ode data/raw/ode_MGS_MOLA_MEGDR.jsonl --ext .tif .img .lbl --max 3
  python -m mars_survival scrape download URL [--dest data/files]

Env: NASA_API_KEY (default DEMO_KEY, very limited), SCRAPER_UA, MIN_INTERVAL, MARS_DATA_DIR
Dependency: pip install requests

NB: the ODE / PDS API parameters below must be checked against the official docs
(ODE REST manual, PDS API docs): product type names vary by instrument.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = os.getenv("SCRAPER_UA", "MarsSurvivalMap/0.1 (research project; contact: YOUR_EMAIL)")
DATA = Path(os.getenv("MARS_DATA_DIR", "data"))
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL", "1.0"))  # seconds between 2 requests / host
CACHE_TTL = 7 * 24 * 3600
NASA_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")

ODE_BASE = "https://oderest.rsl.wustl.edu/live2/"
PDS_API = "https://pds.nasa.gov/api/search/1/products"
NASA_MARS = "https://api.nasa.gov/mars-photos/api/v1"

# Layers useful for the survival map -> where to look (check pt via `ode-types`)
LAYERS = {
    "elevation":   {"why": "elevation, pressure, radiation", "ode": {"ihid": "MGS", "iid": "MOLA", "pt": "MEGDR"}},
    "water_ice":   {"why": "hydrogen/water (neutrons)",       "ode": {"ihid": "ODY", "iid": "GRS"}},
    "subsurface":  {"why": "subsurface ice (radar)",          "ode": {"ihid": "MRO", "iid": "SHARAD"}},
    "thermal":     {"why": "thermal inertia, temperature",    "ode": {"ihid": "ODY", "iid": "THEMIS"}},
    "minerals":    {"why": "hydrated minerals, resources",    "ode": {"ihid": "MRO", "iid": "CRISM"}},
    "slopes_hires": {"why": "fine slopes, landing sites", "ode": {"ihid": "MRO", "iid": "HIRISE"}},
    "weather_ground": {"why": "surface weather (REMS, MEDA)", "pds_q": 'lid like "urn:nasa:pds:mars2020_meda*"'},
    "radiation":   {"why": "surface dose (Curiosity RAD)",   "pds_q": 'lid like "urn:nasa:pds:msl_rad*"'},
}


MAX_TRIES = int(os.getenv("SCRAPER_MAX_TRIES", "30"))


class Polite:
    """HTTP session: User-Agent, retries/backoff, robots.txt, rate limiting, SQLite cache."""

    def __init__(self) -> None:
        if "TON_EMAIL" in UA:
            print("[tip] set SCRAPER_UA with your e-mail (courtesy towards the NASA/PDS servers).", file=sys.stderr)
        DATA.mkdir(parents=True, exist_ok=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        retry = Retry(total=5, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), respect_retry_after_header=True)
        self.s.mount("https://", HTTPAdapter(max_retries=retry))
        self.s.mount("http://", HTTPAdapter(max_retries=retry))
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.db = sqlite3.connect(DATA / "cache.sqlite")
        self.db.execute("CREATE TABLE IF NOT EXISTS http_cache(key TEXT PRIMARY KEY, body TEXT, ts REAL)")

    # -- politeness ---------------------------------------------------------
    def _allowed(self, url: str) -> bool:
        """robots.txt read with OUR User-Agent (urllib.robotparser.read() would send Python's, often
        refused with 403 -> wrongly interpreted as "everything forbidden"). Non-200 response or network failure -> allowed."""
        u = urlparse(url)
        base = f"{u.scheme}://{u.netloc}"
        if base not in self._robots:
            rp = None
            try:
                r = self.s.get(base + "/robots.txt", timeout=15)
                if r.status_code == 200:
                    rp = urllib.robotparser.RobotFileParser()
                    rp.parse(r.text.splitlines())
            except requests.RequestException:
                rp = None
            self._robots[base] = rp
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(UA, url)

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        dt = time.time() - self._last.get(host, 0.0)
        if dt < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - dt)
        self._last[host] = time.time()

    # -- JSON with cache ---------------------------------------------------
    def get_json(self, url: str, params: dict | None = None, cache: bool = True):
        params = params or {}
        key = url + "?" + json.dumps({k: v for k, v in sorted(params.items()) if k != "api_key"})
        if cache:
            row = self.db.execute("SELECT body, ts FROM http_cache WHERE key=?", (key,)).fetchone()
            if row and time.time() - row[1] < CACHE_TTL:
                return json.loads(row[0])
        if not self._allowed(url):
            raise PermissionError(f"robots.txt forbids: {url}")
        self._wait(url)
        r = self.s.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        self.db.execute("INSERT OR REPLACE INTO http_cache VALUES(?,?,?)", (key, json.dumps(data), time.time()))
        self.db.commit()
        return data

    def head_size(self, url: str) -> str:
        """Advertised size (HEAD), to decide BEFORE downloading large files."""
        try:
            self._wait(url)
            n = self.s.head(url, timeout=30, allow_redirects=True).headers.get("Content-Length")
            return f"{int(n) / 1e6:.1f} MB" if n else "unknown size"
        except requests.RequestException as e:
            return f"HEAD failed ({e.__class__.__name__})"

    # -- download with resume --------------------------------------
    def download(self, url: str, dest_dir: str | Path) -> Path:
        """Resumable download, verified (advertised size), streamed hash, provenance log."""
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / (Path(urlparse(url).path).name or "download.bin")
        part = dest.with_name(dest.name + ".part")
        if dest.exists():
            return dest
        if not self._allowed(url):
            raise PermissionError(f"robots.txt forbids: {url}")
        last = None
        for attempt in range(1, MAX_TRIES + 1):          # frequent disconnections on large files: we resume on our own
            try:
                return self._download_once(url, dest, part)
            except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout, IOError) as e:
                last = e
                got = part.stat().st_size if part.exists() else 0
                wait = min(60, 2 ** min(attempt, 6))
                print(f"[attempt {attempt}/{MAX_TRIES}] connection dropped at {got / 1e6:.0f} MB ({e.__class__.__name__}) "
                      f"- resuming in {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise IOError(f"failed after {MAX_TRIES} attempts; the partial file is kept ({part}), rerun the command") from last

    def _download_once(self, url: str, dest: Path, part: Path) -> Path:
        pos = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={pos}-"} if pos else {}
        self._wait(url)
        with self.s.get(url, headers=headers, stream=True, timeout=60) as r:
            if r.status_code == 416:  # already complete
                os.replace(part, dest)
                return self._finish(url, dest)
            r.raise_for_status()
            resumed = r.status_code == 206
            expected = r.headers.get("Content-Length")
            with open(part, "ab" if resumed else "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        size = part.stat().st_size
        want = None if expected is None else int(expected) + (pos if resumed else 0)
        if want is not None and size != want:
            raise IOError(f"incomplete download ({size} B instead of {want})")
        os.replace(part, dest)
        return self._finish(url, dest)

    @staticmethod
    def _finish(url: str, dest: Path) -> Path:
        h = hashlib.sha256()
        with open(dest, "rb") as f:                      # streamed: the whole file is never held in memory
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        rec = {"url": url, "path": str(dest), "size_bytes": dest.stat().st_size, "sha256": h.hexdigest(),
               "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        log = DATA / "raw" / "downloads.jsonl"            # provenance log (feeds the catalogue)
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"OK {dest} sha256={rec['sha256']}")
        return dest


def write_jsonl(name: str, rows: list[dict]) -> Path:
    out = DATA / "raw" / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(rows)} rows -> {out}")
    return out


# --------------------------------------------------------------------------- sources
def ode_types(p: Polite) -> None:
    data = p.get_json(ODE_BASE, {"query": "iipt", "target": "mars", "output": "JSON"})
    print(json.dumps(data, indent=2)[:6000])


def ode_products(p: Polite, ihid: str, iid: str, pt: str | None, bbox, limit: int, page: int = 500) -> list[dict]:
    params = {"query": "product", "results": "copmf", "output": "JSON", "target": "mars",
              "ihid": ihid, "iid": iid}
    if pt:
        params["pt"] = pt
    if bbox:
        params.update(minlat=bbox[0], maxlat=bbox[1], westernlon=bbox[2], easternlon=bbox[3], loc="o")
    rows: list[dict] = []
    while len(rows) < limit:
        params.update(limit=min(page, limit - len(rows)), offset=len(rows))
        res = p.get_json(ODE_BASE, params).get("ODEResults", {})
        if res.get("Status") not in (None, "Success"):
            print("ODE:", res.get("Status"), res.get("Error", ""), file=sys.stderr)
            break
        prods = res.get("Products", {}).get("Product", [])
        prods = [prods] if isinstance(prods, dict) else prods
        if not prods:
            break
        rows.extend(prods)
        if len(prods) < params["limit"]:
            break
    return rows


def pds_search(p: Polite, q: str, limit: int) -> list[dict]:
    data = p.get_json(PDS_API, {"q": q, "limit": limit})
    return data.get("data", [])


def rover_manifest(p: Polite, rover: str) -> dict:
    return p.get_json(f"{NASA_MARS}/manifests/{rover}", {"api_key": NASA_KEY})


def rover_photos(p: Polite, rover: str, sol: int, camera: str | None, max_pages: int) -> list[dict]:
    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        params = {"sol": sol, "page": page, "api_key": NASA_KEY}
        if camera:
            params["camera"] = camera
        photos = p.get_json(f"{NASA_MARS}/rovers/{rover}/photos", params).get("photos", [])
        if not photos:
            break
        rows.extend(photos)
    return rows


def iter_ode_file_urls(jsonl_path, exts):
    """Extracts file URLs from a JSONL produced by `ode` (Product_files structure to be verified)."""
    exts = tuple(e.lower() for e in exts)
    for line in Path(jsonl_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        files = json.loads(line).get("Product_files", {}).get("Product_file", [])
        files = [files] if isinstance(files, dict) else files
        for f in files:
            url = f.get("URL") or ""
            if url.lower().endswith(exts):
                yield url


# --------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="mars-survival scrape", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("layers")
    sub.add_parser("ode-types")
    o = sub.add_parser("ode")
    o.add_argument("--ihid", required=True)
    o.add_argument("--iid", required=True)
    o.add_argument("--pt")
    o.add_argument("--bbox", nargs=4, type=float, metavar=("MINLAT", "MAXLAT", "WLON", "ELON"))
    o.add_argument("--limit", type=int, default=100)
    d = sub.add_parser("pds")
    d.add_argument("q")
    d.add_argument("--limit", type=int, default=50)
    m = sub.add_parser("manifest")
    m.add_argument("rover")
    ph = sub.add_parser("photos")
    ph.add_argument("rover")
    ph.add_argument("--sol", type=int, required=True)
    ph.add_argument("--camera")
    ph.add_argument("--max-pages", type=int, default=3)
    fo = sub.add_parser("fetch-ode")
    fo.add_argument("jsonl")
    fo.add_argument("--ext", nargs="+", default=[".tif", ".img", ".lbl"])
    fo.add_argument("--max", type=int, default=3)
    fo.add_argument("--dest", default=str(DATA / "files"))
    fo.add_argument("--dry-run", action="store_true", help="list the URLs (and sizes via HEAD) without downloading")
    dl = sub.add_parser("download")
    dl.add_argument("url")
    dl.add_argument("--dest", default=str(DATA / "files"))
    a = ap.parse_args(argv)

    if a.cmd == "layers":
        print(json.dumps(LAYERS, indent=2, ensure_ascii=False))
        return
    p = Polite()
    if a.cmd == "ode-types":
        ode_types(p)
    elif a.cmd == "ode":
        write_jsonl(f"ode_{a.ihid}_{a.iid}_{a.pt or 'all'}", ode_products(p, a.ihid, a.iid, a.pt, a.bbox, a.limit))
    elif a.cmd == "pds":
        write_jsonl("pds_search", pds_search(p, a.q, a.limit))
    elif a.cmd == "manifest":
        out = DATA / "raw" / f"manifest_{a.rover}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rover_manifest(p, a.rover), indent=2))
        print(out)
    elif a.cmd == "photos":
        write_jsonl(f"photos_{a.rover}_sol{a.sol}", rover_photos(p, a.rover, a.sol, a.camera, a.max_pages))
    elif a.cmd == "fetch-ode":
        for i, url in enumerate(iter_ode_file_urls(a.jsonl, a.ext)):
            if i >= a.max:
                break
            if a.dry_run:
                print(url, p.head_size(url))
            else:
                p.download(url, a.dest)
    elif a.cmd == "download":
        p.download(a.url, a.dest)


if __name__ == "__main__":
    main()
