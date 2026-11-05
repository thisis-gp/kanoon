"""Security headers, CORS, docs switch, null bytes, SPA/static handling."""
import importlib

import pytest
from fastapi.testclient import TestClient

from model import metadata as meta_mod


def test_api_json_has_headers_and_no_store(client, monkeypatch):
    monkeypatch.setattr(meta_mod, "list_cases", lambda limit=20, offset=0: {"cases": []})
    r = client.get("/cases")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert r.headers["cache-control"] == "no-store"
    csp = r.headers["content-security-policy"]
    for part in ("default-src 'self'", "script-src 'self'", "object-src 'none'", "base-uri 'self'",
                 "img-src 'self' data:", "style-src 'self' 'unsafe-inline'", "frame-src 'self'",
                 "https://identitytoolkit.googleapis.com", "https://securetoken.googleapis.com",
                 "https://firestore.googleapis.com", "https://*.firebaseapp.com"):
        assert part in csp, part


def test_headers_also_on_errors_and_429(client, api, monkeypatch):
    r = client.get("/nope/nothing")
    assert r.status_code == 404 and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 1)
    monkeypatch.setattr(meta_mod, "list_cases", lambda limit=20, offset=0: {"cases": []})
    client.get("/cases")
    r = client.get("/cases")
    assert r.status_code == 429 and r.headers["x-frame-options"] == "SAMEORIGIN"


def test_cors_credentials_off(client):
    r = client.options("/ask", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and "access-control-allow-credentials" not in r.headers


def test_dev_origins_only_outside_production(monkeypatch):
    from model import api as api_mod
    try:
        monkeypatch.setenv("ENVIRONMENT", "production")
        importlib.reload(api_mod)
        c = TestClient(api_mod.app)
        r = c.options("/ask", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        assert r.status_code == 400 and "access-control-allow-origin" not in r.headers
        ngrok = "https://tarot-remindful-candy.ngrok-free.dev"
        r = c.options("/ask", headers={"Origin": ngrok, "Access-Control-Request-Method": "POST"})
        assert r.headers["access-control-allow-origin"] == ngrok
        monkeypatch.setenv("ENVIRONMENT", "development")
        importlib.reload(api_mod)
        r = TestClient(api_mod.app).options("/ask", headers={"Origin": "http://localhost:5173",
                                                             "Access-Control-Request-Method": "POST"})
        assert r.status_code == 200
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        importlib.reload(api_mod)


def test_docs_disabled_by_default_and_enabled_by_flag(monkeypatch):
    from model import api as api_mod
    try:
        monkeypatch.delenv("ENABLE_DOCS", raising=False)
        importlib.reload(api_mod)
        c = TestClient(api_mod.app)
        assert all(c.get(p).status_code == 404 for p in ("/docs", "/redoc", "/openapi.json"))
        monkeypatch.setenv("ENABLE_DOCS", "1")
        importlib.reload(api_mod)
        c = TestClient(api_mod.app)
        assert c.get("/openapi.json").status_code == 200 and c.get("/docs").status_code == 200
    finally:
        monkeypatch.delenv("ENABLE_DOCS", raising=False)
        importlib.reload(api_mod)


def test_null_byte_paths_are_404_not_500(client):
    for path in ("/%00", "/cases/12%00", "/supreme_court_pdfs/1.pdf%00", "/assets/%00.js", "/a%00b/c"):
        r = client.get(path)
        assert r.status_code in (404, 422), (path, r.status_code)
        assert r.status_code != 500


@pytest.fixture
def served(tmp_path, monkeypatch):
    """The app with a real built-frontend directory and a PDF directory."""
    from model import api as api_mod
    static, pdfs = tmp_path / "static", tmp_path / "pdfs"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>spa</html>")
    (static / "assets" / "app-abc123.js").write_text("console.log(1)")
    (static / "favicon.txt").write_text("x")
    pdfs.mkdir()
    (pdfs / "660.pdf").write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setenv("STATIC_DIR", str(static))
    monkeypatch.setenv("PDF_DIR", str(pdfs))
    importlib.reload(api_mod)
    api_mod._hits.clear()
    yield TestClient(api_mod.app, raise_server_exceptions=False)
    monkeypatch.delenv("STATIC_DIR"); monkeypatch.delenv("PDF_DIR")
    importlib.reload(api_mod)


def test_spa_null_byte_and_traversal_are_404_or_index(served):
    assert served.get("/%00").status_code == 404
    assert served.get("/foo%00bar").status_code == 404
    assert served.get("/assets/%00").status_code == 404
    assert served.get("/supreme_court_pdfs/%00").status_code != 500
    assert served.get("/supreme_court_pdfs/660.pdf%00").status_code != 500
    r = served.get("/../../etc/passwd")
    assert r.status_code in (200, 404) and "root:" not in r.text


def test_spa_serves_index_for_routes_but_404_for_missing_assets(served):
    r = served.get("/results")
    assert r.status_code == 200 and "spa" in r.text and r.headers["cache-control"] == "no-cache"
    assert served.get("/assets/missing-hash.js").status_code == 404
    assert served.get("/favicon.txt").text == "x"


def test_hashed_assets_immutable_cache(served):
    r = served.get("/assets/app-abc123.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_pdf_has_frame_headers_without_csp(served):
    r = served.get("/supreme_court_pdfs/660.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "content-security-policy" not in r.headers
    assert "immutable" not in r.headers.get("cache-control", "")


def test_pdf_mount_is_rate_limited_generously(served):
    from model import api as api_mod
    api_mod.STATIC_LIMIT_PER_MIN = 5
    try:
        codes = [served.get("/supreme_court_pdfs/660.pdf").status_code for _ in range(6)]
    finally:
        api_mod.STATIC_LIMIT_PER_MIN = 300
    assert codes == [200] * 5 + [429]
