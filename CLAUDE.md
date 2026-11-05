# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Kanoon is a full-stack semantic legal search engine over ~924 Indian Supreme Court judgments. FastAPI backend on Postgres/ParadeDB + React/Vite frontend (Vercel, or bundled into the backend image for the VM deployment in `docs/DEPLOY-VM.md`). Everything — chunks, embeddings, metadata, citations, search history, answer cache — lives in Postgres.

## Commands

Backend (run from `Backend/`):

- `python -m uvicorn model.api:app --host 0.0.0.0 --port 8000` — dev server (`uvicorn` isn't on PATH on Windows, so invoke via `python -m`)
- `pip install -r requirements.txt`
- `python -m model.retrieval build supreme_court_cleaned_texts` — chunk + embed the corpus into the `chunks` table (**required before search/chat works**)
- `python -m model.metadata backfill supreme_court_cleaned_texts` — extract title/judges/date/summary per case into `case_meta`
- `python -m model.citations build ...` / `python -m model.citations self-refs <pdf_dir>` — build the citation graph
- Copy `Backend/env.sample` → `Backend/.env` and set at least one LLM key (see Gotchas)

Store (Docker Compose service `db`, ParadeDB image):

- `DATABASE_URL=postgresql://ailse:ailse@localhost:5432/ailse` (use `@db:5432` inside compose)

Frontend (run from `Frontend/`):

- `node node_modules/vite/bin/vite.js` (or `npm run dev`) — Vite dev server (`vite` isn't on PATH on Windows)
- `npm run build` · `npm run lint`

## Architecture

**Backend entry:** `Backend/model/api.py` — the whole FastAPI app. Endpoints: `POST /ask`, `POST /query` (case cards), `POST /chat_query` (case-scoped chat), `GET /search`, `GET /cases`, `GET /cases/{id}`, `GET /cases/{id}/cites`, `GET /cases/{id}/cited-by`, `GET /suggestions`, `GET /health`. (The old FAISS/Qdrant `model/main.py` has been removed; do not recreate it.)

**Store:** Postgres via the ParadeDB Docker image (pgvector + pg_search BM25). Tables: `chunks(id, case_id, text, embedding vector(384))`, `case_meta`, `citations`, `case_refs`, `searches`, `answer_cache`.

**Retrieval** (`model/retrieval.py`, `RetrievalEngine`): sentence-safe/word-safe chunking, `all-MiniLM-L6-v2` embeddings, HYBRID search = pgvector dense (`<=>`) + BM25 (pg_search `@@@`) fused with Reciprocal Rank Fusion, then cross-encoder rerank (`cross-encoder/ms-marco-MiniLM-L-6-v2`). `search(query, k, case_id=None)` — pass `case_id` to scope to ONE judgment (per-case chat). In-memory result cache. Env: `INFER_CONCURRENCY` (default 1), `RERANK_DEPTH` (default 50).

**LLM gateway** (`model/llm_gateway.py`): multi-provider fallback (NVIDIA NIM → Groq → OpenRouter), throttled ~24/min (`LLM_MIN_GAP`), daily cap `LLM_DAILY_CAP`. `generate(prompt, system, temperature)` tries providers in order.

**Grounded answers** (`model/ask.py`): `answer(question, case_id, k)` → `{answer, provider, sources, cited}`. Strict-from-sources with inline `[n]` citations plus abstention. Persisted to the `answer_cache` table.

**Supporting modules:** `model/citations.py` (regex extraction of Indian citations → `cites`/`cited_by`), `model/metadata.py` (LLM metadata extraction into `case_meta`), `model/history.py` (writes `searches`; `GET /suggestions` returns popular recent queries).

**Frontend** (`Frontend/`): React 19 + Vite + Tailwind. Unified `/results` page = AI overview (from `/ask`) + case list (from `/query`); HomePage hero routes to `/results?q=`. CasePage = PDF viewer + per-case chat + CitationsPanel. Google-only login via Firebase (`VITE_FIREBASE_*` in `Frontend/.env`). Backend calls go through `src/utils/api.js` using `VITE_API_URL` (empty/unset = same origin; set `http://localhost:8000` for `npm run dev`). Brand name = Kanoon.

## Docs

- `docs/ARCHITECTURE.md`, `docs/EVALUATION.md` (retrieval numbers are a small optimistic proxy; never quote 84-96% or 7 s to 4 ms), `docs/DEPLOY-VM.md`. `DEPLOYMENT.md` and `SETUP_GITFLOW.md` are partly legacy (AWS App Runner).
- The old SQLite/FAISS leftovers (`Backend/db/`, `Backend/build_all_indexes.py`) were removed; do not recreate them.
- Licence: MIT for the code (see `LICENSE`); the judgments are not covered by it (see the README).

## Gotchas

- **Backend needs at least one LLM key** in `Backend/.env`: `NVIDIA_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`. The gateway falls back across whichever are set.
- **Search/chat return nothing until the index is built** — run `python -m model.retrieval build ...` first.
- **Rate limits:** `RATE_OTHER_PER_MIN` (60), `RATE_LLM_PER_MIN` (10), `RATE_SEARCH_PER_MIN` (10, `/query` + `/search`), `RATE_STATIC_PER_MIN` (300), extra CORS origins via `CORS_ALLOWED_ORIGINS`. All other security env vars (LLM caps, deadline, pool, retention, health token) are listed in `Backend/env.sample`; background in `docs/SECURITY.md`.
- **Windows:** `vite`/`uvicorn` aren't on PATH → invoke via `node node_modules/vite/bin/vite.js` and `python -m uvicorn`. `pkill -f` is unreliable → use PowerShell `Stop-Process`.
- **Data dirs (large/local):** `supreme_court_pdfs/`, `supreme_court_cleaned_texts/`, `supreme_court_texts/`.
- `case_id` = the PDF/text filename stem (e.g. `660` ↔ `660.pdf` ↔ `660.txt`); it threads through `chunks`, `case_meta`, citations, and PDF paths.
