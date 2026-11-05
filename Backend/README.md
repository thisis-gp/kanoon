# Backend: FastAPI on Postgres/ParadeDB

One FastAPI app (`model/api.py`) does hybrid retrieval, grounded answers with citations, case metadata, a regex citation graph and search history. Everything is stored in Postgres (ParadeDB image: pgvector plus pg_search). In the VM image the same process also serves the built React app and the case PDFs.

Not legal advice: see the disclaimer in the [root README](../README.md). Architecture: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Run locally

```bash
docker compose up -d db                                   # from the repo root; Postgres on localhost:5432
cd Backend
pip install -r requirements.txt                           # fastapi, uvicorn, pydantic, psycopg2-binary, sentence-transformers
cp env.sample .env                                        # add at least one LLM key to enable /ask and /chat_query
export DATABASE_URL=postgresql://ailse:ailse@localhost:5432/ailse
python -m model.retrieval init                            # extensions, table, HNSW and BM25 indexes
python -m model.retrieval build supreme_court_cleaned_texts
python -m model.metadata init && python -m model.metadata backfill supreme_court_cleaned_texts
python -m model.citations init && python -m model.citations build supreme_court_cleaned_texts
python -m uvicorn model.api:app --host 0.0.0.0 --port 8000
```

`build` truncates the `chunks` table before loading. `python -m model.citations self-refs <pdf_dir>` also fills `case_refs` (needed for `cited-by`; slow, requires `markitdown`). Search and chat return nothing until the index is built. The text and PDF folders (`supreme_court_cleaned_texts/`, `supreme_court_pdfs/`) are large and are not in git.

Docker image: build the one-origin image (API plus React) from the repo root with `Dockerfile.vm`; see [docs/DEPLOY-VM.md](../docs/DEPLOY-VM.md). `Backend/Dockerfile` builds the API only.

## Endpoints

| Method and path | Body or query | Returns |
|---|---|---|
| `GET /health` | none | `{"status":"healthy","chunks":N}`; 503 if the database is unreachable |
| `POST /ask` | `{"query": str, "k": int = 6}` | Grounded answer across all cases: `{answer, provider, sources:[{n, case_id, text}], cited:[n]}`. 400 if `query` is blank. Logged to `searches` |
| `POST /chat_query` | `{"case_id": str, "question": str}` | Same shape as `/ask`, restricted to one case. 400 if `question` is blank |
| `POST /query` | `{"query": str, "top_k": int = 5}` | Unique case cards: `{query, total_results, results:[metadata + source]}`. Uses the matching passage as the summary when no summary exists. Logged to `searches` |
| `GET /search` | `q` (required), `k` (1-50, default 10), `case_id` (optional) | Raw reranked chunks without an LLM: `{query, results:[{case_id, text, score}]}` |
| `GET /suggestions` | `limit` (1-12, default 6) | `{suggestions:[str]}`, popular queries of the last 30 days |
| `GET /cases` | `limit` (1-100, default 20), `offset` | Paginated case metadata |
| `GET /cases/{case_id}` | none | `{title, judges, date, summary, ...}` plus `pdfUrl`. An unknown id returns 200 with "Not available" fields, not 404 |
| `GET /cases/{case_id}/cites` | none | `{case_id, cites:[...]}` outbound citations found by regex |
| `GET /cases/{case_id}/cited-by` | none | `{case_id, cited_by:[...]}`. Empty until `case_refs` is filled |
| `GET /supreme_court_pdfs/{id}.pdf` | none | Case PDF, if the PDF folder exists |
| `GET /{path}` | none | Built React app files, with `index.html` as fallback for client-side routes, if the static folder exists |

Interactive docs are at `/docs`.

Error behaviour for `/ask` and `/chat_query`: HTTP 429 with a `Retry-After` header when the daily LLM cap is reached; HTTP 503 "answer service unavailable" when all providers fail or no key is set (no provider detail is returned).

### Rate limits and CORS

- Per client IP, in memory, one worker: 60 requests per minute for API calls in general (`RATE_OTHER_PER_MIN`) and 10 per minute for `/ask` and `/chat_query` (`RATE_LLM_PER_MIN`). Over the limit gives HTTP 429 with `Retry-After`. `/health`, `OPTIONS` and static file GETs are not limited. The IP is the last `X-Forwarded-For` entry (the one a proxy such as ngrok appends); earlier entries are client-controlled and ignored.
- CORS allows only listed origins. The built-in list contains the owner's ngrok origin, `http://127.0.0.1:8080`, `http://localhost:3000` and `http://localhost:5173`. Add more (for example your Vercel domain) with `CORS_ALLOWED_ORIGINS`. A `*` is ignored. Allowed methods are GET, POST and OPTIONS.

## Environment variables

Provider keys are read from `Backend/.env` first, then from the process environment. `.env` is git-ignored; never commit it.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql://ailse:ailse@localhost:5432/ailse` | Postgres connection string (use host `db` inside compose) |
| `NVIDIA_API_KEY` | none | First provider (`meta/llama-3.1-8b-instruct`) |
| `GROQ_API_KEY` | none | Second provider (model set by `GROQ_MODEL`, default `qwen/qwen3.8-27b`) |
| `OPENROUTER_API_KEY` | none | Third provider (`meta-llama/llama-3.3-70b-instruct:free`) |
| `LLM_MIN_GAP` | `2.5` | Minimum seconds between LLM calls (throttle, about 24 calls per minute) |
| `LLM_DAILY_CAP` | `300` | Provider calls allowed per UTC day; cached answers do not count |
| `RATE_OTHER_PER_MIN` | `60` | Per-IP requests per minute for non-LLM API calls |
| `RATE_LLM_PER_MIN` | `10` | Per-IP requests per minute for `/ask` and `/chat_query` |
| `CORS_ALLOWED_ORIGINS` | empty | Comma-separated extra origins, exact match, no wildcard |
| `INFER_CONCURRENCY` | `1` | Model inferences allowed at the same time (embed and rerank). Raising it adds memory, not speed, on 2 cores |
| `RERANK_DEPTH` | `50` | Fused candidates sent to the cross-encoder. Lower is faster. On a small known-item proxy (n=30 per query type, Backend/eval/results/RESULTS.md) depth 20 missed 1 query in 30 that depth 50 got, and cut cold p50 from about 5-7 s to about 2-3 s on the 2-OCPU VM |
| `STATIC_DIR` | `/app/static` | Built frontend folder, served if it exists |
| `PDF_DIR` | `/app/supreme_court_pdfs` | PDF folder, mounted at `/supreme_court_pdfs` if it exists |
| `HF_HOME`, `HF_HUB_OFFLINE` | image defaults | Hugging Face model cache; set offline once models are cached |
| `OMP_NUM_THREADS`, `MKL_NUM_THREADS` | unset | Used on the VM to limit torch to 2 threads |

The gateway tries the providers in the order NVIDIA, Groq, OpenRouter and falls through on any error. Providers whose key is missing are skipped (they raise and the next is tried).

## Layout

| Path | Purpose |
|---|---|
| `model/api.py` | FastAPI app, middleware, endpoints |
| `model/retrieval.py` | Schema, chunking, embedding, hybrid search, rerank |
| `model/ask.py` | Prompt, citations, answer cache |
| `model/llm_gateway.py` | Provider failover, throttle, daily cap |
| `model/metadata.py` | Case metadata extraction (`init`, `backfill`, `get`) |
| `model/citations.py` | Citation extraction (`init`, `build`, `self-refs`, `cites`, `cited-by`) |
| `model/history.py` | Search log and suggestions |
| `clean/` | Text cleaning scripts for the raw judgments |
| `test/` | Plain-Python self-checks, see below |
| `eval/` | Retrieval proxy scripts (being added; see [docs/EVALUATION.md](../docs/EVALUATION.md)) |
| `db/`, `build_all_indexes.py` | Legacy files from the earlier SQLite and FAISS design; not used by `model/api.py` |

## Tests

```bash
python test/test_retrieval.py   # chunker tests need no database; the end-to-end test needs a loaded database
python test/test_citations.py
python test/test_ask.py         # skips the LLM part if no provider key is set
```

`test_retrieval.py` truncates the `chunks` table, so point `DATABASE_URL` at a throwaway database. CI (`.github/workflows/ci.yml`) installs the requirements, compiles `model/api.py` and validates the Docker build.

## Troubleshooting

- `/ask` returns 503: no provider key is set, or every provider failed. The failure takes several seconds because each provider is tried.
- `/ask` returns 429: the per-IP limit or the daily cap. Check `Retry-After`.
- Empty search results: the `chunks` table is empty; run the `build` step.
- Browser CORS error: add the page origin to `CORS_ALLOWED_ORIGINS` and restart.
- Out-of-memory kill under load: keep `INFER_CONCURRENCY=1` and see the memory notes in [docs/DEPLOY-VM.md](../docs/DEPLOY-VM.md).
