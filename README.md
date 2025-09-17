Kanoon – Legal Case Search & Chat

Overview

Kanoon is a full‑stack legal research assistant for Indian Supreme Court cases. It provides fast semantic search, per‑case chat grounded on FAISS indexes, and global search powered by Qdrant. The backend is deployed on AWS App Runner; the frontend is deployed on Vercel.

Project Report

For background, design decisions, and evaluation, refer to the project report included in this repository:
[Project Report (PDF)](MSc_UoR_Computer_Science_Report_Template_and_Guide__1_%20%282%29.pdf)

Key Features

- Semantic search across 900+ Supreme Court PDFs
- Per‑case chat with grounded retrieval (FAISS)
- Global search via Qdrant Cloud
- Clean, responsive React (Vite + Tailwind)
- CI/CD: GitHub Actions → AWS App Runner (Backend) and Vercel (Frontend)

Architecture

- Frontend (Vercel): React + Vite; serves PDFs from `Frontend/public/supreme_court_pdfs/`
- Backend (AWS App Runner): FastAPI; integrates FAISS (per‑case) and Qdrant (global)
- Data: SQLite for metadata, FAISS indexes per case, Qdrant collection for global vector search

Monorepo Layout

- Backend/: FastAPI service, FAISS/Qdrant integration, metadata DB
- Frontend/: React app, SPA routing, PDF viewer
- DEPLOYMENT.md: Backend deployment (AWS)
- FRONTEND_DEPLOYMENT.md: Frontend deployment (Vercel)
- FIREBASE_SETUP.md: Optional chat history index setup
- SETUP_GITFLOW.md: Branching and environments

Quick Start (Local)

1) Prerequisites
- Python 3.10+, Node 20+, Docker (optional)

2) Environment
- Copy `Backend/env.sample` → `.env` and set values (see Backend README)
- Copy `Frontend/env.sample` → `.env` and set values (see Frontend README)

3) Run Backend

```bash
cd Backend
pip install -r requirements.txt
uvicorn model.main:app --host 0.0.0.0 --port 8000 --reload
```

4) Run Frontend

```bash
cd Frontend
npm install
npm run dev
```

Production Deployments

- Backend: AWS App Runner via GitHub Actions (`.github/workflows/deploy-prod.yml`). See DEPLOYMENT.md
- Frontend: Vercel via GitHub Actions (`.github/workflows/deploy-frontend.yml`) or Vercel dashboard. See FRONTEND_DEPLOYMENT.md

Core Tech

- FastAPI, LangChain, FAISS, Qdrant Cloud, Groq LLM
- React, Vite, Tailwind, Firebase (optional for history)
- AWS App Runner, ECR, GitHub Actions, Vercel

Documentation

- Backend details: `Backend/README.md`
- Frontend details: `Frontend/README.md`
- Backend deployment: `DEPLOYMENT.md`
- Frontend deployment: `FRONTEND_DEPLOYMENT.md`
- Firebase index setup: `FIREBASE_SETUP.md`
- GitFlow & environments: `SETUP_GITFLOW.md`

License

This repository is provided for educational and research purposes. Review third‑party licenses for dependencies and datasets.


