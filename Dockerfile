# ==========================================
# Stage 1: Build Frontend Next.js Application
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_PUBLIC_API_URL=/api/v1 \
    NEXT_OUTPUT_MODE=export \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN npm run build

# ==========================================
# Stage 2: Build Backend Python Dependencies
# ==========================================
FROM python:3.14-slim AS backend-builder
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
RUN pip install --no-cache-dir .

# ==========================================
# Stage 3: Final Production Image
# ==========================================
FROM python:3.14-slim AS runner
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL="sqlite:////app/data/kra_reconciliation.db" \
    CORS_ORIGINS="*"

# Install Nginx and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages & executables from builder
COPY --from=backend-builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy backend application code & database migration setup
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Copy built frontend static export to Nginx root
COPY --from=frontend-builder /app/frontend/out /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Ensure executable permissions and create data directory for persistent SQLite fallback
RUN chmod +x /app/docker-entrypoint.sh && \
    mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
