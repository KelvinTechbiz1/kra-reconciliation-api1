#!/bin/sh
set -e

echo "======================================================="
echo " Starting KRA Reconciliation Application Container     "
echo "======================================================="

# Run database migrations and seed initial accounts
echo "[1/3] Initializing database schema & admin accounts..."
python -m app.init_db

PORT="${PORT:-8000}"
echo "[2/3] Configuring environment (Target Port: ${PORT})..."

# Check if Nginx is installed
if command -v nginx > /dev/null 2>&1; then
    # Replace default 8000 port in nginx config if custom PORT environment variable is specified
    if [ "$PORT" != "8000" ]; then
        sed -i "s/listen 8000;/listen ${PORT};/g" /etc/nginx/conf.d/default.conf || true
    fi

    echo "[3/3] Launching Services..."
    echo "  -> Starting FastAPI backend on http://127.0.0.1:8001..."
    uvicorn app.main:app --host 127.0.0.1 --port 8001 &
    BACKEND_PID=$!

    # Wait 2 seconds for backend to start up
    sleep 2

    echo "  -> Starting Nginx web server on http://0.0.0.0:${PORT}..."
    nginx -g "daemon off;" &
    NGINX_PID=$!

    # Trap termination signals for clean shutdown
    trap "echo 'Stopping container processes...'; kill -TERM $BACKEND_PID $NGINX_PID 2>/dev/null || true" INT TERM
    wait $BACKEND_PID $NGINX_PID
else
    echo "[3/3] Launching FastAPI backend on http://0.0.0.0:${PORT}..."
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
fi
