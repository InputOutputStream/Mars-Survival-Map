import pathlib

HTML = (pathlib.Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")


def test_3d_canvas_is_attached():
    """Regression: a trailing // comment once swallowed the rest of the renderer line, so the 3D canvas was never added to the page."""
    line = next(l for l in HTML.splitlines() if "new THREE.WebGLRenderer" in l)
    code = line.split("//")[0] if "//" in line.replace("http://", "").replace("https://", "") else line
    assert "host.appendChild(renderer.domElement)" in code
