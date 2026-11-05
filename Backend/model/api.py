"""
AILSE API (Slice 4) — clean FastAPI app on the new Postgres/ParadeDB stack.

Replaces the Qdrant + per-case-FAISS main.py. Everything routes through:
  retrieval.RetrievalEngine  (hybrid search, case_id scoping)
  ask.answer                 (grounded Perplexity answers + citations)
  citations.CitationGraph    (cites / cited-by)

Run:  uvicorn model.api:app --host 0.0.0.0 --port 8000
"""
import os
import re
import json
import time
import hashlib
import hmac
import asyncio
import ipaddress
import logging
import threading
from contextlib import closing
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from model.retrieval import RetrievalEngine
from model.citations import CitationGraph
from model import ask as ask_mod
from model import metadata as meta_mod
from model import history as history_mod
from model import llm_gateway
from model import retrieval as retrieval_mod
from model.errors import Busy

# Interactive docs and the OpenAPI schema are off unless ENABLE_DOCS=1 (public servers should not publish them).
_DOCS_ON = os.getenv("ENABLE_DOCS", "") == "1"
app = FastAPI(title="AILSE Legal Search API", version="2.0.0",
              description="Perplexity-style legal search over Indian Supreme Court cases",
              docs_url="/docs" if _DOCS_ON else None,
              redoc_url="/redoc" if _DOCS_ON else None,
              openapi_url="/openapi.json" if _DOCS_ON else None)

# ---- per-IP rate limiting (in-memory, single worker) ----
# Buckets: llm (/ask, /chat_query), search (/query, /search: embedding + cross-encoder rerank, so
# strict), pdf and static (generous, files only), other (cheap DB reads).
LLM_PATHS = {"/ask", "/chat_query"}
SEARCH_PATHS = {"/query", "/search"}
PDF_PREFIX = "/supreme_court_pdfs"
# Optional public bucket for judgment PDFs; when set, pdfUrl points there and the CSP allows its origin.
PDF_BASE_URL = os.getenv("PDF_BASE_URL", "").strip().rstrip("/")
_PDF_ORIGIN = "/".join(PDF_BASE_URL.split("/")[:3]) if PDF_BASE_URL.startswith("https://") else ""
LLM_LIMIT_PER_MIN = int(os.getenv("RATE_LLM_PER_MIN", "10"))
SEARCH_LIMIT_PER_MIN = int(os.getenv("RATE_SEARCH_PER_MIN", "10"))
OTHER_LIMIT_PER_MIN = int(os.getenv("RATE_OTHER_PER_MIN", "60"))
STATIC_LIMIT_PER_MIN = int(os.getenv("RATE_STATIC_PER_MIN", "300"))
WINDOW_S = 60
PRUNE_EVERY_S = 60
_hits = defaultdict(deque)          # (ip, bucket) -> request timestamps
_hits_lock = threading.Lock()
_last_prune = [0.0]


def normalize_ip(raw: str) -> str:
    """Bucket key for an address: IPv4 as is, IPv4-mapped IPv6 as IPv4, other IPv6 collapsed to its /64
    (one subscriber usually owns a whole /64, so rotating the low 64 bits must not mint new buckets).
    Anything that is not an IP address is returned unchanged."""
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return raw
    if addr.version == 4:
        return str(addr)
    if addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(ipaddress.ip_network((addr, 64), strict=False))


def client_ip(request: Request) -> str:
    """Behind ngrok: the proxy appends the real peer to X-Forwarded-For, so trust only the
    LAST entry (earlier entries are client-supplied and spoofable). Fall back to the socket peer."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return normalize_ip(xff.split(",")[-1].strip())
    return normalize_ip(request.client.host) if request.client else "unknown"


def _bucket(method: str, path: str):
    """(bucket name, per-minute limit) for a request, or None when it is not limited."""
    if method == "OPTIONS" or path == "/health":
        return None
    if path in LLM_PATHS:
        return "llm", LLM_LIMIT_PER_MIN
    if path in SEARCH_PATHS:
        return "search", SEARCH_LIMIT_PER_MIN
    if path == PDF_PREFIX or path.startswith(PDF_PREFIX + "/"):
        return "pdf", STATIC_LIMIT_PER_MIN
    if method in ("GET", "HEAD") and not _is_api_path(path):
        return "static", STATIC_LIMIT_PER_MIN
    return "other", OTHER_LIMIT_PER_MIN


def _prune(now: float) -> None:
    """Drop idle keys; runs at most once per PRUNE_EVERY_S (caller holds the lock)."""
    if now - _last_prune[0] < PRUNE_EVERY_S:
        return
    _last_prune[0] = now
    for k in [k for k, v in _hits.items() if not v or now - v[-1] > WINDOW_S]:
        del _hits[k]


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    rule = _bucket(request.method, request.url.path)
    if rule is None:
        return await call_next(request)
    bucket, limit = rule
    key, now = (client_ip(request), bucket), time.monotonic()
    with _hits_lock:
        _prune(now)
        q = _hits[key]
        while q and now - q[0] > WINDOW_S:
            q.popleft()
        if len(q) >= limit:
            retry = max(1, int(WINDOW_S - (now - q[0])) + 1)
            return _error(429, "rate limit exceeded", headers={"Retry-After": str(retry)})
        q.append(now)
    return await call_next(request)


_API_PREFIXES = ("/ask", "/chat_query", "/query", "/search", "/suggestions", "/cases", "/health")
def _is_api_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _API_PREFIXES)


# ---- consistent JSON errors: {"detail": <message string>, "error": <code>} ----
# `detail` stays a plain string because the frontend shows it directly.
_ERROR_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed",
                422: "validation_error", 429: "rate_limited", 503: "unavailable"}


def _error(status: int, message: str, headers=None, **extra) -> JSONResponse:
    body = {"detail": message, "error": _ERROR_CODES.get(status, "http_error"), **extra}
    return JSONResponse(body, status_code=status, headers=headers)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, str(exc.detail), headers=getattr(exc, "headers", None))


@app.exception_handler(Busy)
async def _busy_error(request: Request, exc: Busy):
    """A bounded resource is full: tell the client to retry instead of queueing the request."""
    return _error(503, "server busy, please retry shortly",
                  headers={"Retry-After": str(exc.retry_after)})


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    fields = [{"field": ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path")),
               "message": e["msg"]} for e in exc.errors()]
    summary = "; ".join(f"{f['field']}: {f['message']}" if f["field"] else f["message"]
                        for f in fields[:3])
    return _error(422, f"invalid request: {summary}", fields=fields)


# ---- structured request log: method, path, status, duration, hashed client IP.
# Never logs the query string, request body, headers, or keys. ----
log = logging.getLogger("kanoon.access")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False
_IP_SALT = os.getenv("IP_HASH_SALT") or os.getenv("LOG_IP_SALT", "kanoon")   # set IP_HASH_SALT in production


CLIENT_HASH_LEN = 32      # stored hashes (searches.ip_hash, per-client LLM caps); logs use 12


def ip_hash(ip: str, length: int = 12) -> str:
    """Salted hash of a client address; the raw address is never stored or logged."""
    return hashlib.sha256(f"{_IP_SALT}:{ip}".encode()).hexdigest()[:length]


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log.info(json.dumps({
            "event": "request", "method": request.method, "path": request.url.path[:200],
            "status": status, "ms": round((time.perf_counter() - start) * 1000, 1),
            "ip": ip_hash(client_ip(request))}))


# ---- security headers ----
# CSP matches the React build served from this origin: own scripts and styles only (Tailwind output is a
# file; style 'unsafe-inline' is for React inline style attributes), Firebase Auth/Firestore endpoints,
# the Firebase auth iframe, Google Fonts (CSS + font files) and Google profile photos.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://apis.google.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "img-src 'self' data: https://lh3.googleusercontent.com",
    "connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com "
    f"https://firestore.googleapis.com https://*.firebaseapp.com https://*.googleapis.com {_PDF_ORIGIN}".strip(),
    f"frame-src 'self' https://*.firebaseapp.com {_PDF_ORIGIN}".strip(),
    "frame-ancestors 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",                      # the case page embeds the PDF in an iframe
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
ASSET_CACHE = "public, max-age=31536000, immutable"       # /assets/* files are content-hashed by Vite


@app.middleware("http")
async def security_headers(request: Request, call_next):
    path = request.url.path
    if "\x00" in path:                                    # %00 in a path: never reaches the filesystem
        response = _error(404, "not found")
    else:
        response = await call_next(request)
    h = response.headers
    for k, v in SECURITY_HEADERS.items():
        h.setdefault(k, v)
    ctype = h.get("content-type", "")
    if not ctype.startswith("application/pdf"):          # the browser PDF viewer breaks under a strict CSP
        h.setdefault("Content-Security-Policy", CSP)
    if "cache-control" not in h:
        if ctype.startswith("application/json"):
            h["Cache-Control"] = "no-store"
        elif path.startswith("/assets/") and response.status_code == 200:
            h["Cache-Control"] = ASSET_CACHE
        elif ctype.startswith("text/html"):
            h["Cache-Control"] = "no-cache"
    return response


# CORS is added LAST so it is the outermost layer: 429s and errors still carry CORS headers.
# Allowed browser origins: ngrok front door + local fallback, plus extras from CORS_ALLOWED_ORIGINS
# (comma-separated, exact origins, no wildcard), e.g. the Vercel domain.
_PRODUCTION = os.getenv("ENVIRONMENT", "").strip().lower() == "production"
_DEV_ORIGINS = ["http://127.0.0.1:8080", "http://localhost:3000", "http://localhost:5173"]
_origins = ["https://tarot-remindful-candy.ngrok-free.dev"] + ([] if _PRODUCTION else _DEV_ORIGINS)
_origins += [o.strip().rstrip("/") for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
             if o.strip() and o.strip() != "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,          # no cookies are used; the API is called with plain fetch
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning"],
)


def _llm_call(request: Request, fn, *a, **k):
    """Run an LLM-backed answer for this client. Daily caps -> 429, LLM slots full -> 503 + Retry-After
    (Busy handler), provider failure -> 503 (no provider detail)."""
    token = llm_gateway.CLIENT.set(ip_hash(client_ip(request), CLIENT_HASH_LEN))
    try:
        return fn(*a, **k)
    except llm_gateway.ClientCapReached:
        raise HTTPException(429, "daily limit for your connection reached, try again tomorrow",
                            headers={"Retry-After": "3600"})
    except llm_gateway.DailyCapReached:
        raise HTTPException(429, "daily LLM quota reached, try again tomorrow",
                            headers={"Retry-After": "3600"})
    except RuntimeError as e:
        print(f"[llm] unavailable: {type(e).__name__}")   # no provider text in logs/responses
        raise HTTPException(503, "answer service unavailable")
    finally:
        llm_gateway.CLIENT.reset(token)


_engine = RetrievalEngine()
_graph = CitationGraph()


@app.on_event("startup")
def _warm_models():
    """Pre-load embed + rerank models so the first query isn't slow."""
    try:
        history_mod.init_db()
    except Exception as e:
        print(f"[history] init failed: {type(e).__name__}")
    history_mod.start_retention()          # purge old rows now, then once a day
    from model.retrieval import _embed, _rerank
    try:
        _embed(); _rerank()
        print("[warm] models loaded")
    except Exception as e:
        print(f"[warm] failed (non-fatal): {type(e).__name__}")


# ---- input limits ----
MAX_QUERY_CHARS = 1000
MAX_ASK_K = 20
MAX_QUERY_TOP_K = 50
CASE_ID_PATTERN = r"^[A-Za-z0-9_.-]{1,64}$"
_CASE_ID_RE = re.compile(CASE_ID_PATTERN)
CaseIdPath = Path(..., pattern=CASE_ID_PATTERN, description="Case id, e.g. 660")


class AskRequest(BaseModel):
    query: str = Field(..., max_length=MAX_QUERY_CHARS)
    k: int = Field(6, ge=1, le=MAX_ASK_K)


class ChatRequest(BaseModel):
    case_id: str = Field(..., max_length=64)
    question: str = Field(..., max_length=MAX_QUERY_CHARS)

    @field_validator("case_id", mode="before")
    @classmethod
    def _case_id_text(cls, v):
        if isinstance(v, bool) or not isinstance(v, (str, int)):
            raise ValueError("case_id must be a string or integer")
        v = str(v).strip()
        if not _CASE_ID_RE.match(v):
            raise ValueError("case_id may only contain letters, digits, '_', '.', '-' (max 64)")
        return v


class QueryRequest(BaseModel):
    query: str = Field(..., max_length=MAX_QUERY_CHARS)
    top_k: int = Field(5, ge=1, le=MAX_QUERY_TOP_K)


def _version() -> str:
    """Build id: GIT_COMMIT env (set at image build) or a VERSION file next to the package."""
    v = os.getenv("GIT_COMMIT", "").strip()
    if not v:
        try:
            with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "VERSION"), encoding="utf-8") as f:
                v = f.read().strip()
        except OSError:
            v = ""
    return v[:40] or "unknown"


HEALTH_DB_CHECK = os.getenv("HEALTH_DB_CHECK", "1") != "0"   # 0 = never touch the DB from /health
HEALTH_DB_TTL_S = 10
HEALTH_DB_TIMEOUT_S = 3
_health_db = {"at": -1e9, "ok": True}
_health_lock = None


def _db_ping() -> bool:
    """One tiny query on a short-lived direct connection (not the request pool)."""
    import psycopg2
    try:
        with closing(psycopg2.connect(getattr(_engine, "dsn", retrieval_mod.DSN),
                                      connect_timeout=2)) as c, c.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as e:
        log.warning(json.dumps({"event": "health_db_down", "error": type(e).__name__}))
        return False


async def _db_ok() -> bool:
    """Cached DB reachability, checked off the request threadpool so /health never queues behind
    search traffic. At most one check per HEALTH_DB_TTL_S, whatever the request rate."""
    global _health_lock
    if _health_lock is None:
        _health_lock = asyncio.Lock()
    async with _health_lock:
        if time.monotonic() - _health_db["at"] > HEALTH_DB_TTL_S:
            try:
                ok = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, _db_ping),
                                            HEALTH_DB_TIMEOUT_S)
            except Exception:
                ok = False
            _health_db.update(at=time.monotonic(), ok=ok)
        return _health_db["ok"]


def _health_token_ok(request: Request) -> bool:
    expected = os.getenv("HEALTH_TOKEN", "")
    given = request.headers.get("x-health-token", "")
    return bool(expected) and hmac.compare_digest(expected.encode(), given.encode())


def _health_detail() -> dict:
    """Operator view, only behind X-Health-Token. Never includes secrets, DSNs, or error text."""
    body = {
        "version": f"{app.version}+{_version()}",
        "chunks": None,
        "models": {"embedding": retrieval_mod.EMBED_MODEL,
                   "embedding_loaded": retrieval_mod._embedder is not None,
                   "reranker": retrieval_mod.RERANK_MODEL,
                   "reranker_loaded": retrieval_mod._reranker is not None},
        "caches": {"search": len(_engine._cache), "answer": len(ask_mod._answer_cache)},
        "llm_calls_today": llm_gateway.calls_today(),
        "llm_daily_cap": llm_gateway.daily_cap(),
    }
    try:
        with closing(_engine._conn()) as c, c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks;")
            body["chunks"] = cur.fetchone()[0]
    except Exception as e:
        log.warning(json.dumps({"event": "health_chunks_failed", "error": type(e).__name__}))
    return body


@app.get("/health")
async def health(request: Request):
    """Public: only status and db_ok. Cheap, answered on the event loop (not the search threadpool).
    With a matching X-Health-Token header (env HEALTH_TOKEN) it adds the operator detail."""
    ok = await _db_ok() if HEALTH_DB_CHECK else None
    healthy = ok is not False
    body = {"status": "healthy" if healthy else "unhealthy", "db_ok": ok}
    if _health_token_ok(request):
        body.update(await asyncio.get_running_loop().run_in_executor(None, _health_detail))
    return JSONResponse(body, status_code=200 if healthy else 503)


@app.post("/ask")
def ask(req: AskRequest, request: Request):
    """Global Perplexity-style answer across ALL cases, with inline citations."""
    if not req.query.strip():
        raise HTTPException(400, "query required")
    history_mod.log(req.query, "ask", ip_hash(client_ip(request), CLIENT_HASH_LEN))
    return _llm_call(request, ask_mod.answer, req.query, k=req.k)


@app.post("/chat_query")
def chat_query(req: ChatRequest, request: Request):
    """Per-case chat — scoped to ONE judgment (case_id filter)."""
    if not req.question.strip():
        raise HTTPException(400, "question required")
    return _llm_call(request, ask_mod.answer, req.question, case_id=req.case_id)


@app.post("/query")
def query(req: QueryRequest, request: Request):
    """Legacy-compatible search: returns unique case cards with metadata."""
    history_mod.log(req.query, "search", ip_hash(client_ip(request), CLIENT_HASH_LEN))
    hits = _engine.search(req.query, k=max(req.top_k * 6, 30))
    seen, results = set(), []
    for h in hits:
        cid = h["case_id"]
        if cid in seen:
            continue
        seen.add(cid)
        m = meta_mod.get(cid)
        # if the summary is missing, show the actual matching passage instead
        if not m.get("summary") or m["summary"] == "Not available":
            m["summary"] = h["text"].strip()[:240] + "…"
        results.append({**m, "source": f"{cid}.txt"})
        if len(results) >= req.top_k:
            break
    return {"query": req.query, "total_results": len(results), "results": results}


@app.get("/search")
def search(q: str = Query(..., min_length=1, max_length=MAX_QUERY_CHARS),
           k: int = Query(10, ge=1, le=50),
           case_id: str = Query(None, pattern=CASE_ID_PATTERN)):
    """Raw ranked chunks (no LLM) — for debugging / case cards."""
    return {"query": q, "results": _engine.search(q, k=k, case_id=case_id)}


@app.get("/suggestions")
def get_suggestions(limit: int = Query(6, ge=1, le=12)):
    """Most-popular recent queries for the home page (from search history)."""
    return {"suggestions": history_mod.suggestions(limit=limit)}


@app.get("/cases")
def list_cases(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Paginated case list (metadata)."""
    return meta_mod.list_cases(limit=limit, offset=offset)


@app.get("/cases/{case_id}")
def case_detail(case_id: str = CaseIdPath):
    """Case metadata (title/judges/date/summary) + PDF path. 404 for unknown ids."""
    data = meta_mod.find(case_id)
    if data is None:
        raise HTTPException(404, "case not found")
    data["pdfUrl"] = f"{PDF_BASE_URL or PDF_PREFIX}/{case_id}.pdf"
    return data


@app.get("/cases/{case_id}/cites")
def cites(case_id: str = CaseIdPath):
    return {"case_id": case_id, "cites": _graph.cites(case_id)}


@app.get("/cases/{case_id}/cited-by")
def cited_by(case_id: str = CaseIdPath):
    return {"case_id": case_id, "cited_by": _graph.cited_by(case_id)}


# ---- built React frontend (same origin) + case PDFs ----
STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")
PDF_DIR = os.getenv("PDF_DIR", "/app/supreme_court_pdfs")
if os.path.isdir(PDF_DIR):
    app.mount("/supreme_court_pdfs", StaticFiles(directory=PDF_DIR), name="pdfs")
if os.path.isdir(STATIC_DIR):
    _root = os.path.realpath(STATIC_DIR)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Serve a built file if it exists, else index.html (client-side routing)."""
        if "\x00" in full_path:
            raise HTTPException(404, "not found")
        try:
            candidate = os.path.realpath(os.path.join(_root, full_path))
            is_file = os.path.isfile(candidate)
        except (ValueError, OSError):                      # bad path bytes or length: just not found
            raise HTTPException(404, "not found")
        if full_path and is_file and candidate.startswith(_root + os.sep):
            return FileResponse(candidate)
        if full_path.startswith("assets/"):                # a missing hashed file must not become index.html
            raise HTTPException(404, "not found")
        return FileResponse(os.path.join(_root, "index.html"))
