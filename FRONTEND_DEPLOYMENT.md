# Frontend Vercel Deployment Guide

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
   - Install Command: `npm ci`

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
VITE_API_URL=https://y6vgijxxp7.us-east-1.awsapprunner.com
VITE_APP_NAME=AILSE
VITE_APP_VERSION=1.0.0
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
├── env.example            # Environment variables template
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
