"""MCP tool implementations for CSA Assessment Reports."""

from typing import Any, Dict
import json

from ..models.inputs import (
    ListAssessmentReportsInput,
    GetAssessmentSheetInput,
    GetAssessmentSheetNamesInput,
    GetAssessmentExecutiveSummaryInput,
    GetMasterReportSummaryInput,
    ParseSharePointURLInput,
)
from ..services import AssessmentReportService, MasterReportService, SharePointURLParser


class MCPTools:
    """
    MCP tool handlers for assessment reports.

    Implements all 5 MCP tools:
    - list_assessment_reports
    - get_assessment_executive_summary
    - get_assessment_sheet
    - get_master_report_summary
    - parse_sharepoint_url
    """

    def __init__(
        self,
        assessment_service: AssessmentReportService,
        master_report_service: MasterReportService,
        url_parser: SharePointURLParser,
    ):
        """
        Initialize MCP tools.

        Args:
            assessment_service: Assessment report service instance
            master_report_service: Master report service instance
            url_parser: URL parser service instance
        """
        self.assessment_service = assessment_service
        self.master_report_service = master_report_service
        self.url_parser = url_parser

    def list_assessment_reports(self, arguments: Dict[str, Any]) -> str:
        """
        List assessment reports with optional filtering.

        Args:
            arguments: Tool arguments dictionary

        Returns:
            JSON string with list of reports
        """
        try:
            # Validate input
            input_data = ListAssessmentReportsInput(**arguments)

            # Call service
            output = self.assessment_service.list_reports(input_data)

            # Return as JSON
            return json.dumps(output.dict(), indent=2, default=str)

        except Exception as e:
            return json.dumps({"error": str(e), "tool": "list_assessment_reports"}, indent=2)

    def get_assessment_summary_metrics(self, arguments: Dict[str, Any]) -> str:
        """
        Get structured summary metrics from an assessment report.

        Note: This extracts structured data from multiple sheets (Analyzed Facts,
        SI Performance, etc.), NOT the formatted 'Executive Summary' sheet.
        Use get_assessment_sheet with sheet_name='Executive Summary' for that.

        Args:
            arguments: Tool arguments dictionary

        Returns:
            JSON string with executive summary data
        """
        try:
            # Validate input
            input_data = GetAssessmentExecutiveSummaryInput(**arguments)

            # Call service
            output = self.assessment_service.get_executive_summary(input_data)

            # Return as JSON
            return json.dumps(output.dict(), indent=2, default=str)

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "tool": "get_assessment_executive_summary",
                    "hint": "Make sure the report exists. Use list_assessment_reports to find available reports.",
                },
                indent=2,
            )

    def get_assessment_sheet(self, arguments: Dict[str, Any]) -> str:
        """
        Get a sheet from an assessment report with pagination.

        Args:
            arguments: Tool arguments dictionary

        Returns:
            JSON string with sheet data (CSV or JSON format)
        """
        try:
            # Validate input
            input_data = GetAssessmentSheetInput(**arguments)

            # Call service
            output = self.assessment_service.get_sheet(input_data)

            # Return as JSON
            return json.dumps(output.dict(), indent=2, default=str)

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "tool": "get_assessment_sheet",
                    "hint": "Check that file_id and sheet_name are correct. Use list_assessment_reports to find file_id.",
                },
                indent=2,
            )

    def get_assessment_sheet_names(self, arguments: Dict[str, Any]) -> str:
        """
        Get list of sheet names from an assessment report.

        Args:
            arguments: Tool arguments dictionary

        Returns:
            JSON string with list of sheet names
        """
        try:
            # Validate input
            input_data = GetAssessmentSheetNamesInput(**arguments)

            # Call service
            output = self.assessment_service.get_sheet_names(input_data)

            # Return as JSON
            return json.dumps(output.dict(), indent=2, default=str)

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "tool": "get_assessment_sheet_names",
                    "hint": "Check that file_id is correct. Use list_assessment_reports to find file_id.",
                },
                indent=2,
            )

    def get_master_report_summary(self, arguments: Dict[str, Any]) -> str:
        """
        Get master report summary with optional filtering.

        Args:
            arguments: Tool arguments dictionary

        Returns:
            JSON string with master report data
        """
        try:
            # Validate input
            input_data = GetMasterReportSummaryInput(**arguments)

            # Call service
            output = self.master_report_service.get_summary(input_data)

            # Return as JSON
            return json.dumps(output.dict(), indent=2, default=str)

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "tool": "get_master_report_summary",
                    "hint": "Make sure a master report exists for the specified year and month.",
                },
                indent=2,
            )

    def parse_sharepoint_url(self, arguments: Dict[str, Any]) -> str:
        """
        Parse a SharePoint URL to extract file information.

        Args:
            arguments: Tool arguments dictionary

        Returns:
            JSON string with parsed URL information
        """
        try:
            # Validate input
            input_data = ParseSharePointURLInput(**arguments)

            # Call service
            output = self.url_parser.parse(input_data)

            # Return as JSON
            return json.dumps(output.dict(), indent=2, default=str)

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "tool": "parse_sharepoint_url",
                    "hint": "Make sure the URL is a valid SharePoint URL (https://...sharepoint.com/...)",
                },
                indent=2,
            )

    def get_tool_definitions(self) -> list:
        """
        Get MCP tool definitions for registration.

        Returns:
            List of tool definition dictionaries
        """
        return [
            {
                "name": "list_assessment_reports",
                "description": "List available CSA assessment reports with optional filtering by organization, account, date, and RI purchase option.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "org_id": {"type": "string", "description": "Organization ID to filter by"},
                        "org_name": {"type": "string", "description": "Organization name (partial match)"},
                        "payer_account_id": {"type": "string", "description": "AWS payer account ID"},
                        "year": {
                            "type": "integer",
                            "description": "Year (2020-2030)",
                            "minimum": 2020,
                            "maximum": 2030,
                        },
                        "month": {"type": "integer", "description": "Month (1-12)", "minimum": 1, "maximum": 12},
                        "ri_purchase_option": {
                            "type": "string",
                            "description": "RI purchase option (e.g., 'No Upfront')",
                        },
                    },
                },
            },
            {
                "name": "get_assessment_summary_metrics",
                "description": "Get structured summary metrics from a CSA assessment report as JSON. Extracts data from multiple sheets: Analyzed Facts (key metrics), SI Performance, Savings Plans, Reserved Instances, and recommendations. NOTE: This does NOT return the formatted 'Executive Summary' sheet - use get_assessment_sheet with sheet_name='Executive Summary' for that raw sheet.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "SharePoint file ID from list_assessment_reports",
                        },
                        "org_id": {"type": "string", "description": "Organization ID hint for site lookup (optional)"},
                        "sharepoint_site_name": {"type": "string", "description": "SharePoint site name hint for site lookup (optional)"},
                    },
                    "required": ["file_id"],
                },
            },
            {
                "name": "get_assessment_sheet",
                "description": "Get the contents of any sheet from a CSA assessment report, with pagination support for large sheets. Returns CSV format by default.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "SharePoint file ID from list_assessment_reports",
                        },
                        "sheet_name": {
                            "type": "string",
                            "description": "Name of sheet to retrieve (e.g., 'compute_usage.csv', 'SI Performance')",
                        },
                        "page": {"type": "integer", "description": "Page number (1-based)", "default": 1, "minimum": 1},
                        "page_size": {
                            "type": "integer",
                            "description": "Rows per page (default: 1000, max: 5000)",
                            "default": 1000,
                            "minimum": 1,
                            "maximum": 5000,
                        },
                        "format": {
                            "type": "string",
                            "description": "Return format: 'csv' or 'json'",
                            "enum": ["csv", "json"],
                            "default": "csv",
                        },
                        "org_id": {"type": "string", "description": "Organization ID hint for site lookup (optional)"},
                        "sharepoint_site_name": {"type": "string", "description": "SharePoint site name hint for site lookup (optional)"},
                    },
                    "required": ["file_id", "sheet_name"],
                },
            },
            {
                "name": "get_assessment_sheet_names",
                "description": "Get the list of all sheet names available in a CSA assessment report. Use this to discover what sheets are available before calling get_assessment_sheet.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "SharePoint file ID from list_assessment_reports or parse_sharepoint_url",
                        },
                        "org_id": {"type": "string", "description": "Organization ID hint for site lookup (optional)"},
                        "sharepoint_site_name": {"type": "string", "description": "SharePoint site name hint for site lookup (optional)"},
                    },
                    "required": ["file_id"],
                },
            },
            {
                "name": "get_master_report_summary",
                "description": "Get summary from master report using file_id. Use parse_sharepoint_url first to get file_id from the SharePoint URL. Master reports contain consolidated data across multiple payer accounts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "SharePoint file ID of the master report (REQUIRED - get from parse_sharepoint_url)"
                        },
                        "site_id": {
                            "type": "string",
                            "description": "Optional SharePoint site ID hint (from parse_sharepoint_url)"
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional category filter for specific payer accounts"
                        },
                    },
                    "required": ["file_id"],
                },
            },
            {
                "name": "parse_sharepoint_url",
                "description": "Parse a SharePoint URL to extract file information and determine if it's a master report or assessment report. Supports both sharing links and direct file URLs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "SharePoint URL to parse"},
                        "return_type": {
                            "type": "string",
                            "description": "Type of data to return",
                            "enum": ["metadata", "executive_summary", "full"],
                            "default": "metadata",
                        },
                    },
                    "required": ["url"],
                },
            },
        ]


# Made with Bob
