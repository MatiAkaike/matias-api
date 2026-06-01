#!/bin/bash
# start.sh - Inicia el servidor API de Matias
# Uso: ./start.sh [puerto]

PORT=${1:-8000}
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== M.A.T.I.A.S. API ==="
echo "Iniciando en http://localhost:${PORT}"
echo "Endpoints:"
echo "  GET  http://localhost:${PORT}/api/health"
echo "  POST http://localhost:${PORT}/api/chat"
echo "  POST http://localhost:${PORT}/api/session/new"
echo ""

# Kill any existing process on the port
lsof -ti :${PORT} 2>/dev/null | xargs kill -9 2>/dev/null

cd "$DIR" && .venv/bin/python server.py --host 0.0.0.0 --port "${PORT}"
