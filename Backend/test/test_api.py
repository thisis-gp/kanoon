"""API behaviour: validation, 404, error shape, /health, CORS, access log. No DB, no network."""
import io
import json
import logging

from model import ask as ask_mod
from model import llm_gateway
from model import metadata as meta_mod
from conftest import FakeEngine

CARD = {"id": "660", "title": "A vs B", "judges": "X", "date": "01-01-2020", "summary": "s"}


def _assert_error(r, status, code):
    assert r.status_code == status, r.text
    body = r.json()
    assert isinstance(body["detail"], str) and body["error"] == code, body


def test_unknown_case_is_404(client, monkeypatch):
    monkeypatch.setattr(meta_mod, "find", lambda cid: None)
    _assert_error(client.get("/cases/99999"), 404, "not_found")


def test_known_case_is_200_with_pdf_url(client, monkeypatch):
    monkeypatch.setattr(meta_mod, "find", lambda cid: dict(CARD))
    r = client.get("/cases/660")
    assert r.status_code == 200 and r.json()["pdfUrl"] == "/supreme_court_pdfs/660.pdf"


def test_bad_case_id_path_is_422(client):
    for bad in ("bad%20id", "a%24b", "x" * 65):
        _assert_error(client.get(f"/cases/{bad}"), 422, "validation_error")
        _assert_error(client.get(f"/cases/{bad}/cited-by"), 422, "validation_error")


def test_unknown_route_is_json_404(client):
    _assert_error(client.get("/nope/nothing"), 404, "not_found")


def test_ask_validation(client, monkeypatch):
    monkeypatch.setattr(ask_mod, "answer", lambda q, **k: {"answer": "ok"})
    _assert_error(client.post("/ask", json={"query": "   "}), 400, "bad_request")
    _assert_error(client.post("/ask", json={}), 422, "validation_error")
    _assert_error(client.post("/ask", json={"query": "x" * 1001}), 422, "validation_error")
    _assert_error(client.post("/ask", json={"query": "q", "k": 0}), 422, "validation_error")
    _assert_error(client.post("/ask", json={"query": "q", "k": 21}), 422, "validation_error")
    assert client.post("/ask", json={"query": "q", "k": 20}).status_code == 200
    assert client.post("/ask", json={"query": "x" * 1000}).status_code == 200


def test_validation_error_lists_fields(client):
    body = client.post("/ask", json={"query": "q", "k": 0}).json()
    assert body["fields"][0]["field"] == "k"


def test_chat_case_id_type_rules(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(ask_mod, "answer", lambda q, case_id=None, **k: seen.update(c=case_id) or {})
    assert client.post("/chat_query", json={"case_id": 660, "question": "q"}).status_code == 200
    assert seen["c"] == "660"
    assert client.post("/chat_query", json={"case_id": " 12 ", "question": "q"}).status_code == 200
    assert seen["c"] == "12"
    for bad in ("../etc", "a b", "", [1], {"a": 1}, True, None):
        _assert_error(client.post("/chat_query", json={"case_id": bad, "question": "q"}),
                      422, "validation_error")
    _assert_error(client.post("/chat_query", json={"case_id": "1", "question": " "}), 400, "bad_request")


def test_search_and_query_bounds(client, monkeypatch):
    from model import api as api_mod
    monkeypatch.setattr(api_mod._engine, "search", lambda q, k=10, case_id=None: [])
    assert client.get("/search", params={"q": "tax"}).status_code == 200
    _assert_error(client.get("/search", params={"q": ""}), 422, "validation_error")
    _assert_error(client.get("/search", params={"q": "x" * 1001}), 422, "validation_error")
    _assert_error(client.get("/search", params={"q": "a", "k": 51}), 422, "validation_error")
    _assert_error(client.get("/search", params={"q": "a", "k": 0}), 422, "validation_error")
    _assert_error(client.get("/search", params={"q": "a", "case_id": "a b"}), 422, "validation_error")
    _assert_error(client.post("/query", json={"query": "a", "top_k": 0}), 422, "validation_error")
    _assert_error(client.post("/query", json={"query": "a", "top_k": 51}), 422, "validation_error")


def test_llm_failure_mapping(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret provider text sk-123")
    monkeypatch.setattr(ask_mod, "answer", boom)
    r = client.post("/ask", json={"query": "q"})
    _assert_error(r, 503, "unavailable")
    assert "sk-123" not in r.text and "secret" not in r.text

    def capped(*a, **k):
        raise llm_gateway.DailyCapReached("cap")
    monkeypatch.setattr(ask_mod, "answer", capped)
    r = client.post("/ask", json={"query": "q"})
    _assert_error(r, 429, "rate_limited")
    assert r.headers["Retry-After"] == "3600"


def test_health_public_is_minimal(client, api, monkeypatch):
    monkeypatch.setenv("HEALTH_TOKEN", "s3cret")
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "healthy", "db_ok": True}


def test_health_does_not_touch_pool_or_db_engine(client, api, monkeypatch):
    class Boom:
        _cache = {}

        def _conn(self):
            raise AssertionError("public /health must not use the request pool")
    monkeypatch.setattr(api, "_engine", Boom())
    assert client.get("/health").json() == {"status": "healthy", "db_ok": True}


def test_health_db_down_is_503_without_error_text(client, api, monkeypatch):
    monkeypatch.setattr(api, "_db_ping", lambda: False)
    r = client.get("/health")
    assert r.status_code == 503 and r.json() == {"status": "unhealthy", "db_ok": False}


def test_health_db_check_is_cached(client, api, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "_db_ping", lambda: calls.append(1) or True)
    for _ in range(5):
        client.get("/health")
    assert len(calls) == 1


def test_health_db_check_can_be_disabled(client, api, monkeypatch):
    monkeypatch.setattr(api, "HEALTH_DB_CHECK", False)
    monkeypatch.setattr(api, "_db_ping", lambda: (_ for _ in ()).throw(AssertionError("no DB")))
    assert client.get("/health").json() == {"status": "healthy", "db_ok": None}


def test_health_detail_needs_the_token(client, api, monkeypatch):
    eng = FakeEngine(lambda sql, p: [(46281,)])
    monkeypatch.setattr(api, "_engine", eng)
    monkeypatch.setenv("GIT_COMMIT", "abc1234")
    monkeypatch.setenv("HEALTH_TOKEN", "s3cret")
    for headers in ({}, {"X-Health-Token": "wrong"}, {"X-Health-Token": ""}):
        assert set(client.get("/health", headers=headers).json()) == {"status", "db_ok"}
    body = client.get("/health", headers={"X-Health-Token": "s3cret"}).json()
    assert body["status"] == "healthy" and body["db_ok"] is True and body["chunks"] == 46281
    assert body["version"].endswith("+abc1234")
    assert set(body["models"]) == {"embedding", "embedding_loaded", "reranker", "reranker_loaded"}
    assert set(body["caches"]) == {"search", "answer"}
    assert body["llm_daily_cap"] == llm_gateway.daily_cap()
    assert "postgresql" not in json.dumps(body)


def test_health_detail_disabled_when_no_token_configured(client, monkeypatch):
    monkeypatch.delenv("HEALTH_TOKEN", raising=False)
    assert set(client.get("/health", headers={"X-Health-Token": ""}).json()) == {"status", "db_ok"}


def test_health_token_compare_is_constant_time(monkeypatch):
    import inspect
    from model import api as api_mod
    assert "compare_digest" in inspect.getsource(api_mod._health_token_ok)


def test_cors_allow_and_deny(client):
    ok = "https://tarot-remindful-candy.ngrok-free.dev"
    r = client.options("/ask", headers={"Origin": ok, "Access-Control-Request-Method": "POST",
                                        "Access-Control-Request-Headers": "content-type,ngrok-skip-browser-warning"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == ok
    r = client.options("/ask", headers={"Origin": "https://evil.example",
                                        "Access-Control-Request-Method": "POST"})
    assert r.status_code == 400 and "access-control-allow-origin" not in r.headers
    r = client.get("/suggestions", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_headers_on_429(client, api, monkeypatch):
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 1)
    monkeypatch.setattr(meta_mod, "list_cases", lambda limit=20, offset=0: {"cases": []})
    origin = "http://localhost:5173"
    client.get("/cases")
    r = client.get("/cases", headers={"Origin": origin})
    assert r.status_code == 429 and r.headers["access-control-allow-origin"] == origin


def test_access_log_has_no_query_text(client, api, monkeypatch):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    api.log.addHandler(handler)
    monkeypatch.setattr(api._engine, "search", lambda q, k=10, case_id=None: [])
    try:
        client.get("/search", params={"q": "my secret question"},
                   headers={"x-forwarded-for": "9.9.9.9", "authorization": "Bearer sk-abc"})
    finally:
        api.log.removeHandler(handler)
    line = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert line["method"] == "GET" and line["path"] == "/search" and line["status"] == 200
    assert line["ms"] >= 0 and line["ip"] == api.ip_hash("9.9.9.9") and len(line["ip"]) == 12
    assert "secret" not in buf.getvalue() and "sk-abc" not in buf.getvalue()
    assert "9.9.9.9" not in buf.getvalue()


def test_client_cap_and_busy_mapping(client, monkeypatch):
    from model.errors import Busy

    def per_client(*a, **k):
        raise llm_gateway.ClientCapReached("x")
    monkeypatch.setattr(ask_mod, "answer", per_client)
    r = client.post("/ask", json={"query": "q"})
    _assert_error(r, 429, "rate_limited")
    assert "connection" in r.json()["detail"] and r.headers["Retry-After"] == "3600"

    def busy(*a, **k):
        raise Busy("LLM busy", retry_after=7)
    monkeypatch.setattr(ask_mod, "answer", busy)
    r = client.post("/ask", json={"query": "q"})
    _assert_error(r, 503, "unavailable")
    assert r.headers["Retry-After"] == "7"


def test_gateway_sees_hashed_client_not_raw_ip(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(ask_mod, "answer", lambda q, **k: seen.update(c=llm_gateway.CLIENT.get()) or {})
    client.post("/ask", json={"query": "q"}, headers={"x-forwarded-for": "9.9.9.9"})
    from model import api as api_mod
    assert seen["c"] == api_mod.ip_hash("9.9.9.9", 32) and "9.9.9.9" not in seen["c"]
    assert llm_gateway.CLIENT.get() is None                    # context restored after the request


def test_pdf_url_uses_bucket_when_configured(client, monkeypatch):
    from model import api as api_mod
    base = "https://objectstorage.example.com/n/ns/b/pdfs/o"
    monkeypatch.setattr(api_mod, "PDF_BASE_URL", base)
    monkeypatch.setattr(meta_mod, "find", lambda cid: dict(CARD))
    assert client.get("/cases/660").json()["pdfUrl"] == f"{base}/660.pdf"
