import http.server
import json
import threading

import pytest

from mars_survival import scraper

DATA = bytes(range(256)) * 4096          # 1 MB


class _H(http.server.BaseHTTPRequestHandler):
    hits = {"json": 0}

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/robots.txt":
            if getattr(self.server, "robots", None):
                body = self.server.robots.encode(); self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            else:
                self.send_response(404); self.end_headers()
        elif self.path.startswith("/api"):
            _H.hits["json"] += 1
            body = json.dumps({"data": [1, 2, 3]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        elif self.path == "/file.bin":
            start = 0
            rng = self.headers.get("Range")
            if rng:
                start = int(rng.split("=")[1].split("-")[0])
            body = DATA[start:]
            self.send_response(206 if rng else 200)
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        elif self.path == "/flaky.bin":                      # cuts the connection every other time, mid-file
            _H.hits["flaky"] = _H.hits.get("flaky", 0) + 1
            start = int(self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0]) if self.headers.get("Range") else 0
            body = DATA[start:]
            self.send_response(206 if start else 200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body if _H.hits["flaky"] % 2 == 0 else body[:len(body) // 2])
        elif self.path == "/truncated.bin":
            self.send_response(200); self.send_header("Content-Length", str(len(DATA))); self.end_headers(); self.wfile.write(DATA[:1000])
        else:
            self.send_response(404); self.end_headers()


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "DATA", tmp_path)
    monkeypatch.setattr(scraper, "MIN_INTERVAL", 0.0)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    srv.robots = None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_json_is_cached(server):
    _, base = server
    _H.hits["json"] = 0
    p = scraper.Polite()
    assert p.get_json(base + "/api", {"q": "x", "api_key": "SECRET"}) == {"data": [1, 2, 3]}
    assert p.get_json(base + "/api", {"q": "x", "api_key": "OTHER"}) == {"data": [1, 2, 3]}   # API key excluded from the cache key
    assert _H.hits["json"] == 1


def test_download_hash_log_and_resume(server, tmp_path):
    _, base = server
    p = scraper.Polite()
    dest_dir = tmp_path / "files"
    dest_dir.mkdir()
    (dest_dir / "file.bin.part").write_bytes(DATA[:300_000])                     # resuming a partial download
    out = p.download(base + "/file.bin", dest_dir)
    assert out.read_bytes() == DATA
    rec = json.loads((tmp_path / "raw" / "downloads.jsonl").read_text().splitlines()[-1])
    import hashlib
    assert rec["sha256"] == hashlib.sha256(DATA).hexdigest() and rec["size_bytes"] == len(DATA)


def test_flaky_connection_is_retried_and_resumed(server, tmp_path, monkeypatch):
    _, base = server
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)
    _H.hits["flaky"] = 0
    out = scraper.Polite().download(base + "/flaky.bin", tmp_path / "f")
    assert out.read_bytes() == DATA and _H.hits["flaky"] >= 2


def test_truncated_download_is_rejected_and_resumable(server, tmp_path, monkeypatch):
    _, base = server
    monkeypatch.setattr(scraper, "MAX_TRIES", 2)
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)
    p = scraper.Polite()
    with pytest.raises(Exception):
        p.download(base + "/truncated.bin", tmp_path / "f")
    assert not (tmp_path / "f" / "truncated.bin").exists()          # never presented as complete


def test_robots_disallow_is_respected_and_404_allows(server, tmp_path):
    srv, base = server
    srv.robots = "User-agent: *\nDisallow: /file.bin\n"
    p = scraper.Polite()
    with pytest.raises(PermissionError):
        p.download(base + "/file.bin", tmp_path / "f")
    srv.robots = None
    assert scraper.Polite().download(base + "/file.bin", tmp_path / "g").exists()
