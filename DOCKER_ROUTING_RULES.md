# Docker & Reverse Proxy Routing Rules — Markdown Optimizer

Instructions applied whenever Docker, containerization, networking, reverse proxy configuration, or access URLs are created, modified, or documented for **Markdown Optimizer**.

---

## 1. Zero Port 80 in Docker Compose

- Never add host port 80 mappings to `docker-compose.yml`.
- Frontend must listen internally on port **9123**.
- Backend must listen internally on port **9124**.
- Use `expose` where appropriate instead of publishing application ports directly to the host.
- Never use `80:80`, `80:9123`, `80:9124`, or any other host port 80 mapping in Docker Compose.
- Frontend, backend, and Host Nginx must communicate through the appropriate shared Docker network.
- Use the existing Markdown Optimizer Docker network if available. Otherwise, configure a shared external network consistently across the application and Host Nginx.
- Do not create unnecessary Docker networks or modify unrelated services.
- Preserve existing database and supporting-service configurations unless changes are necessary.

## 2. Portless URL Policy

Never display explicit application service port numbers in browser URLs, access links, API documentation, or user-facing instructions.

Use these clean URLs for Markdown Optimizer:

- **Main Application:** `http://localhost/markdown-optimizer/`
- **Swagger API Docs:** `http://localhost/markdown-optimizer/docs`
- **OpenAPI Schema:** `http://localhost/markdown-optimizer/openapi.json`
- **API Base Path:** `/markdown-optimizer/api/v1/`
- **WebSocket Stream, if implemented:** `ws://localhost/markdown-optimizer/ws/`

All user-facing documentation must use these portless URLs. Internal service ports `9123` and `9124` may appear in Docker, Nginx, and application configuration files where technically required, but never in browser-facing URLs.

## 3. Reverse Proxy Routing via Host Nginx (`host-nginx.conf`)

Port 80/443 routing must be handled exclusively by the Host Nginx reverse proxy.

- Do not configure Docker Compose to publish host port 80 for Markdown Optimizer.
- Configure Host Nginx to reach the frontend and backend through their actual container or service names and shared Docker network.
- Route `/markdown-optimizer/` to the frontend container on port `9123`, preserving the `/markdown-optimizer/` application base path.
- Route `/markdown-optimizer/api/v1/` to the backend container on port `9124`, mapping requests to the corresponding internal API routes.
- Route `/markdown-optimizer/docs` to the backend Swagger documentation endpoint.
- Route `/markdown-optimizer/openapi.json` to the backend OpenAPI schema endpoint.
- If WebSockets are implemented, route `/markdown-optimizer/ws/` to the appropriate backend WebSocket endpoint and configure HTTP/1.1, `Upgrade`, and `Connection` headers.
- Preserve the appropriate `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto` headers.
- Ensure FastAPI's `root_path`, Swagger schema URL, and reverse-proxy path handling work correctly under `/markdown-optimizer`.
- Avoid double-prefixing API paths or stripping required prefixes.
- Inspect the existing Nginx configuration before making changes. Update existing configuration rather than creating conflicting server blocks.
- Preserve existing HTTPS/TLS settings and unrelated application routes.
- Do not overwrite or replace the host's complete Nginx configuration unnecessarily.
- Ensure proxy timeout and request-size settings are appropriate for Markdown processing and any supported file uploads.

## 4. Frontend Client Architecture

All frontend API calls must use clean relative endpoints.

- Update `config.js`, environment configuration, and React/Vite components to use paths such as `/markdown-optimizer/api/v1/...`.
- Never hardcode `localhost:9123`, `localhost:9124`, or other host-and-port combinations in frontend API calls.
- Never construct API URLs using hardcoded local service addresses.
- Configure Vite with the correct `/markdown-optimizer/` base path.
- Ensure the production frontend server listens internally on port `9123`.
- Ensure the backend listens internally on port `9124`.
- Configure frontend routing to support direct navigation and page refreshes under `/markdown-optimizer/`.
- Ensure production frontend assets, JavaScript bundles, CSS, fonts, and other static files load correctly under the `/markdown-optimizer/` prefix.
- Confirm API requests, Swagger documentation, and any implemented WebSocket connections work through Host Nginx.
- If WebSockets are implemented, construct their URLs dynamically using `window.location.host` and the current page protocol, switching between `ws:` and `wss:` as appropriate.
- Browser DevTools Network requests must use the standard browser origin without explicit application service ports.
- Do not add unnecessary CORS exceptions when requests are routed through the same origin.
- Preserve existing frontend framework, state management, routing, and build configuration unless changes are required for deployment.

## 5. Docker Networking and Service Configuration

- Keep the frontend and backend on their designated service ports: `9123` and `9124`.
- Ensure Host Nginx can resolve and access both application containers through the shared Docker network.
- Inspect the existing repository to identify actual service names, container names, and network names before making changes.
- Do not assume a network or container name without inspecting the existing configuration.
- Do not expose application ports unnecessarily to the host.
- Preserve existing environment variables, database connectivity, health checks, volumes, restart policies, and service dependencies unless a change is necessary.
- Ensure the frontend can access backend APIs through the intended reverse-proxy path.
- Ensure the backend can reach its existing database, storage, and other required internal services.
- Use Docker service DNS names rather than hardcoded container IP addresses.
- Keep secrets in environment variables or an appropriate secrets-management mechanism.
- Include appropriate container health checks and startup dependencies where needed.
- Ensure the application binds to `0.0.0.0` inside its container when required for Docker networking.
- Do not introduce additional databases, services, or infrastructure unless required by the existing application.

## 6. Markdown Optimizer Application Requirements

These routing rules apply specifically to the **Markdown Optimizer** application.
Preserve and support the application's actual implemented functionality.
- Do not invent application modules, API endpoints, or features that do not exist in the repository.
- Inspect the existing implementation and route only actual backend endpoints.
- Ensure all frontend pages and nested routes are fully supported under `/markdown-optimizer/`.

