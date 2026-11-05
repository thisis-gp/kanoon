Frontend – React (Vite) SPA

Overview

The AILSE frontend is a Vite + React SPA deployed on Vercel. It provides global search, per‑case pages with PDF viewing, and a chat interface grounded on backend retrieval.

Project Report

For system background and UX considerations, see the repository report:
[Project Report (PDF)](../MSc_UoR_Computer_Science_Report_Template_and_Guide__1_%20%282%29.pdf)

Local Development

```bash
npm install
npm run dev
```

Environment

Copy `env.sample` to `.env.local` and configure:

- `VITE_API_URL`: backend origin without a trailing slash. Empty or unset means same origin.
- `VITE_FIREBASE_*`: optional. Without them the app still works; login shows a "not available" message and search and case pages stay public.
- `VITE_REPO_URL`: optional GitHub link for the footer.

Running against a tunnel (ngrok or ssh)

- ngrok: set `VITE_API_URL=https://<name>.ngrok-free.dev`. Every request already sends `ngrok-skip-browser-warning: 1`, so the interstitial page does not break `fetch`.
- The backend must allow your origin: set `CORS_ALLOWED_ORIGINS=http://localhost:5173` (dev) or your Vercel domain on the backend and restart it.
- ssh: `ssh -L 8080:127.0.0.1:8080 <host>`, then `VITE_API_URL=http://127.0.0.1:8080`.
- PDFs load from the page origin (`/supreme_court_pdfs/{id}.pdf`), not from the API tunnel, because an iframe cannot send the skip header.

Error handling

- 429: shows the wait time from `Retry-After`. 503: "answer service is busy or unavailable", case search still works. Network failure and abstention ("Not available in the sources.") have their own messages.

Build & Preview

```bash
npm run build
npm start  # vite preview --host 0.0.0.0 --port 3000
```

Static Assets

- PDFs are served from `public/supreme_court_pdfs/{id}.pdf`
- Vercel routing is configured in `vercel.json` to serve assets and SPA fallback

API Integration

- API calls are in `src/utils/api.js`
- `getCaseById(id)` builds PDF URLs locally and expects minimal metadata from the backend

Deployment (Vercel)

- Automatic via GitHub Actions (`.github/workflows/deploy-frontend.yml`) or Vercel dashboard
- Ensure the project root is `Frontend/` in Vercel settings

Troubleshooting

- Blank page on Vercel: verify `Frontend/vercel.json` routes for `/assets` and `/supreme_court_pdfs`
- 404 on case details: backend `/cases/{id}` must return minimal metadata with fallbacks
- Firebase index errors: create the composite index as per `../../FIREBASE_SETUP.md`

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript and enable type-aware lint rules. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
