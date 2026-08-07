"""
AILSE API (Slice 4) — clean FastAPI app on the new Postgres/ParadeDB stack.

Replaces the Qdrant + per-case-FAISS main.py. Everything routes through:
  retrieval.RetrievalEngine  (hybrid search, case_id scoping)
  ask.answer                 (grounded Perplexity answers + citations)
  citations.CitationGraph    (cites / cited-by)

Run:  uvicorn model.api:app --host 0.0.0.0 --port 8000
"""
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from model.retrieval import RetrievalEngine
from model.citations import CitationGraph
from model import ask as ask_mod
from model import metadata as meta_mod
from model import history as history_mod

app = FastAPI(title="AILSE Legal Search API", version="2.0.0",
              description="Perplexity-style legal search over Indian Supreme Court cases")

_origins = [os.getenv("FRONTEND_URL", "http://localhost:3000"),
            "http://localhost:3000", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # accept any localhost / 127.0.0.1 port in dev (fixes preflight 400)
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = RetrievalEngine()
_graph = CitationGraph()


@app.on_event("startup")
def _warm_models():
    """Pre-load embed + rerank models so the first query isn't slow."""
    try:
        history_mod.init_db()
    except Exception as e:
        print(f"[history] init failed: {e}")
    from model.retrieval import _embed, _rerank
    try:
        _embed(); _rerank()
        print("[warm] models loaded")
    except Exception as e:
        print(f"[warm] failed (non-fatal): {e}")


class AskRequest(BaseModel):
    query: str
    k: int = 6

class ChatRequest(BaseModel):
    case_id: str
    question: str

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@app.get("/health")
def health():
    try:
        with _engine._conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks;")
            n = cur.fetchone()[0]
        return {"status": "healthy", "chunks": n}
    except Exception as e:
        raise HTTPException(503, f"db unhealthy: {e}")


@app.post("/ask")
def ask(req: AskRequest):
    """Global Perplexity-style answer across ALL cases, with inline citations."""
    if not req.query.strip():
        raise HTTPException(400, "query required")
    history_mod.log(req.query, "ask")
    return ask_mod.answer(req.query, k=req.k)


@app.post("/chat_query")
def chat_query(req: ChatRequest):
    """Per-case chat — scoped to ONE judgment (case_id filter)."""
    if not req.question.strip():
        raise HTTPException(400, "question required")
    return ask_mod.answer(req.question, case_id=req.case_id.strip())


@app.post("/query")
def query(req: QueryRequest):
    """Legacy-compatible search: returns unique case cards with metadata."""
    history_mod.log(req.query, "search")
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
def search(q: str = Query(..., min_length=1), k: int = Query(10, ge=1, le=50),
           case_id: str = Query(None)):
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
def case_detail(case_id: str):
    """Case metadata (title/judges/date/summary) + PDF path."""
    data = meta_mod.get(case_id.strip())
    data["pdfUrl"] = f"/supreme_court_pdfs/{case_id.strip()}.pdf"
    return data


@app.get("/cases/{case_id}/cites")
def cites(case_id: str):
    return {"case_id": case_id, "cites": _graph.cites(case_id.strip())}


@app.get("/cases/{case_id}/cited-by")
def cited_by(case_id: str):
    return {"case_id": case_id, "cited_by": _graph.cited_by(case_id.strip())}
