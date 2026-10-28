# Build Stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Builds assets with base: '/markdown-optimizer/'
RUN npm run build

# Production Stage with Nginx
FROM nginx:alpine

# Copy custom nginx configuration listening on 9123
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy production build assets
COPY --from=build /app/dist /usr/share/nginx/html

# Frontend listens internally on port 9123 per Docker routing rules
EXPOSE 9123

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:9123/markdown-optimizer/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
