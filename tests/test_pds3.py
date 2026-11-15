"""Test of Range reading on a SYNTHETIC PDS3 file (test fixture only: never displayed as Martian data)."""
import http.server, threading, re
import numpy as np
from mars_survival import pds3

LABEL = """PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 400
^IMAGE = 3
OBJECT = IMAGE
  LINES = 40
  LINE_SAMPLES = 50
  SAMPLE_BITS = 32
  SAMPLE_TYPE = PC_REAL
  MISSING_CONSTANT = -3.4028226550889045e+38
END_OBJECT = IMAGE
OBJECT = IMAGE_MAP_PROJECTION
  MAP_PROJECTION_TYPE = EQUIRECTANGULAR
  MAP_SCALE = 1.0 <METERS/PIXEL>
  A_AXIS_RADIUS = 3396.19 <KM>
  CENTER_LATITUDE = 18.0 <DEG>
  CENTER_LONGITUDE = 77.0 <DEG>
  LINE_PROJECTION_OFFSET = 20.0
  SAMPLE_PROJECTION_OFFSET = 25.0
END_OBJECT = IMAGE_MAP_PROJECTION
END
"""
Z = (np.arange(40 * 50, dtype="<f4").reshape(40, 50))


def _blob():
    head = LABEL.encode().ljust(800, b" ")
    return head + Z.tobytes()


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        b = _blob(); m = re.match(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
        if not m:
            self.send_response(200); self.end_headers(); self.wfile.write(b); return
        s, e = int(m[1]), min(int(m[2]), len(b) - 1)
        self.send_response(206); self.send_header("Content-Length", str(e - s + 1)); self.end_headers()
        self.wfile.write(b[s:e + 1])


def _server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/x.IMG"


def test_label_and_window_narrow_and_wide():
    srv, url = _server()
    try:
        r = pds3.open_remote(url)
        assert (r.lines, r.samples, r.offset, r.px_m) == (40, 50, 800, 1.0)
        assert np.array_equal(pds3.read_window(r, 5, 9, 10, 20), Z[5:9, 10:20])      # narrow: row by row
        assert np.array_equal(pds3.read_window(r, 5, 9, 0, 50), Z[5:9, :])           # wide: contiguous block
    finally:
        srv.shutdown()


def test_geo_roundtrip_and_center():
    srv, url = _server()
    try:
        r = pds3.open_remote(url)
        row, col = r.lonlat_to_pixel(18.0, 77.0)
        lat, lon = r.pixel_to_lonlat(row, col)
        assert abs(lat - 18.0) < 1e-6 and abs(lon - 77.0) < 1e-6
    finally:
        srv.shutdown()


def test_server_without_range_fails_loudly():
    class N(H):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"x")
    srv = http.server.HTTPServer(("127.0.0.1", 0), N)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        import pytest
        with pytest.raises(RuntimeError):
            pds3.open_remote(f"http://127.0.0.1:{srv.server_port}/x")
    finally:
        srv.shutdown()


def test_latitude_is_from_equator():
    srv, url = _server()
    try:
        r = pds3.open_remote(url)
        lat, _ = r.pixel_to_lonlat(r.line_off + 1, r.samp_off + 1)      # pixel at the projection origin
        assert abs(lat) < 1e-9                                           # lat 0 (equator), not CENTER_LATITUDE
    finally:
        srv.shutdown()


def test_truncated_response_is_retried():
    calls = {"n": 0}
    class F(H):
        def do_GET(self):
            calls["n"] += 1
            b = _blob(); m = re.match(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
            s, e = int(m[1]), min(int(m[2]), len(b) - 1)
            self.send_response(206); self.send_header("Content-Length", str(e - s + 1)); self.end_headers()
            self.wfile.write(b[s:e + 1][: (5 if calls["n"] == 2 else None)])      # 2nd request: cut short
            if calls["n"] == 2:
                self.wfile.flush(); self.connection.close()
    srv = http.server.HTTPServer(("127.0.0.1", 0), F)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        import time; orig = time.sleep; time.sleep = lambda x: None
        r = pds3.open_remote(f"http://127.0.0.1:{srv.server_port}/x.IMG")
        assert np.array_equal(pds3.read_window(r, 2, 6, 0, 50), Z[2:6])
        assert calls["n"] >= 3
    finally:
        time.sleep = orig; srv.shutdown()
