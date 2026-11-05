"""LLM gateway: provider fallthrough order and daily cap, with fake providers (no network)."""
import threading
import time

import pytest

from model import llm_gateway as gw


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(gw, "_throttle", lambda: None)
    monkeypatch.setattr(gw, "_DAILY_CAP", 100)
    monkeypatch.setattr(gw, "_day", [time.strftime("%Y-%m-%d", time.gmtime()), 0])
    monkeypatch.setattr(gw, "_by_client", {})
    monkeypatch.setattr(gw, "_PER_CLIENT_CAP", 20)
    monkeypatch.setattr(gw, "_RESERVE", 30)


def _provider(name, calls, result=None, error=None):
    def fn(system, prompt, temperature):
        calls.append(name)
        if error:
            raise error
        return result
    return (name, fn)


def test_first_healthy_provider_wins(monkeypatch):
    calls = []
    monkeypatch.setattr(gw, "PROVIDERS", [_provider("a", calls, "A"), _provider("b", calls, "B")])
    assert gw.generate("hi") == ("A", "a")
    assert calls == ["a"]


def test_falls_through_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr(gw, "PROVIDERS", [
        _provider("nvidia", calls, error=RuntimeError("no NVIDIA_API_KEY")),
        _provider("groq", calls, error=OSError("403")),
        _provider("openrouter", calls, "OK"),
    ])
    assert gw.generate("hi") == ("OK", "openrouter")
    assert calls == ["nvidia", "groq", "openrouter"]


def test_all_fail_raises_runtime_error_naming_providers(monkeypatch):
    calls = []
    monkeypatch.setattr(gw, "PROVIDERS", [
        _provider("a", calls, error=RuntimeError("x")), _provider("b", calls, error=ValueError("y"))])
    with pytest.raises(RuntimeError) as e:
        gw.generate("hi")
    assert "a: x" in str(e.value) and "b: y" in str(e.value)
    assert not isinstance(e.value, gw.DailyCapReached)


def test_default_provider_order():
    assert [n for n, _ in gw.PROVIDERS] == ["nvidia", "groq", "openrouter"]


def test_no_keys_means_all_providers_fail_without_network(monkeypatch):
    for name in ("NVIDIA_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(gw, "_ENV", "/nonexistent/.env")
    def no_net(*a, **k):
        raise AssertionError("network must not be touched without keys")
    monkeypatch.setattr(gw, "_post", no_net)
    with pytest.raises(RuntimeError) as e:
        gw.generate("hi")
    assert "no NVIDIA_API_KEY" in str(e.value)


def test_daily_cap_counts_requests_not_provider_attempts(monkeypatch):
    calls = []
    monkeypatch.setattr(gw, "_DAILY_CAP", 2)
    monkeypatch.setattr(gw, "PROVIDERS", [
        _provider("a", calls, error=RuntimeError("x")), _provider("b", calls, "B")])
    gw.generate("1"); gw.generate("2")
    assert gw.calls_today() == 2 and calls == ["a", "b", "a", "b"]
    with pytest.raises(gw.DailyCapReached):
        gw.generate("3")
    assert calls == ["a", "b", "a", "b"]          # providers not called once capped
    assert gw.daily_cap() == 2


def test_daily_cap_resets_on_new_day(monkeypatch):
    monkeypatch.setattr(gw, "_DAILY_CAP", 1)
    monkeypatch.setattr(gw, "PROVIDERS", [_provider("a", [], "A")])
    gw.generate("1")
    with pytest.raises(gw.DailyCapReached):
        gw.generate("2")
    gw._day[0] = "2000-01-01"                      # pretend the stored day is old
    assert gw.calls_today() == 0
    assert gw.generate("3") == ("A", "a")


# ---- per-client cap, reserve, locking ----

def test_per_client_daily_cap(monkeypatch):
    monkeypatch.setattr(gw, "_PER_CLIENT_CAP", 3)
    monkeypatch.setattr(gw, "PROVIDERS", [_provider("a", [], "A")])
    tok = gw.CLIENT.set("ip-1")
    try:
        for _ in range(3):
            gw.generate("q")
        with pytest.raises(gw.ClientCapReached):
            gw.generate("q")
        assert isinstance(gw.ClientCapReached("x"), gw.DailyCapReached)   # API maps both to 429
        gw.CLIENT.set("ip-2")
        assert gw.generate("q") == ("A", "a")                              # others unaffected
    finally:
        gw.CLIENT.reset(tok)
    assert gw.calls_today() == 4


def test_default_limits():
    assert (gw._PER_CLIENT_CAP, gw._RESERVE, gw.LLM_DEADLINE_S, gw.LLM_CONCURRENCY) == (20, 30, 30.0, 3)


def test_reserve_keeps_last_calls_for_new_users(monkeypatch):
    monkeypatch.setattr(gw, "_DAILY_CAP", 10)
    monkeypatch.setattr(gw, "_RESERVE", 4)
    monkeypatch.setattr(gw, "_PER_CLIENT_CAP", 50)
    monkeypatch.setattr(gw, "_RESERVE_PER_CLIENT", 2)
    monkeypatch.setattr(gw, "PROVIDERS", [_provider("a", [], "A")])
    tok = gw.CLIENT.set("heavy")
    try:
        for _ in range(6):                                   # heavy client drains the open part
            gw.generate("q")
        with pytest.raises(gw.DailyCapReached):              # reserved part is closed to it
            gw.generate("q")
        for who in ("new-1", "new-2"):                       # light users still get answers
            gw.CLIENT.set(who)
            assert gw.generate("q") == ("A", "a")
        gw.CLIENT.set("new-1")
        assert gw.generate("q") == ("A", "a")                # 2nd call is still within the light-user share
        with pytest.raises(gw.DailyCapReached):
            gw.generate("q")                                  # ... the 3rd is not
        gw.CLIENT.set("new-3")
        assert gw.generate("q") == ("A", "a")                # reserve exhausted by now: 10th call
        with pytest.raises(gw.DailyCapReached):
            gw.generate("q")                                  # hard global cap
    finally:
        gw.CLIENT.reset(tok)
    assert gw.calls_today() == 10


def test_count_call_cannot_overshoot_under_threads(monkeypatch):
    monkeypatch.setattr(gw, "_DAILY_CAP", 50)
    monkeypatch.setattr(gw, "_RESERVE", 0)
    monkeypatch.setattr(gw, "_PER_CLIENT_CAP", 1000)
    ok, capped = [], []

    def work(i):
        for _ in range(20):
            try:
                gw._count_call(f"c{i}")
                ok.append(1)
            except gw.DailyCapReached:
                capped.append(1)
    ts = [threading.Thread(target=work, args=(i,)) for i in range(16)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(ok) == 50 and gw.calls_today() == 50 and len(capped) == 16 * 20 - 50


def test_throttle_reserves_distinct_slots_under_lock(monkeypatch):
    monkeypatch.undo()                                       # use the real _throttle
    monkeypatch.setattr(gw, "_MIN_GAP", 0.05)
    monkeypatch.setattr(gw, "_next_slot", [0.0])
    sleeps = []
    monkeypatch.setattr(gw.time, "sleep", lambda d: sleeps.append(d))
    for _ in range(4):
        gw._throttle()
    assert len(sleeps) == 3 and sleeps == sorted(sleeps)     # each caller got a later slot


# ---- deadline and concurrency ----

def test_deadline_stops_provider_chain(monkeypatch):
    monkeypatch.setattr(gw, "LLM_DEADLINE_S", 0.05)
    calls = []

    def slow(system, prompt, t):
        calls.append("slow"); time.sleep(0.1); raise OSError("timeout")
    monkeypatch.setattr(gw, "PROVIDERS", [("slow", slow), _provider("never", calls, "N")])
    with pytest.raises(RuntimeError) as e:
        gw.generate("q")
    assert calls == ["slow"] and "deadline" in str(e.value)


def test_post_timeout_is_capped_by_deadline(monkeypatch):
    seen = {}

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"{}"
    monkeypatch.setattr(gw.urllib.request, "urlopen", lambda req, timeout: seen.update(t=timeout) or R())
    tok = gw._deadline.set(time.monotonic() + 2.0)
    try:
        gw._post("http://x", {}, {}, timeout=45)
        assert seen["t"] <= 2.0
        gw._deadline.set(time.monotonic() - 1)
        with pytest.raises(TimeoutError):
            gw._post("http://x", {}, {}, timeout=45)
    finally:
        gw._deadline.reset(tok)


def test_groq_retry_sleep_respects_deadline(monkeypatch):
    import urllib.error
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(gw, "_ENV", "/nonexistent/.env")
    n = []

    def post(*a, **k):
        n.append(1)
        raise urllib.error.HTTPError("u", 429, "x", {}, None)
    monkeypatch.setattr(gw, "_post", post)
    monkeypatch.setattr(gw.time, "sleep", lambda d: pytest.fail("must not sleep past the deadline"))
    tok = gw._deadline.set(time.monotonic() + 0.5)
    try:
        with pytest.raises(TimeoutError):
            gw._groq(None, "p", 0.2)
    finally:
        gw._deadline.reset(tok)
    assert len(n) == 1


def test_concurrency_cap_returns_busy_not_queue(monkeypatch):
    from model.errors import Busy
    started, release = threading.Event(), threading.Event()

    def blocking(system, prompt, t):
        started.set(); release.wait(2); return "A"
    monkeypatch.setattr(gw, "PROVIDERS", [("a", blocking)])
    monkeypatch.setattr(gw, "_llm_slots", threading.BoundedSemaphore(1))
    t = threading.Thread(target=gw.generate, args=("q",))
    t.start(); assert started.wait(2)
    before = gw.calls_today()
    with pytest.raises(Busy):
        gw.generate("q2")                                    # fails immediately, does not wait
    assert gw.calls_today() == before                        # a busy rejection burns no quota
    release.set(); t.join()
    assert gw.generate("q3") == ("A", "a")                   # slot is free again


def test_slot_released_when_cap_hit(monkeypatch):
    monkeypatch.setattr(gw, "_DAILY_CAP", 0)
    monkeypatch.setattr(gw, "_llm_slots", threading.BoundedSemaphore(1))
    for _ in range(3):
        with pytest.raises(gw.DailyCapReached):
            gw.generate("q")


def test_max_tokens_set_for_groq_and_openrouter(monkeypatch):
    bodies = []
    monkeypatch.setattr(gw, "_post", lambda url, body, h, timeout=45:
                        bodies.append(body) or {"choices": [{"message": {"content": " ok "}}]})
    monkeypatch.setenv("GROQ_API_KEY", "k"); monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(gw, "_ENV", "/nonexistent/.env")
    assert gw._groq(None, "p", 0.2) == "ok" and gw._openrouter("s", "p", 0.2) == "ok"
    assert [b["max_tokens"] for b in bodies] == [700, 700]
