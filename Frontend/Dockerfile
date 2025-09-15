# Frontend Dockerfile for Vercel deployment
FROM node:18-alpine

# Clear build cache and start fresh
RUN rm -rf /var/cache/apk/* && \
    rm -rf /tmp/* && \
    rm -rf /var/tmp/*

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Clear npm cache and install dependencies
RUN npm cache clean --force && \
    npm ci --only=production --no-audit --no-fund

# Copy source code
COPY . .

# Clear any existing build artifacts
RUN rm -rf dist/ && \
    rm -rf node_modules/.cache/ && \
    rm -rf .vite/

# Build the application
RUN npm run build

# Expose port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]