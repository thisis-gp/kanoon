# GitFlow Setup Guide

## **Branch Structure**

```
master (development)
  ↓ (PR + Review)
prod (production)
  ↓ (auto-deploy)
AWS App Runner
```

## **Workflow Process**

### **1. Development Workflow**
```bash
# Work on master branch
git checkout master
git pull origin master

# Make your changes
git add .
git commit -m "feat: add new feature"
git push origin master
```

### **2. Create PR to Production**
```bash
# Create PR from master to prod
# Go to GitHub → Pull Requests → New Pull Request
# Base: prod ← Compare: master
```

### **3. Review Process**
- ✅ **Required reviewers** (set in GitHub settings)
- ✅ **CI checks must pass** (linting, tests, Docker build)
- ✅ **No merge conflicts**

### **4. Merge to Production**
```bash
# After PR approval, merge to prod
# This triggers automatic deployment to AWS
```

## **GitHub Settings to Configure**

### **1. Branch Protection Rules**

#### **For `master` branch:**
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- ✅ Include administrators

#### **For `prod` branch:**
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- ✅ Require review from code owners
- ✅ Include administrators
- ✅ Restrict pushes that create files

### **2. Environment Protection**

#### **Production Environment:**
- ✅ Required reviewers (add team members)
- ✅ Wait timer: 0 minutes
- ✅ Restrict to specific branches: `prod`

## **How to Set Up Branch Protection**

### **Step 1: Go to Repository Settings**
1. Go to your GitHub repository
2. Click **Settings** → **Branches**

### **Step 2: Add Branch Protection Rule for `master`**
1. Click **Add rule**
2. Branch name pattern: `master`
3. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
4. Click **Create**

### **Step 3: Add Branch Protection Rule for `prod`**
1. Click **Add rule**
2. Branch name pattern: `prod`
3. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Require review from code owners
4. Click **Create**

## **Example Workflow**

### **Developer Workflow:**
```bash
# 1. Work on master branch
git checkout master
git pull origin master

# 2. Make changes directly on master
# ... code changes ...

# 3. Commit and push
git add .
git commit -m "feat: add new API endpoint"
git push origin master
```

### **Release to Production:**
```bash
# 1. After changes are on master
# Go to GitHub → Create PR: master → prod

# 2. After PR approval and merge
# Deployment happens automatically!
```

## **Benefits of This Setup**

- ✅ **Code Review**: All changes reviewed before production
- ✅ **Quality Gates**: CI checks must pass
- ✅ **Rollback Safety**: Easy to revert if issues
- ✅ **Audit Trail**: Clear history of what went to production
- ✅ **Team Collaboration**: Multiple reviewers can approve
- ✅ **Automated Deployment**: No manual deployment needed

## **Troubleshooting**

### **If CI fails:**
- Check the Actions tab for error details
- Fix the issues in your branch
- Push again to trigger new CI run

### **If deployment fails:**
- Check the deployment logs in Actions
- Verify AWS credentials and permissions
- Check App Runner service status

### **If PR can't be merged:**
- Ensure all CI checks pass
- Get required approvals
- Resolve any merge conflicts
