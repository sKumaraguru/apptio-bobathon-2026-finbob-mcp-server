"""
Lambda handler for CSA Assessment Reports Backend Service.

This module adapts the FastAPI application to run on AWS Lambda using Mangum.
"""
import sys
import os

# Add package root to path so unzip_requirements can be found
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import unzip_requirements  # noqa: F401

from mangum import Mangum
from backend.backend_service import app

# Lambda handler with Mangum adapter
# lifespan="on" enables FastAPI startup events to initialize services
handler = Mangum(app, lifespan="on")

# Made with Bob
