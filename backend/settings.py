"""Settings configuration for CSA Assessment Reports MCP Server."""

import json
from typing import List

from pydantic import BaseSettings, validator

from backend.src.models.internal import SharePointSiteConfig


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Settings are loaded from environment variables first, then from .env file if it exists.
    The .env file is optional - if not present, only environment variables will be used.
    This allows the service to work in Lambda where env vars are set directly.
    
    In Pydantic v1, BaseSettings will:
    1. First check environment variables
    2. Then check .env file if it exists (won't fail if missing)
    3. Use default values if neither is found
    """

    csa_azure_tenant_id: str
    csa_azure_client_id: str
    csa_azure_client_secret: str
    csa_sharepoint_site_id: str
    csa_reports_sharepoint_sites: List[SharePointSiteConfig]

    @validator("csa_reports_sharepoint_sites", pre=True)
    def parse_reports_sharepoint_sites(cls, value):
        """Parse assessment SharePoint sites from JSON environment variable."""
        if isinstance(value, str):
            return json.loads(value)
        return value

    class Config:
        """Pydantic configuration.
        
        The env_file is optional - Pydantic v1 BaseSettings will not fail if the file
        doesn't exist. It will simply skip loading from the file and use environment
        variables directly, which is perfect for Lambda deployments.
        """

        env_file = ".env"  # Changed from "../.env" to ".env" (correct path)
        env_file_encoding = "utf-8"
        case_sensitive = False


# Made with Bob
