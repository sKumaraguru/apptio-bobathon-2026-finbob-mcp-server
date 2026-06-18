# Stage 1: Builder
FROM python:3.13-alpine AS builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache \
  gcc \
  musl-dev \
  libffi-dev \
  openssl-dev \
  cargo \
  rust \
  curl

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-alpine

WORKDIR /app

# Copy only Python runtime and installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY *.py .
COPY mcp_models.py .

# Create non-root user for security
RUN adduser -D -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 3000

# Start MCP server
CMD ["python", "start_mcp.py"]

# Optimized with Alpine multi-stage build - Made with Bob

# Made with Bob
