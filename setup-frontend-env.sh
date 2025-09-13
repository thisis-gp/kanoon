#!/bin/bash

# Frontend Environment Setup Script
echo "🚀 Setting up Frontend Environment for GitHub Actions..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository. Please run this from the project root."
    exit 1
fi

echo "📋 Frontend Environment Setup Instructions:"
echo ""
echo "1. 🌐 Go to GitHub → Settings → Environments"
echo "2. ➕ Click 'New environment'"
echo "3. 📝 Name it: 'frontend'"
echo "4. 🔐 Add these environment secrets:"
echo ""
echo "   VERCEL_TOKEN: your_vercel_token"
echo "   VERCEL_ORG_ID: your_org_id" 
echo "   VERCEL_PROJECT_ID: your_project_id"
echo ""
echo "5. ⚙️  Configure environment protection rules (optional):"
echo "   - Required reviewers: (optional)"
echo "   - Wait timer: 0 minutes"
echo "   - Restrict to branches: prod"
echo ""
echo "6. 🌐 Set up Vercel project:"
echo "   - Go to vercel.com"
echo "   - Import repository: thisis-gp/kanoon"
echo "   - Set root directory: Frontend"
echo "   - Configure environment variables in Vercel dashboard"
echo ""
echo "7. 🧪 Test deployment:"
echo "   - Push changes to master"
echo "   - Create PR: master → prod"
echo "   - Merge PR → Frontend deploys automatically!"
echo ""
echo "✅ Environment setup complete!"
echo "📖 See FRONTEND_DEPLOYMENT.md for detailed instructions"
