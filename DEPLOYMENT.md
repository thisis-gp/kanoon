# Kanoon Deployment Guide

This document explains the CI/CD pipeline setup for the Kanoon legal search application.

## Branch Structure

- **`master`**: Development branch
  - Triggers development deployment
  - Deploys to `kanoon-backend-dev` App Runner service
  - Uses `kanoon-backend-dev` ECR repository

- **`prod`**: Production branch
  - Triggers production deployment
  - Deploys to `kanoon-backend-service` App Runner service
  - Uses `kanoon-backend` ECR repository

## Prerequisites

### AWS Resources Required

1. **ECR Repositories**:
   ```bash
   # Create production repository
   aws ecr create-repository --repository-name kanoon-backend --region us-east-1
   
   # Create development repository
   aws ecr create-repository --repository-name kanoon-backend-dev --region us-east-1
   ```

2. **App Runner Services**:
   - `kanoon-backend-service` (production)
   - `kanoon-backend-dev` (development)

3. **IAM Permissions**:
   - ECR push/pull permissions
   - App Runner service update permissions

### GitHub Secrets Required

Add these secrets to your GitHub repository:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `GROQ_API_KEY`
- `QDRANT_CLOUD_URL`
- `QDRANT_CLOUD_API_KEY`

## Deployment Workflow

### Development Deployment

1. **Push to master branch**:
   ```bash
   git add .
   git commit -m "feat: new feature"
   git push origin master
   ```

2. **GitHub Actions automatically**:
   - Builds Docker image
   - Pushes to ECR (`kanoon-backend-dev`)
   - Updates App Runner service (`kanoon-backend-dev`)

### Production Deployment

1. **Merge to prod branch**:
   ```bash
   git checkout prod
   git merge master
   git push origin prod
   ```

2. **GitHub Actions automatically**:
   - Builds Docker image
   - Pushes to ECR (`kanoon-backend`)
   - Updates App Runner service (`kanoon-backend-service`)

## Manual Deployment

You can also trigger deployments manually:

1. Go to GitHub Actions tab
2. Select the workflow (deploy-dev.yml or deploy-prod.yml)
3. Click "Run workflow"

## Monitoring Deployments

### Check Deployment Status

```bash
# Check App Runner service status
aws apprunner describe-service --service-arn <SERVICE_ARN>

# Check ECR images
aws ecr list-images --repository-name kanoon-backend
aws ecr list-images --repository-name kanoon-backend-dev
```

### View Logs

1. Go to AWS App Runner console
2. Select your service
3. Go to "Logs" tab
4. View real-time logs

## Environment Variables

### Development
- `ENVIRONMENT=development`
- `HOST=0.0.0.0`
- `PORT=8000`

### Production
- `ENVIRONMENT=production`
- `HOST=0.0.0.0`
- `PORT=8000`

## Troubleshooting

### Common Issues

1. **ECR Push Failed**:
   - Check AWS credentials
   - Verify ECR repository exists
   - Check IAM permissions

2. **App Runner Update Failed**:
   - Verify service name matches
   - Check service ARN
   - Verify ECR image exists

3. **Environment Variables Missing**:
   - Check GitHub secrets
   - Verify secret names match workflow

### Debug Commands

```bash
# Test AWS credentials
aws sts get-caller-identity

# List ECR repositories
aws ecr describe-repositories

# List App Runner services
aws apprunner list-services
```

## Security Best Practices

1. **Branch Protection**:
   - Enable branch protection rules for `prod`
   - Require pull request reviews
   - Require status checks

2. **Secrets Management**:
   - Use GitHub secrets for sensitive data
   - Rotate AWS keys regularly
   - Use least privilege IAM policies

3. **Image Security**:
   - Scan images for vulnerabilities
   - Use specific image tags (not `latest`)
   - Regular security updates

## Rollback Procedure

If a deployment fails:

1. **Find previous working image**:
   ```bash
   aws ecr list-images --repository-name kanoon-backend --query 'imageIds[*].imageTag'
   ```

2. **Update App Runner service**:
   ```bash
   aws apprunner start-deployment --service-arn <SERVICE_ARN> --source-configuration '{
     "ImageRepository": {
       "ImageIdentifier": "<PREVIOUS_IMAGE_TAG>",
       "ImageRepositoryType": "ECR"
     }
   }'
   ```

## Support

For deployment issues:
1. Check GitHub Actions logs
2. Check AWS App Runner logs
3. Verify all prerequisites are met
4. Contact the development team
