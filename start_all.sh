#!/bin/bash
# Start both backend service and MCP server
# This script manages both processes and handles graceful shutdown

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# PIDs for cleanup
BACKEND_PID=""
MCP_PID=""

# Cleanup function
cleanup() {
    log_info "Shutting down services..."
    
    if [ ! -z "$MCP_PID" ]; then
        log_info "Stopping MCP server (PID: $MCP_PID)..."
        kill -TERM "$MCP_PID" 2>/dev/null || true
        wait "$MCP_PID" 2>/dev/null || true
    fi
    
    if [ ! -z "$BACKEND_PID" ]; then
        log_info "Stopping backend service (PID: $BACKEND_PID)..."
        kill -TERM "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    
    log_info "All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if .env file exists
if [ ! -f ".env" ]; then
    log_error ".env file not found!"
    log_info "Copy .env.example to .env and configure it:"
    log_info "  cp .env.example .env"
    exit 1
fi

# Load environment variables
source .env

# Get ports from environment or use defaults
BACKEND_PORT=${BACKEND_SERVICE_PORT:-8000}
MCP_PORT=${MCP_SERVER_PORT:-3000}

log_info "=========================================="
log_info "Starting CSA Assessment Reports Services"
log_info "=========================================="
log_info "Backend Service Port: $BACKEND_PORT"
log_info "MCP Server Port: $MCP_PORT"
log_info "=========================================="

# Start backend service
log_info "Starting backend service..."
(cd backend && uv run start_backend.py) &
BACKEND_PID=$!

# Wait for backend to be ready
log_info "Waiting for backend service to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
        log_info "✓ Backend service is ready"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        log_error "Backend service failed to start within timeout"
        cleanup
        exit 1
    fi
    
    sleep 1
done

# Start MCP server
log_info "Starting MCP server..."
(cd mcp && uv run start_mcp.py) &
MCP_PID=$!

# Wait a bit for MCP server to start
sleep 2

log_info "=========================================="
log_info "✓ All services started successfully!"
log_info "=========================================="
log_info "Backend Service: http://localhost:$BACKEND_PORT"
log_info "  - Health: http://localhost:$BACKEND_PORT/health"
log_info "  - Docs: http://localhost:$BACKEND_PORT/docs"
log_info "MCP Server: http://localhost:$MCP_PORT"
log_info "=========================================="
log_info "Press Ctrl+C to stop all services"
log_info "=========================================="

# Wait for processes
wait $BACKEND_PID $MCP_PID


# Made with Bob