"""
Backend Service for CSA Assessment Reports.

This service uses Pydantic v1 and provides REST API endpoints for all tool operations.
It acts as the backend for the MCP server, handling all SharePoint and Excel processing.
"""

import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.src.models.inputs import (
    ListAssessmentReportsInput,
    GetAssessmentSheetInput,
    GetAssessmentSheetNamesInput,
    GetAssessmentExecutiveSummaryInput,
    GetMasterReportSummaryInput,
    ParseSharePointURLInput,
)
from backend.src.models.internal import SharePointSiteConfig
from backend.src.services import AssessmentReportService, MasterReportService, SharePointURLParser
from backend.src.sharepoint import SharePointClient, FileDiscoveryService, CacheManager
from backend.settings import Settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="CSA Assessment Reports Backend Service",
    description="Backend service for MCP server - handles SharePoint and Excel processing",
    version="0.1.0",
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services (initialized on startup)
assessment_service: Optional[AssessmentReportService] = None
master_report_service: Optional[MasterReportService] = None
url_parser: Optional[SharePointURLParser] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global assessment_service, master_report_service, url_parser

    logger.info("Initializing backend service...")

    try:
        # Load settings
        settings = Settings()

        # Initialize SharePoint site configurations
        site_configs = [
            SharePointSiteConfig(
                site_id=settings.csa_sharepoint_site_id,
                site_name="Primary SharePoint Site",
                site_type="primary",
            ),
            *[
                SharePointSiteConfig(
                    site_id=site.site_id,
                    site_name=site.site_name,
                    site_type="assessment",
                )
                for site in settings.csa_reports_sharepoint_sites
            ],
        ]

        # Initialize cache manager
        # Force local cache for development (S3 cache causes 80s+ timeouts that exceed MCP's 60s limit)
        cache_manager = CacheManager(cache_ttl_hours=4, use_s3=False)
        logger.info("Cache manager initialized with local cache (use_s3=False)")

        # Initialize SharePoint client
        sp_client = SharePointClient(
            tenant_id=settings.csa_azure_tenant_id,
            client_id=settings.csa_azure_client_id,
            client_secret=settings.csa_azure_client_secret,
            site_configs=site_configs,
            cache_manager=cache_manager,
        )

        # Initialize discovery service
        discovery_service = FileDiscoveryService(sp_client)

        # Initialize services
        assessment_service = AssessmentReportService(sp_client, discovery_service)
        master_report_service = MasterReportService(sp_client, discovery_service)
        url_parser = SharePointURLParser(sp_client)

        logger.info("Backend service initialized successfully")

    except Exception as e:
        logger.exception("Failed to initialize backend service during startup: %s", e)
        raise


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "csa-assessment-backend", "version": "0.1.0"}


@app.post("/api/list_assessment_reports")
async def list_assessment_reports(request: ListAssessmentReportsInput):
    """
    List assessment reports with optional filtering.

    Args:
        request: Assessment report filter parameters

    Returns:
        JSON response with list of reports
    """
    try:
        logger.info(f"list_assessment_reports called with: {request.dict()}")

        if assessment_service is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Call service
        output = assessment_service.list_reports(request)

        # Return as dict
        return output.dict()

    except Exception as e:
        logger.exception("Error in list_assessment_reports with request=%s: %s", request.dict(), e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/get_assessment_summary_metrics")
async def get_assessment_summary_metrics(request: GetAssessmentExecutiveSummaryInput):
    """
    Get structured summary metrics from an assessment report.

    Args:
        request: Assessment report identification parameters

    Returns:
        JSON response with executive summary data
    """
    try:
        logger.info(f"get_assessment_summary_metrics called with: {request.dict()}")

        if assessment_service is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Call service
        output = assessment_service.get_executive_summary(request)

        # Return as dict
        return output.dict()

    except Exception as e:
        logger.exception("Error in get_assessment_summary_metrics with request=%s: %s", request.dict(), e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/get_assessment_sheet")
async def get_assessment_sheet(request: GetAssessmentSheetInput):
    """
    Get a sheet from an assessment report with pagination.

    Args:
        request: Assessment sheet request parameters

    Returns:
        JSON response with sheet data
    """
    try:
        logger.info(f"get_assessment_sheet called with: {request.dict()}")

        if assessment_service is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Call service
        output = assessment_service.get_sheet(request)

        # Return as dict
        return output.dict()

    except Exception as e:
        logger.exception("Error in get_assessment_sheet with request=%s: %s", request.dict(), e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/get_assessment_sheet_names")
async def get_assessment_sheet_names(request: GetAssessmentSheetNamesInput):
    """
    Get list of sheet names from an assessment report.

    Args:
        request: Assessment sheet names request parameters

    Returns:
        JSON response with list of sheet names
    """
    try:
        logger.info(f"get_assessment_sheet_names called with: {request.dict()}")

        if assessment_service is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Call service
        output = assessment_service.get_sheet_names(request)

        # Return as dict
        return output.dict()

    except Exception as e:
        logger.exception("Error in get_assessment_sheet_names with request=%s: %s", request.dict(), e)
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/get_master_report_summary")
async def get_master_report_summary(request: GetMasterReportSummaryInput):
    """
    Get master report summary with optional filtering.

    Args:
        request: Master report summary parameters

    Returns:
        JSON response with master report data
    """
    try:
        logger.info(f"get_master_report_summary called with: {request.dict()}")

        if master_report_service is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Call service
        output = master_report_service.get_summary(request)

        # Return as dict
        return output.dict()

    except Exception as e:
        logger.exception("Error in get_master_report_summary with request=%s: %s", request.dict(), e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/parse_sharepoint_url")
async def parse_sharepoint_url(request: ParseSharePointURLInput):
    """
    Parse a SharePoint URL to extract file information.

    Args:
        request: SharePoint URL parsing parameters

    Returns:
        JSON response with parsed URL information
    """
    try:
        logger.info(f"parse_sharepoint_url called with: {request.dict()}")

        if url_parser is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Call service
        output = url_parser.parse(request)

        # Return as dict
        return output.dict()

    except Exception as e:
        logger.exception("Error in parse_sharepoint_url with request=%s: %s", request.dict(), e)
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.exception("Unhandled exception for path=%s method=%s: %s", request.url.path, request.method, exc)
    return JSONResponse(status_code=500, content={"error": str(exc), "type": type(exc).__name__})


if __name__ == "__main__":
    # This will be run via uvicorn command or start_backend.py script
    # Not meant to be run directly
    logger.info("Please use 'python start_backend.py' or 'uvicorn backend_service:app' to start the service")


# Made with Bob
