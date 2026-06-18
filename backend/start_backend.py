#!/usr/bin/env python3
"""
Startup script for the backend service.

This script starts the FastAPI backend service that uses Pydantic v1.
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to Python path so 'backend' package can be imported
# This allows imports like 'from backend.src.services import ...'
parent_dir = str(Path(__file__).parent.parent.resolve())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Start the backend service.
    
    Note: Explicit .env loading is optional here since Pydantic BaseSettings
    will automatically load from .env if it exists. However, we keep this
    for early validation and clearer logging during local development.
    In Lambda, environment variables are set directly, so this won't run.
    """
    from dotenv import load_dotenv

    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        logger.info(f"Loading environment from {env_file}")
        load_dotenv(env_file)
    else:
        logger.info(f".env file not found at {env_file}, will use environment variables only")

    # Get configuration
    port = int(os.getenv("BACKEND_SERVICE_PORT", "8000"))
    host = os.getenv("BACKEND_SERVICE_HOST", "0.0.0.0")

    logger.info("=" * 60)
    logger.info("Starting CSA Assessment Reports Backend Service")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Using Pydantic v1")
    logger.info("=" * 60)

    # Check required environment variables
    required_vars = [
        "CSA_AZURE_TENANT_ID",
        "CSA_AZURE_CLIENT_ID",
        "CSA_AZURE_CLIENT_SECRET",
        "CSA_SHAREPOINT_SITE_ID",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these in your .env file")
        sys.exit(1)

    # Import uvicorn here to avoid import errors if not installed
    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn not installed. Install backend dependencies:")
        logger.error("  uv pip install -e '.[backend]'")
        sys.exit(1)

    # Start the server
    try:
        uvicorn.run(
            "backend_service:app",
            host=host,
            port=port,
            log_level="info",
            reload=False,  # Set to True for development
        )
    except KeyboardInterrupt:
        logger.info("Backend service stopped by user")
    except Exception as e:
        logger.error(f"Failed to start backend service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# Made with Bob
