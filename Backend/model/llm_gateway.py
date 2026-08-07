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
import urllib.request
import urllib.error

# Throttle: min gap between LLM calls so bulk jobs (metadata backfill) don't trip
# provider rate limits / Cloudflare IP blocks. ~24 req/min.
_MIN_GAP = float(os.getenv("LLM_MIN_GAP", "2.5"))
_last_call = [0.0]
def _throttle():
    dt = time.time() - _last_call[0]
    if dt < _MIN_GAP:
        time.sleep(_MIN_GAP - dt)
    _last_call[0] = time.time()

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
                      {"model": "llama-3.1-8b-instant", "messages": msgs,
                       "temperature": temperature},
                      {"Authorization": f"Bearer {key}"})
            return d["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429, 503):
                time.sleep(1.5 * (attempt + 1))
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
               "temperature": temperature},
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


def generate(prompt, system=None, temperature=0.2):
    """Return (text, provider_name). Tries providers in order; raises if all fail."""
    errors = []
    for name, fn in PROVIDERS:
        try:
            _throttle()
            return fn(system, prompt, temperature), name
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError("all LLM providers failed -> " + " | ".join(errors))


if __name__ == "__main__":
    txt, who = generate("Reply with exactly the word: OK")
    print(f"[{who}] {txt}")
