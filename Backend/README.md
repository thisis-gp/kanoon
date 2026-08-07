Backend – FastAPI, FAISS, Qdrant

Overview

This service powers AILSE's semantic search and per‑case chat. It exposes REST endpoints via FastAPI, loads pre‑built FAISS indexes for each case, and integrates with Qdrant Cloud for global search across all documents.

Project Report

See the repository‑bundled report for design, experiments, and evaluation:
[Project Report (PDF)](../MSc_UoR_Computer_Science_Report_Template_and_Guide__1_%20%282%29.pdf)

Key Endpoints

- `GET /health`: Liveness probe
- `GET /faiss_status`: Status of prebuilt FAISS indexes
- `POST /query`: Global semantic search across cases (Qdrant + metadata)
- `GET /cases/{id}`: Case metadata for a given case id
- `POST /cases/{id}/chat`: Per‑case QA grounded on the case’s FAISS index

Environment Variables

Copy `env.sample` to `.env` and populate:

- `ENVIRONMENT`: development|production
- `FRONTEND_URL`: SPA origin (local dev or Vercel domain)
- `GROQ_API_KEY`: API key for Groq LLM
- `QDRANT_CLOUD_URL`: Qdrant Cloud endpoint
- `QDRANT_CLOUD_API_KEY`: Qdrant Cloud API key

Local Development

```bash
pip install -r requirements.txt
uvicorn model.main:app --host 0.0.0.0 --port 8000 --reload
```

Data & Indexes

- FAISS indexes are prebuilt and shipped in `Backend/faiss_index/`
- Source texts and PDFs live under `Backend/supreme_court_cleaned_texts/` and `Backend/supreme_court_pdfs/`
- SQLite metadata DB: `Backend/cases_metadata.db`

Notes on Embeddings

- FAISS (per‑case) and Qdrant (global) use HuggingFace `all-MiniLM-L6-v2` embeddings to avoid online embedding quotas.
- The API avoids creating embeddings during request handling; indexes are prebuilt offline.

Docker

```bash
docker build -t ailse-backend .
docker run -p 8000:8000 --env-file .env ailse-backend
```

Deployment (AWS App Runner)

- Images are built and pushed to ECR via GitHub Actions.
- App Runner updates service and triggers deployment. See `../../DEPLOYMENT.md` and `.github/workflows/deploy-prod.yml`.

Troubleshooting

- 429 embedding quota: prebuild indexes; do not embed at runtime
- CORS: ensure `FRONTEND_URL` and Vercel domains are in `CORSMiddleware`
- Empty search metadata: ensure SQLite `case_metadata` contains entries


