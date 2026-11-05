# Frontend Vercel Deployment Guide

> **Updated for the current stack.** The frontend is a Vite app that calls the backend through `VITE_API_URL`. Two ways to host it: bundled into the backend image (same origin, see [docs/DEPLOY-VM.md](docs/DEPLOY-VM.md)) or on Vercel with `VITE_API_URL` pointing at wherever the backend is reachable (for example a tunnel URL). The `awsapprunner.com` URL and the `VITE_APP_NAME` / `VITE_APP_VERSION` settings in older versions of this guide are outdated: the AWS backend is gone and the app does not read those two variables. The Firebase variables are required for login; see [Frontend/README.md](Frontend/README.md) for the full list.
> Note: `Frontend/env.example` mentioned below is now `Frontend/env.sample`.

## **🚀 Complete Setup Steps**

### **Step 1: Vercel Account Setup**

1. **Go to [Vercel](https://vercel.com)**
2. **Sign up/Login** with GitHub
3. **Import your repository** `thisis-gp/kanoon`
4. **Set Root Directory** to `Frontend`
5. **Configure Build Settings**:
   - Framework Preset: `Vite`
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Install Command: `npm ci` (or `npm install`)

### **Step 2: Get Vercel Credentials**

1. **Go to Vercel Dashboard** → **Settings** → **General**
2. **Copy these values**:
   - `VERCEL_TOKEN` (from Account Settings → Tokens)
   - `VERCEL_ORG_ID` (from Team Settings)
   - `VERCEL_PROJECT_ID` (from Project Settings)

### **Step 3: Create Frontend Environment in GitHub**

1. **Go to GitHub** → **Settings** → **Environments**
2. **Click "New environment"**
3. **Name it**: `frontend`
4. **Add environment secrets**:
   - `VERCEL_TOKEN`: your_vercel_token
   - `VERCEL_ORG_ID`: your_org_id
   - `VERCEL_PROJECT_ID`: your_project_id

### **Step 4: Configure Environment Protection Rules (Optional)**

For the `frontend` environment:
- ✅ **Required reviewers** (if you want approval)
- ✅ **Wait timer**: 0 minutes
- ✅ **Restrict to specific branches**: `prod`

### **Step 5: Configure Environment Variables**

In **Vercel Dashboard** → **Project Settings** → **Environment Variables**:

```
VITE_API_URL=https://<your-backend-origin>    # no trailing slash
VITE_FIREBASE_API_KEY=...                       # and the other VITE_FIREBASE_* values
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
VITE_FIREBASE_DATABASE_URL=...
```

### **Step 6: Test Deployment**

1. **Push to master**:
   ```bash
   git add Frontend/
   git commit -m "feat: add frontend Vercel deployment setup"
   git push origin master
   ```

2. **Create PR: master → prod**
3. **Merge PR** → Frontend deploys automatically!

## **📁 File Structure Created**

```
Frontend/
├── Dockerfile              # Docker configuration
├── .dockerignore           # Docker ignore file
├── vercel.json            # Vercel configuration
├── env.sample             # Environment variables template
└── package.json           # Updated with start script

.github/workflows/
└── deploy-frontend.yml    # Frontend deployment workflow
```

## **🔄 Deployment Workflow**

1. **Make changes** in `Frontend/` directory
2. **Commit to master** branch
3. **Create PR: master → prod**
4. **Merge PR** → Triggers deployment
5. **Frontend deploys** to Vercel automatically

## **✅ What Happens on Deployment**

1. **GitHub Actions** detects changes in `Frontend/`
2. **Installs dependencies** with `npm ci`
3. **Runs tests** (if configured)
4. **Builds application** with `npm run build`
5. **Deploys to Vercel** using Vercel CLI
6. **Updates production** URL

## **🔧 Configuration Details**

### **Docker Support**
- ✅ **Dockerfile** for containerized builds
- ✅ **.dockerignore** for optimized builds
- ✅ **Multi-stage builds** for production

### **Vercel Integration**
- ✅ **Automatic deployments** on PR merge
- ✅ **Environment variables** management
- ✅ **Custom domain** support
- ✅ **Preview deployments** for PRs

### **CI/CD Features**
- ✅ **Only deploys** when `Frontend/` changes
- ✅ **Only deploys** from `prod` branch
- ✅ **Build validation** before deployment
- ✅ **Automatic cleanup** after deployment

## **🌐 Access Your Frontend**

After deployment, you'll get:
- **Production URL**: `https://your-project.vercel.app`
- **Custom Domain**: Configure in Vercel dashboard
- **Preview URLs**: For each PR

## **📊 Monitoring**

- **Vercel Dashboard**: Real-time deployment status
- **GitHub Actions**: Build and deployment logs
- **Vercel Analytics**: Performance metrics

## **🚨 Troubleshooting**

### **Common Issues:**

1. **Build Fails**:
   - Check `package.json` scripts
   - Verify all dependencies are installed
   - Check for TypeScript errors

2. **Environment Variables**:
   - Ensure all `VITE_*` variables are set
   - Check Vercel environment variable configuration

3. **Deployment Not Triggered**:
   - Verify workflow file is in `.github/workflows/`
   - Check if changes are in `Frontend/` directory
   - Ensure PR is merged to `prod` branch

## **🎯 Next Steps**

1. **Set up Vercel account** and import repository
2. **Add GitHub secrets** for Vercel integration
3. **Configure environment variables** in Vercel
4. **Test deployment** with a small change
5. **Configure custom domain** (optional)

**Your frontend will be live on Vercel!** 🚀

## Backend side of a Vercel deployment

- Set `CORS_ALLOWED_ORIGINS=https://<your-vercel-domain>` in the backend environment and restart it. Without this the browser blocks the API calls.
- Add the Vercel domain to Firebase "Authorized domains", or Google login fails.
- The case PDFs must ship with the frontend build (`Frontend/public/supreme_court_pdfs/`, large and not in git) because the viewer loads them from the page origin.
- If the backend is behind an ngrok tunnel, the frontend already sends the `ngrok-skip-browser-warning` header on API calls.
