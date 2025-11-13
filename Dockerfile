# Multi-stage build for smaller final image
FROM python:3.11-slim as builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./

# Copy source code
COPY src ./src

# Install dependencies and build the package
RUN uv pip install --system --no-cache .

# Final stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_MODE=stdio

# Create app user for security
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app/resources/pricelists && \
    chown -R mcpuser:mcpuser /app

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/open-mcp-tools /usr/local/bin/open-mcp-tools

# Copy source code (needed for resource loading)
COPY --chown=mcpuser:mcpuser src ./src
COPY --chown=mcpuser:mcpuser schemas ./schemas
COPY --chown=mcpuser:mcpuser resources ./resources

# Switch to non-root user
USER mcpuser

# Create volume mount points
VOLUME ["/app/resources/pricelists"]

# Expose MCP server port
EXPOSE 7284

# Health check (HTTP endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7284/health').read()" || exit 1

# Default command: Run in HTTP/SSE mode
ENTRYPOINT ["open-mcp-tools"]
