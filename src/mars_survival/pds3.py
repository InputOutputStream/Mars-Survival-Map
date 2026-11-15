"""
pds3.py - PARTIAL reading (HTTP Range) of a remote PDS3 raster, without GDAL or a full download.

Target: HiRISE DTMs (DTEEC_*.IMG, ~700 MB, float32, server with `Accept-Ranges: bytes`: tested 2026-11-06).
We read the PDS3 label (ASCII text at the start of the file), then only the lines needed.
The PDS3 keyword names used are those of the standard; NO value is assumed: everything comes from the label.
If a keyword is missing, the error says so and `--inspect` prints the full label for correction.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np
import requests

UA = "MarsSurvivalMap/0.2 (NASA Space Apps 2026, Red Circle; range reads, contact via GitHub repo)"


def parse_label(text: str) -> dict:
    """"KEY = value" keywords of the label (up to END). Nested objects are flattened (last value wins,
    unless the key already exists: first value kept, which favours the IMAGE object / main projection)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.strip() == "END":
            break
        m = re.match(r"\s*(\^?[A-Z0-9_:]+)\s*=\s*(.*?)\s*$", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def _num(v: str) -> float:
    return float(re.match(r"\s*([-+0-9.eE]+)", v).group(1))


@dataclass
class Raster:
    url: str
    lines: int
    samples: int
    bits: int
    little_endian: bool
    offset: int          # byte offset of the first pixel
    px_m: float
    center_lat: float
    center_lon: float
    line_off: float      # LINE_PROJECTION_OFFSET (pixels, line of the projection centre)
    samp_off: float
    radius_m: float
    missing: float | None
    label: dict

    @property
    def dtype(self):
        return np.dtype(("<" if self.little_endian else ">") + {32: "f4", 16: "i2"}[self.bits])

    def lonlat_to_pixel(self, lat: float, lon: float) -> tuple[float, float]:
        """Equirectangular (assumption to be checked with MAP_PROJECTION_TYPE, verified in open_remote)."""
        x = math.radians(lon - self.center_lon) * self.radius_m * math.cos(math.radians(self.center_lat))
        y = math.radians(lat) * self.radius_m   # PDS3 equirectangular: y measured from the EQUATOR (CENTER_LATITUDE is only used for the cos)
        return self.line_off - y / self.px_m + 1, self.samp_off + x / self.px_m + 1   # (line, column), approx. 0-based

    def pixel_to_lonlat(self, row: float, col: float) -> tuple[float, float]:
        y = (self.line_off - (row - 1)) * self.px_m
        x = ((col - 1) - self.samp_off) * self.px_m
        return (math.degrees(y / self.radius_m),
                self.center_lon + math.degrees(x / (self.radius_m * math.cos(math.radians(self.center_lat)))))


def _get(session, url, start, end, tries: int = 6, wait: float = 2.0, exact: bool = True):
    """One Range request, with retries: the HiRISE server sometimes cuts long transfers (IncompleteRead
    observed at ~12 MB on 2026-11-06), hence blocks of ~2 MB."""
    import time
    last = None
    for k in range(1, tries + 1):
        try:
            r = session.get(url, headers={"Range": f"bytes={start}-{end}", "User-Agent": UA}, timeout=60)
            if r.status_code != 206:
                raise RuntimeError(f"the server did not answer 206 (Range) but {r.status_code}: partial reading impossible")
            if exact and len(r.content) != end - start + 1:
                raise IOError(f"truncated response: {len(r.content)} bytes instead of {end - start + 1}")
            return r.content
        except (requests.exceptions.RequestException, IOError) as e:
            last = e
            if k < tries:
                time.sleep(wait * k)
    raise last


def open_remote(url: str, session=None, head_bytes: int = 65536) -> Raster:
    s = session or requests.Session()
    head = _get(s, url, 0, head_bytes - 1, exact=False)   # file shorter than head_bytes: tolerated
    text = head.decode("ascii", errors="replace")
    lab = parse_label(text)
    need = ["RECORD_BYTES", "^IMAGE", "LINES", "LINE_SAMPLES", "SAMPLE_BITS", "MAP_SCALE",
            "CENTER_LATITUDE", "CENTER_LONGITUDE", "LINE_PROJECTION_OFFSET", "SAMPLE_PROJECTION_OFFSET"]
    miss = [k for k in need if k not in lab]
    if miss:
        raise KeyError(f"PDS3 keywords missing from the label: {miss}. Run --inspect and send the output.")
    ptype = lab.get("MAP_PROJECTION_TYPE", "").upper()
    if "EQUIRECT" not in ptype:
        raise NotImplementedError(f"projection {ptype!r} not supported (only EQUIRECTANGULAR is)")
    ptr = lab["^IMAGE"]
    rec = int(_num(ptr))
    offset = (rec - 1) * int(_num(lab["RECORD_BYTES"])) if "<BYTES>" not in ptr else rec - 1
    rad = _num(lab.get("A_AXIS_RADIUS", "3396.19")) * 1000.0   # km -> m; default = IAU equatorial radius (to be confirmed)
    stype = lab.get("SAMPLE_TYPE", "").upper()
    miss_c = lab.get("MISSING_CONSTANT")
    return Raster(url, int(_num(lab["LINES"])), int(_num(lab["LINE_SAMPLES"])), int(_num(lab["SAMPLE_BITS"])),
                  stype in ("PC_REAL", "LSB_INTEGER", "MSB_INTEGER") and stype != "MSB_INTEGER",
                  offset, _num(lab["MAP_SCALE"]), _num(lab["CENTER_LATITUDE"]), _num(lab["CENTER_LONGITUDE"]),
                  _num(lab["LINE_PROJECTION_OFFSET"]), _num(lab["SAMPLE_PROJECTION_OFFSET"]), rad,
                  None if miss_c is None else _num(miss_c.replace("16#", "")) if "16#" not in miss_c else None, lab)


def read_window(r: Raster, row0: int, row1: int, col0: int, col1: int, session=None) -> np.ndarray:
    """Window [row0,row1) x [col0,col1). One Range request per line if the window is narrow, otherwise one contiguous block."""
    s = session or requests.Session()
    row0, col0 = max(0, row0), max(0, col0)
    row1, col1 = min(r.lines, row1), min(r.samples, col1)
    if row1 <= row0 or col1 <= col0:
        raise ValueError("window outside the raster")
    isz = r.dtype.itemsize
    line_bytes = r.samples * isz
    out = np.empty((row1 - row0, col1 - col0), dtype=np.float64)
    if (col1 - col0) / r.samples > 0.25:
        step = max(1, 2_000_000 // line_bytes)        # ~2 MB per request
        for a_row in range(row0, row1, step):
            b_row = min(row1, a_row + step)
            buf = _get(s, r.url, r.offset + a_row * line_bytes, r.offset + b_row * line_bytes - 1)
            blk = np.frombuffer(buf, dtype=r.dtype).reshape(b_row - a_row, r.samples)
            out[a_row - row0:b_row - row0] = blk[:, col0:col1]
    else:
        for i, row in enumerate(range(row0, row1)):
            a = r.offset + row * line_bytes + col0 * isz
            out[i] = np.frombuffer(_get(s, r.url, a, a + (col1 - col0) * isz - 1), dtype=r.dtype)
    if r.missing is not None:
        out[np.isclose(out, r.missing)] = np.nan
    out[out < -1e30] = np.nan      # HiRISE "missing" constants (very negative float32); check MISSING_CONSTANT
    return out
