"""
MCP Server for CSA Assessment Reports using fastmcp.

This server uses Pydantic v2 and acts as a thin wrapper that proxies requests
to the backend service (which uses Pydantic v1).
"""

import logging
import os
from typing import Any, Dict
import httpx
from fastmcp import FastMCP

from mcp_models import (
    ListAssessmentReportsInput,
    GetAssessmentSheetInput,
    GetAssessmentSheetNamesInput,
    GetAssessmentExecutiveSummaryInput,
    GetMasterReportSummaryInput,
    ParseSharePointURLInput,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Get backend service URL from environment
BACKEND_SERVICE_URL = os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000")

# Create FastMCP server
mcp = FastMCP("CSA Assessment Reports")

# HTTP client for backend communication
http_client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout for large files


async def call_backend(endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call backend service endpoint.

    Args:
        endpoint: API endpoint path (e.g., "/api/list_assessment_reports")
        data: Request data dictionary

    Returns:
        Response data dictionary

    Raises:
        Exception: If backend call fails
    """
    url = f"{BACKEND_SERVICE_URL}{endpoint}"

    try:
        logger.info(f"Calling backend: {url}")
        response = await http_client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"Backend HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Backend error: {e.response.text}")

    except httpx.RequestError as e:
        logger.error(f"Backend request error: {e}")
        raise Exception(f"Failed to connect to backend service: {e}")


@mcp.tool()
async def list_assessment_reports(
    org_id: str,
    payer_account_id: str,
    year: int,
    month: int,
    org_name: str | None = None,
    ri_purchase_option: str | None = None,
) -> str:
    """
    List all assessment reports for a specific organization, payer account, and time period.

    This tool discovers available assessment reports in SharePoint based on organization
    and time filters. Use it to find reports when you know the organization details but
    don't have a specific file URL.

    Use this tool when:
    - User asks "what reports are available for org X?"
    - You need to find reports for a specific time period
    - User wants to see all assessments for a payer account
    - You need to discover file_id for subsequent tool calls

    Returns list of reports with:
    - file_id: Use this in get_assessment_summary_metrics or get_assessment_sheet
    - file_name: Human-readable report name
    - org_id, org_name: Organization identifiers
    - payer_account_id: AWS payer account
    - year, month: Report time period
    - jira_ticket: Associated JIRA ticket

    Example workflow:
    1. User: "Show me all reports for org ABC123 in January 2024"
    2. Call list_assessment_reports with org_id, payer_account_id, year=2024, month=1
    3. Use returned file_id in get_assessment_summary_metrics for detailed data

    Args:
        org_id: Organization ID (REQUIRED)
        payer_account_id: AWS payer account ID (REQUIRED)
        year: Year of the report (REQUIRED, 2020-2030)
        month: Month of the report (REQUIRED, 1-12)
        org_name: Optional organization name for context
        ri_purchase_option: Optional RI purchase option filter

    Returns:
        JSON string with list of matching assessment reports and their metadata
    """
    try:
        # Validate input
        input_data = ListAssessmentReportsInput(
            org_id=org_id,
            org_name=org_name,
            payer_account_id=payer_account_id,
            year=year,
            month=month,
            ri_purchase_option=ri_purchase_option,
        )

        # Call backend
        result = await call_backend("/api/list_assessment_reports", input_data.model_dump(exclude_none=True))

        # Return as formatted JSON string
        import json

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error in list_assessment_reports: {e}")
        import json

        return json.dumps({"error": str(e), "tool": "list_assessment_reports"}, indent=2)


@mcp.tool()
async def get_assessment_summary_metrics(
    file_id: str,
    org_id: str | None = None,
    sharepoint_site_name: str | None = None,
) -> str:
    """
    Get executive summary metrics and key insights from an assessment report.

    This tool extracts high-level summary data, analyzed facts, SI performance metrics,
    current commitments, and key recommendations from an assessment report. Use it to get
    a comprehensive overview without diving into detailed sheets.

    The executive summary includes:
    - Structured metrics (current_metrics, edp_discounts, coverage_metrics, etc.)
    - Analyzed facts (savings opportunities, coverage levels, discount rates)
    - SI performance data (Savings Plans and Reserved Instances utilization)
    - Current commitments (active Savings Plans and RIs)
    - Key recommendations (Day 1 optimizations, non-EC2 analysis)

    Use this tool when:
    - User asks for "high-level summary" or "executive summary"
    - You need key metrics and recommendations
    - User wants to understand overall assessment findings
    - You need structured data rather than raw sheet content

    NOTE: This returns STRUCTURED metrics, not the raw 'Executive Summary' sheet.
    Use get_assessment_sheet with sheet_name='Executive Summary' for the raw sheet.

    Workflow:
    1. Get file_id from parse_sharepoint_url (if user provided URL)
       OR from list_assessment_reports (if searching by org/time)
    2. Call this tool with the file_id
    3. Present structured summary to user

    Optional lookup hints can speed up file-id resolution:
    - Provide sharepoint_site_name to prioritize a matching assessment site first
    - Otherwise provide org_id to use org-based site ordering

    Args:
        file_id: SharePoint file ID from parse_sharepoint_url or list_assessment_reports (REQUIRED)
        org_id: Optional organization ID hint for faster lookup
        sharepoint_site_name: Optional site name hint for faster lookup

    Returns:
        JSON string with executive summary containing metrics, facts, performance data, and recommendations
    """
    try:
        # Validate input
        input_data = GetAssessmentExecutiveSummaryInput(
            file_id=file_id,
            org_id=org_id,
            sharepoint_site_name=sharepoint_site_name,
        )

        # Call backend
        result = await call_backend("/api/get_assessment_summary_metrics", input_data.model_dump(exclude_none=True))

        # Return as formatted JSON string
        import json

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error in get_assessment_summary_metrics: {e}")
        import json

        return json.dumps({"error": str(e), "tool": "get_assessment_summary_metrics"}, indent=2)


@mcp.tool()
async def get_assessment_sheet(
    file_id: str,
    sheet_name: str,
    org_id: str | None = None,
    sharepoint_site_name: str | None = None,
    page: int = 1,
    page_size: int = 1000,
    format: str = "csv",
) -> str:
    """
    Get detailed data from a specific sheet within an assessment report.

    This tool extracts tabular data from individual sheets in the assessment Excel file.
    Use it when you need detailed, granular data beyond the executive summary.

    Available sheets typically include:
    - "Analyzed Facts": Detailed metrics and calculations
    - "SI Performance": Savings Instruments performance breakdown
    - "Day 1 - Optimizations": Immediate optimization opportunities
    - "non_ec2_analysis": Non-EC2 service analysis
    - "Executive Summary": Formatted summary sheet (raw content)
    - CSV sheets: savings_plans.csv, reserved_instances.csv, compute_usage.csv, etc.

    Use this tool when:
    - User asks for "detailed data" from a specific sheet
    - You need granular information not in the executive summary
    - User wants to see raw data or specific calculations
    - You need to access CSV data embedded in the report

    Workflow:
    1. Get file_id from parse_sharepoint_url or list_assessment_reports
    2. Call this tool with file_id and sheet_name
    3. Optionally paginate through results if dataset is large (use page parameter)

    Optional lookup hints can speed up file-id resolution:
    - Provide sharepoint_site_name to prioritize a matching assessment site first
    - Otherwise provide org_id to use org-based site ordering

    Args:
        file_id: SharePoint file ID (REQUIRED)
        sheet_name: Name of the sheet to extract (REQUIRED)
        org_id: Optional organization ID hint
        sharepoint_site_name: Optional site name hint
        page: Page number for pagination (default: 1)
        page_size: Number of rows per page (default: 1000, max: 5000)
        format: Return format - 'csv' or 'json' (default: 'csv')

    Returns:
        JSON string with sheet data, rows, pagination info, and metadata
    """
    try:
        # Validate input
        input_data = GetAssessmentSheetInput(
            file_id=file_id,
            org_id=org_id,
            sharepoint_site_name=sharepoint_site_name,
            sheet_name=sheet_name,
            page=page,
            page_size=page_size,
            format=format,  # type: ignore
        )

        # Call backend
        result = await call_backend("/api/get_assessment_sheet", input_data.model_dump(exclude_none=True))

        # Return as formatted JSON string
        import json

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error in get_assessment_sheet: {e}")
        import json


@mcp.tool()
async def get_assessment_sheet_names(
    file_id: str,
    org_id: str | None = None,
    sharepoint_site_name: str | None = None,
) -> str:
    """
    Get the list of all sheet names available in an assessment report.

    This tool returns a complete list of all sheets (tabs) present in an assessment
    Excel file. Use it to discover what data is available before requesting specific
    sheets with get_assessment_sheet.

    Use this tool when:
    - User asks "what sheets are in this report?"
    - You need to discover available data before extraction
    - User wants to know what information is available
    - You need to validate a sheet name exists before calling get_assessment_sheet

    Returns:
    - List of all sheet names in the Excel file
    - Total count of sheets
    - Report metadata (file_id, file_name, org_id)

    Example workflow:
    1. Get file_id from parse_sharepoint_url or list_assessment_reports
    2. Call this tool with the file_id to see available sheets
    3. Use get_assessment_sheet with a specific sheet_name to get data

    Optional lookup hints can speed up file-id resolution:
    - Provide sharepoint_site_name to prioritize a matching assessment site first
    - Otherwise provide org_id to use org-based site ordering

    Args:
        file_id: SharePoint file ID from parse_sharepoint_url or list_assessment_reports (REQUIRED)
        org_id: Optional organization ID hint for faster lookup
        sharepoint_site_name: Optional site name hint for faster lookup

    Returns:
        JSON string with list of sheet names, total count, and report metadata
    """
    try:
        # Validate input
        input_data = GetAssessmentSheetNamesInput(
            file_id=file_id,
            org_id=org_id,
            sharepoint_site_name=sharepoint_site_name,
        )

        # Call backend
        result = await call_backend("/api/get_assessment_sheet_names", input_data.model_dump(exclude_none=True))

        # Return as formatted JSON string
        import json

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error in get_assessment_sheet_names: {e}")
        import json

        return json.dumps({"error": str(e), "tool": "get_assessment_sheet_names"}, indent=2)

        return json.dumps({"error": str(e), "tool": "get_assessment_sheet"}, indent=2)


@mcp.tool()
async def get_master_report_summary(
    file_id: str,
    site_id: str | None = None,
    category: str | None = None,
) -> str:
    """
    Get summary information from a master report containing multiple payer accounts.

    Master reports aggregate data across multiple payer accounts for an organization.
    This tool extracts high-level summary information for all payers or a specific category.

    Use this tool when:
    - User provides a master report URL
    - User asks for "summary across all payers"
    - You need organization-wide assessment data
    - User wants to see consolidated metrics for multiple accounts

    Master report workflow (IMPORTANT):
    1. User provides master report SharePoint URL
    2. Call parse_sharepoint_url to get file_id and site_id
    3. Call this tool with the file_id (and optionally site_id)
    4. Optionally filter by category for specific payer accounts

    Returns summary with:
    - Organization-level metrics
    - Per-payer account summaries
    - Aggregated savings opportunities
    - Cross-account insights
    - Consolidated recommendations

    Args:
        file_id: SharePoint file ID from parse_sharepoint_url (REQUIRED)
        site_id: Optional site ID hint from parse_sharepoint_url (speeds up lookup)
        category: Optional category filter for specific payer accounts

    Returns:
        JSON string with master report summary containing organization and payer-level data
    """
    try:
        # Validate input
        input_data = GetMasterReportSummaryInput(
            file_id=file_id,
            site_id=site_id,
            category=category,
        )

        # Call backend
        result = await call_backend("/api/get_master_report_summary", input_data.model_dump(exclude_none=True))

        # Return as formatted JSON string
        import json

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error in get_master_report_summary: {e}")
        import json

        return json.dumps({"error": str(e), "tool": "get_master_report_summary"}, indent=2)


@mcp.tool()
async def parse_sharepoint_url(
    url: str,
    return_type: str = "metadata",
) -> str:
    """
    Parse a SharePoint URL to extract file identification information.

    This tool extracts file_id, site_id, and file_name from SharePoint URLs. It should be
    the FIRST tool called when a user provides a SharePoint URL for any assessment report
    or master report.

    Use this tool when:
    - User provides a SharePoint URL
    - You need to identify a file before accessing its contents
    - Starting any workflow that involves SharePoint files
    - You need file_id for subsequent tool calls

    Returns:
    - file_id: Unique identifier for the file (use in subsequent tool calls)
    - site_id: SharePoint site identifier (optional hint for faster lookups)
    - file_name: Name of the file
    - url_type: Type of URL (direct or sharing link)
    - report_type: Whether it's an assessment or master report

    Example workflow:
    1. User: "Here's the assessment report: https://..."
    2. Call parse_sharepoint_url with the URL
    3. Use returned file_id in get_assessment_summary_metrics or get_assessment_sheet

    Master report workflow:
    1. User: "Analyze this master report: https://..."
    2. Call parse_sharepoint_url with the URL
    3. Use returned file_id in get_master_report_summary

    Supports both sharing links and direct file URLs from SharePoint.

    Args:
        url: SharePoint URL (sharing link or direct file URL) (REQUIRED)
        return_type: Type of data to return - 'metadata' (default), 'executive_summary', or 'full'

    Returns:
        JSON string with file_id, site_id, file_name, url_type, and report_type
    """
    try:
        # Validate input
        input_data = ParseSharePointURLInput(
            url=url,
            return_type=return_type,  # type: ignore
        )

        # Call backend
        result = await call_backend("/api/parse_sharepoint_url", input_data.model_dump(exclude_none=True))

        # Return as formatted JSON string
        import json

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error in parse_sharepoint_url: {e}")
        import json

        return json.dumps({"error": str(e), "tool": "parse_sharepoint_url"}, indent=2)


# Cleanup on shutdown
# Note: on_shutdown decorator is not available in all FastMCP versions
# We'll handle cleanup gracefully if supported, otherwise rely on Python's cleanup
async def cleanup():
    """Cleanup resources on shutdown."""
    await http_client.aclose()
    logger.info("MCP server shutdown complete")

# Try to register shutdown handler if supported
on_shutdown_decorator = getattr(mcp, 'on_shutdown', None)
if on_shutdown_decorator is not None:
    cleanup = on_shutdown_decorator(cleanup)
    logger.info("Registered shutdown handler")
else:
    # Fallback: cleanup will happen via Python's normal cleanup mechanisms
    logger.info("FastMCP on_shutdown not available - using default cleanup")


if __name__ == "__main__":
    # Get port from environment
    port = int(os.getenv("MCP_SERVER_PORT", "3000"))

    logger.info(f"Starting MCP server on port {port}")
    logger.info(f"Backend service URL: {BACKEND_SERVICE_URL}")

    # Run the server with HTTP transport
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")


# Made with Bob
