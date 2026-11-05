"""
LLM gateway (Slice 2) — one interface over multiple FREE providers with
priority-ordered fallback. Try provider 1; on error/rate-limit, fall through.

No SDK deps — plain urllib. Keys read from Backend/.env (NVIDIA_API_KEY,
GROQ_API_KEY, OPENROUTER_API_KEY). Cloudflare blocks the default urllib UA on
some providers, so we send a browser UA. Order: NVIDIA -> Groq -> OpenRouter.

Add more providers by appending to PROVIDERS.
"""
import os
import json
import time
import threading
import contextvars
import urllib.request
import urllib.error

from model.errors import Busy

# Throttle: min gap between LLM calls so bulk jobs (metadata backfill) don't trip
# provider rate limits / Cloudflare IP blocks. ~24 req/min. Slots are reserved under a lock and the
# sleep happens outside it, so concurrent callers queue in order without holding the lock.
_MIN_GAP = float(os.getenv("LLM_MIN_GAP", "2.5"))
_next_slot = [0.0]
_throttle_lock = threading.Lock()


def _throttle():
    with _throttle_lock:
        now = time.monotonic()
        start = max(now, _next_slot[0])
        _next_slot[0] = start + _MIN_GAP
    wait = start - now
    if wait <= 0:
        return
    left = _remaining()
    if left is not None and wait >= left:
        raise TimeoutError("LLM deadline would pass while waiting for the throttle")
    time.sleep(wait)


# Per-request deadline across providers and retries, and a hard cap on concurrent LLM calls.
LLM_DEADLINE_S = float(os.getenv("LLM_DEADLINE", "30"))
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "3"))
# Groq retires models without notice (llama-3.1-8b-instant went away): the model is configurable.
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
MAX_TOKENS = 700                                  # answer length cap for Groq and OpenRouter
_llm_slots = threading.BoundedSemaphore(LLM_CONCURRENCY)
_deadline = contextvars.ContextVar("llm_deadline", default=None)
# Who is asking (hashed client id), set by the API per request; None for internal jobs such as backfill.
CLIENT = contextvars.ContextVar("llm_client", default=None)


def _remaining():
    """Seconds left on this request's deadline, or None when no deadline is active."""
    d = _deadline.get()
    return None if d is None else d - time.monotonic()


_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

def _load_env(name):
    try:
        for line in open(_ENV, encoding="utf-8"):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return os.getenv(name, "")

def _post(url, body, headers, timeout=45):
    left = _remaining()
    if left is not None:
        if left <= 0:
            raise TimeoutError("LLM deadline reached")
        timeout = min(timeout, left)
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _groq(system, prompt, temperature):
    key = _load_env("GROQ_API_KEY")
    if not key:
        raise RuntimeError("no GROQ_API_KEY")
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    last = None
    for attempt in range(4):          # Groq's Cloudflare 403 is intermittent — retry
        try:
            d = _post("https://api.groq.com/openai/v1/chat/completions",
                      {"model": GROQ_MODEL, "messages": msgs,
                       "temperature": temperature, "max_tokens": MAX_TOKENS},
                      {"Authorization": f"Bearer {key}"})
            return d["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429, 503):
                pause, left = 1.5 * (attempt + 1), _remaining()
                if left is not None and pause >= left:
                    raise TimeoutError("LLM deadline reached")
                time.sleep(pause)
                continue
            raise
    raise last


def _openrouter(system, prompt, temperature):
    key = _load_env("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("no OPENROUTER_API_KEY")
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    d = _post("https://openrouter.ai/api/v1/chat/completions",
              {"model": "meta-llama/llama-3.3-70b-instruct:free", "messages": msgs,
               "temperature": temperature, "max_tokens": MAX_TOKENS},
              {"Authorization": f"Bearer {key}"})
    return d["choices"][0]["message"]["content"].strip()


def _nvidia(system, prompt, temperature):
    key = _load_env("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("no NVIDIA_API_KEY")
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    d = _post("https://integrate.api.nvidia.com/v1/chat/completions",
              {"model": "meta/llama-3.1-8b-instruct", "messages": msgs,
               "temperature": temperature, "max_tokens": 1024},
              {"Authorization": f"Bearer {key}"})
    return d["choices"][0]["message"]["content"].strip()


# priority order: first healthy provider wins; falls through on failure.
# Keys in Backend/.env: NVIDIA_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY.
PROVIDERS = [("nvidia", _nvidia), ("groq", _groq), ("openrouter", _openrouter)]


class DailyCapReached(RuntimeError):
    pass


class ClientCapReached(DailyCapReached):
    """This client used its own daily share (LLM_DAILY_PER_IP)."""


_DAILY_CAP = int(os.getenv("LLM_DAILY_CAP", "300"))            # total LLM calls per UTC day
_PER_CLIENT_CAP = int(os.getenv("LLM_DAILY_PER_IP", "20"))     # calls per client per UTC day
_RESERVE = int(os.getenv("LLM_DAILY_RESERVE", "30"))           # last N global calls kept for light users
_RESERVE_PER_CLIENT = int(os.getenv("LLM_RESERVE_PER_IP", "3"))  # who counts as a light user
_day = [time.strftime("%Y-%m-%d", time.gmtime()), 0]
_by_client = {}
_count_lock = threading.Lock()


def _count_call(client=None):
    """Count one request against the caps, atomically (the check and the increment share a lock).
    Global cap = _DAILY_CAP. Per-client cap = _PER_CLIENT_CAP. The last _RESERVE global calls are only
    available to clients that have used fewer than _RESERVE_PER_CLIENT calls today, so one heavy
    client cannot leave everybody else with nothing. client=None (internal jobs) skips per-client rules."""
    with _count_lock:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if _day[0] != today:
            _day[0], _day[1] = today, 0
            _by_client.clear()
        if _day[1] >= _DAILY_CAP:
            raise DailyCapReached(f"daily cap of {_DAILY_CAP} LLM calls reached")
        if client is not None:
            used = _by_client.get(client, 0)
            if used >= _PER_CLIENT_CAP:
                raise ClientCapReached(f"per-client cap of {_PER_CLIENT_CAP} LLM calls reached")
            if _day[1] >= _DAILY_CAP - _RESERVE and used >= _RESERVE_PER_CLIENT:
                raise DailyCapReached("remaining LLM calls are reserved for new users")
            _by_client[client] = used + 1
        _day[1] += 1


def configured_providers():
    """Names of providers that have a key set (never the keys themselves)."""
    env_names = {"nvidia": "NVIDIA_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
    return [n for n, _ in PROVIDERS if _load_env(env_names.get(n, "")) ]


def calls_today():
    """LLM provider calls counted so far in the current UTC day."""
    return _day[1] if _day[0] == time.strftime("%Y-%m-%d", time.gmtime()) else 0


def daily_cap():
    return _DAILY_CAP


def generate(prompt, system=None, temperature=0.2):
    """Return (text, provider_name). Tries providers in order; raises if all fail.
    Raises Busy when LLM_CONCURRENCY calls are already running (no queueing), DailyCapReached when a
    cap is hit, and RuntimeError if every provider fails or LLM_DEADLINE seconds pass."""
    if not _llm_slots.acquire(blocking=False):
        raise Busy("LLM busy", retry_after=5)
    token = None
    try:
        _count_call(CLIENT.get())
        token = _deadline.set(time.monotonic() + LLM_DEADLINE_S)
        errors = []
        for name, fn in PROVIDERS:
            if _remaining() <= 0:
                errors.append("deadline: LLM_DEADLINE reached")
                break
            try:
                _throttle()
                return fn(system, prompt, temperature), name
            except Exception as e:
                errors.append(f"{name}: {e}")
        raise RuntimeError("all LLM providers failed -> " + " | ".join(errors))
    finally:
        if token is not None:
            _deadline.reset(token)
        _llm_slots.release()


if __name__ == "__main__":
    txt, who = generate("Reply with exactly the word: OK")
    print(f"[{who}] {txt}")
