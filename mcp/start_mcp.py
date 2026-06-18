#!/usr/bin/env python3
"""
Startup script for the MCP server.

This script starts the FastMCP server that uses Pydantic v2.
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Start the MCP server."""
    # Load environment variables from .env file (optional - for local development)
    # In production (Fargate/Lambda), environment variables are set directly
    from dotenv import load_dotenv

    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        logger.info(f"Loading environment from {env_file}")
        # Don't override existing environment variables (prefer Fargate/Lambda env vars)
        load_dotenv(env_file, override=False)
    else:
        logger.info(f".env file not found at {env_file} - using environment variables from system")

    # Get configuration
    port = int(os.getenv("MCP_SERVER_PORT", "3000"))
    backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000")

    logger.info("=" * 60)
    logger.info("Starting CSA Assessment Reports MCP Server")
    logger.info("=" * 60)
    logger.info(f"MCP Server Port: {port}")
    logger.info(f"Backend Service URL: {backend_url}")
    logger.info(f"Using Pydantic v2 with fastmcp")
    logger.info("=" * 60)

    # Check if backend is accessible
    import httpx

    try:
        logger.info(f"Checking backend health at {backend_url}/api/health...")
        response = httpx.get(f"{backend_url}/api/health", timeout=5.0)
        if response.status_code == 200:
            logger.info("✓ Backend service is healthy")
        else:
            logger.warning(f"Backend service returned status {response.status_code}")
    except Exception as e:
        logger.error(f"✗ Cannot connect to backend service: {e}")
        logger.error("Make sure the backend service is running (python start_backend.py)")
        sys.exit(1)

    # Import and run the MCP server
    try:
        from mcp_server import mcp

        logger.info("Starting MCP server with HTTP/SSE transport...")
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")

    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        logger.error("Install MCP dependencies:")
        logger.error("  uv pip install -e '.[mcp]'")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# Made with Bob
