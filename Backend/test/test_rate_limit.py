"""Per-IP rate limiter: X-Forwarded-For handling, 429 + Retry-After, buckets."""
import pytest

from model import ask as ask_mod
from model import metadata as meta_mod


@pytest.fixture(autouse=True)
def _stubs(monkeypatch):
    monkeypatch.setattr(meta_mod, "list_cases", lambda limit=20, offset=0: {"cases": []})
    monkeypatch.setattr(ask_mod, "answer", lambda *a, **k: {"answer": "x"})


def _get(client, ip="1.1.1.1", path="/cases"):
    return client.get(path, headers={"x-forwarded-for": ip})


def test_blocks_after_limit_with_retry_after(client, api, monkeypatch):
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 3)
    assert [_get(client).status_code for _ in range(3)] == [200, 200, 200]
    r = _get(client)
    assert r.status_code == 429 and r.json()["error"] == "rate_limited"
    retry = int(r.headers["Retry-After"])
    assert 1 <= retry <= api.WINDOW_S + 1


def test_limit_is_per_ip(client, api, monkeypatch):
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 1)
    assert _get(client, "1.1.1.1").status_code == 200
    assert _get(client, "1.1.1.1").status_code == 429
    assert _get(client, "2.2.2.2").status_code == 200


def test_uses_last_xff_entry_so_spoofing_fails(client, api, monkeypatch):
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 2)
    for i in range(2):
        assert _get(client, f"10.0.0.{i}, 5.5.5.5").status_code == 200
    assert _get(client, "10.0.0.99, 5.5.5.5").status_code == 429   # same real peer
    assert _get(client, "10.0.0.99, 6.6.6.6").status_code == 200


def test_client_ip_helper(api):
    from types import SimpleNamespace as NS

    def req(h, host="7.7.7.7"):
        return NS(headers=h, client=NS(host=host) if host else None)
    assert api.client_ip(req({"x-forwarded-for": "a, b , c"})) == "c"
    assert api.client_ip(req({})) == "7.7.7.7"
    assert api.client_ip(req({}, host=None)) == "unknown"


def test_llm_bucket_is_separate_and_stricter(client, api, monkeypatch):
    monkeypatch.setattr(api, "LLM_LIMIT_PER_MIN", 2)

    def post():
        return client.post("/ask", json={"query": "q"}, headers={"x-forwarded-for": "3.3.3.3"})
    assert [post().status_code for _ in range(2)] == [200, 200]
    r = post()
    assert r.status_code == 429 and "Retry-After" in r.headers
    assert _get(client, "3.3.3.3").status_code == 200           # general bucket untouched
    r = client.post("/chat_query", json={"case_id": "1", "question": "q"},
                    headers={"x-forwarded-for": "3.3.3.3"})
    assert r.status_code == 429                                  # chat shares the llm bucket


def test_health_and_options_and_static_are_not_limited(client, api, monkeypatch):
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 1)
    _get(client)                                                 # use up the only slot
    monkeypatch.setattr(api, "_db_ping", lambda: False)
    assert _get(client, path="/health").status_code == 503       # not 429
    assert client.options("/cases", headers={"Origin": "http://localhost:5173",
                          "Access-Control-Request-Method": "GET"}).status_code == 200
    assert _get(client, path="/assets/app.js").status_code == 404  # non-API GET: not limited


def test_window_expires(client, api, monkeypatch):
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 1)
    clock = [1000.0]
    monkeypatch.setattr(api.time, "monotonic", lambda: clock[0])
    assert _get(client).status_code == 200
    assert _get(client).status_code == 429
    clock[0] += api.WINDOW_S + 1
    assert _get(client).status_code == 200


# ---- strict search bucket, static buckets, IPv6, pruning, inference queue ----

def test_query_and_search_use_strict_bucket(client, api, monkeypatch):
    monkeypatch.setattr(api._engine, "search", lambda q, k=10, case_id=None: [])
    monkeypatch.setattr(api, "SEARCH_LIMIT_PER_MIN", 2)
    hdr = {"x-forwarded-for": "4.4.4.4"}
    assert client.get("/search", params={"q": "a"}, headers=hdr).status_code == 200
    assert client.post("/query", json={"query": "a"}, headers=hdr).status_code == 200
    r = client.get("/search", params={"q": "a"}, headers=hdr)
    assert r.status_code == 429 and "Retry-After" in r.headers          # /query and /search share it
    assert client.post("/query", json={"query": "a"}, headers=hdr).status_code == 429
    assert _get(client, "4.4.4.4").status_code == 200                   # other bucket untouched
    assert client.post("/ask", json={"query": "a"}, headers=hdr).status_code == 200  # llm bucket untouched


def test_search_bucket_default_is_10_per_minute(api):
    assert api.SEARCH_LIMIT_PER_MIN == 10 and api.STATIC_LIMIT_PER_MIN == 300


def test_pdf_and_static_buckets_are_limited_but_generous(client, api, monkeypatch):
    monkeypatch.setattr(api, "STATIC_LIMIT_PER_MIN", 3)
    for path in ("/supreme_court_pdfs/1.pdf", "/assets/app.js"):
        hdr = {"x-forwarded-for": "8.8.8.8"}
        codes = [client.get(path, headers=hdr).status_code for _ in range(4)]
        assert codes[:3] == [404, 404, 404] and codes[3] == 429, (path, codes)   # no such file here
    assert _get(client, "8.8.8.8").status_code == 200                    # API bucket separate


def test_ipv6_same_slash64_shares_one_bucket(client, api, monkeypatch):
    monkeypatch.setattr(api, "OTHER_LIMIT_PER_MIN", 2)
    assert _get(client, "2001:db8:1:2::1").status_code == 200
    assert _get(client, "2001:db8:1:2:aaaa:bbbb:cccc:dddd").status_code == 200
    assert _get(client, "2001:db8:1:2:ffff::9").status_code == 429       # same /64: one bucket
    assert _get(client, "2001:db8:1:3::1").status_code == 200            # next /64: new bucket


def test_normalize_ip(api):
    n = api.normalize_ip
    assert n("2001:db8:1:2:3:4:5:6") == "2001:db8:1:2::/64"
    assert n("::ffff:1.2.3.4") == "1.2.3.4" and n("1.2.3.4") == "1.2.3.4"
    assert n("not-an-ip") == "not-an-ip"


def test_spoofed_first_xff_entry_does_not_change_bucket(api):
    from types import SimpleNamespace as NS
    peer = "2001:db8:9:9:1:2:3:4"
    keys = {api.client_ip(NS(headers={"x-forwarded-for": f"{spoof}, {peer}"}, client=NS(host="10.0.0.1")))
            for spoof in ("1.1.1.1", "9.9.9.9", "::1", "2001:db8:ffff::1", "garbage")}
    assert keys == {"2001:db8:9:9::/64"}


def test_prune_runs_on_a_schedule_not_per_request(client, api, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(api.time, "monotonic", lambda: clock[0])
    for i in range(30):
        _get(client, f"5.5.5.{i}")
    assert len(api._hits) == 30
    clock[0] += api.WINDOW_S + 1                       # all 30 keys are idle now
    _get(client, "6.6.6.6")
    assert {k[0] for k in api._hits} == {"6.6.6.6"}    # swept: the schedule was due
    api._hits[("stale", "other")].append(clock[0] - 500)   # an idle key appears right after a sweep
    for _ in range(5):
        _get(client, "6.6.6.6")
    assert ("stale", "other") in api._hits             # not scanned again within the interval
    clock[0] += api.PRUNE_EVERY_S + 1
    _get(client, "6.6.6.6")
    assert ("stale", "other") not in api._hits


def test_inference_busy_returns_503_with_retry_after(client, api, monkeypatch):
    from model import retrieval as rt
    import threading
    monkeypatch.setattr(rt, "_INFER", threading.Semaphore(1))
    monkeypatch.setattr(rt, "INFER_QUEUE_TIMEOUT", 0.05)
    monkeypatch.setattr(rt, "_embed", lambda: (_ for _ in ()).throw(AssertionError("must not run")))
    rt._INFER.acquire()                                    # another request holds the only slot
    api._engine._cache.clear()
    r = client.get("/search", params={"q": "busy"})
    assert r.status_code == 503 and r.json()["error"] == "unavailable"
    assert r.headers["Retry-After"] == "1"
    rt._INFER.release()


def test_infer_slot_released_after_use_and_on_error():
    from model import retrieval as rt
    import threading
    sem = threading.Semaphore(1)
    import unittest.mock as m
    with m.patch.object(rt, "_INFER", sem):
        with rt.infer_slot():
            assert not sem.acquire(blocking=False)
        assert sem.acquire(blocking=False); sem.release()
        try:
            with rt.infer_slot():
                raise ValueError
        except ValueError:
            pass
        assert sem.acquire(blocking=False)
