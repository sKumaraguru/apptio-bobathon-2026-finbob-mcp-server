"""
Pydantic v2 models for MCP server.

These models mirror the v1 models in src/models/ but use Pydantic v2 syntax.
They are used only by the MCP server to avoid Pydantic version conflicts.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal
from datetime import datetime


# Input Models


class ListAssessmentReportsInput(BaseModel):
    """Input for list_assessment_reports tool."""

    org_id: str = Field(..., description="Organization ID to filter reports")
    org_name: Optional[str] = Field(None, description="Organization name (partial match)")
    payer_account_id: str = Field(..., description="AWS payer account ID to filter reports")
    year: int = Field(..., ge=2020, le=2030, description="Year to filter reports (2020-2030)")
    month: int = Field(..., ge=1, le=12, description="Month to filter reports (1-12)")
    ri_purchase_option: Optional[str] = Field(None, description="RI purchase option")


class GetAssessmentSheetInput(BaseModel):
    """Input for get_assessment_sheet tool."""

    file_id: str = Field(..., description="SharePoint file ID")
    org_id: Optional[str] = Field(None, description="Optional organization ID hint to prioritize assessment site lookup")
    sharepoint_site_name: Optional[str] = Field(
        None, description="Optional SharePoint site name hint to prioritize assessment site lookup"
    )
    sheet_name: str = Field(..., description="Name of sheet to retrieve")
    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(1000, ge=1, le=5000, description="Rows per page")
    format: Literal["csv", "json"] = Field("csv", description="Return format")


class GetAssessmentExecutiveSummaryInput(BaseModel):
    """Input for get_assessment_executive_summary tool."""

    file_id: str = Field(..., description="SharePoint file ID")
    org_id: Optional[str] = Field(None, description="Optional organization ID hint to prioritize assessment site lookup")
    sharepoint_site_name: Optional[str] = Field(
        None, description="Optional SharePoint site name hint to prioritize assessment site lookup"
    )

class GetAssessmentSheetNamesInput(BaseModel):
    """Input for get_assessment_sheet_names tool."""

    file_id: str = Field(..., description="SharePoint file ID")
    org_id: Optional[str] = Field(None, description="Optional organization ID hint to prioritize assessment site lookup")
    sharepoint_site_name: Optional[str] = Field(
        None, description="Optional SharePoint site name hint to prioritize assessment site lookup"
    )



class GetMasterReportSummaryInput(BaseModel):
    """Input for get_master_report_summary tool."""

    file_id: str = Field(..., description="SharePoint file ID of the master report")
    site_id: Optional[str] = Field(None, description="Optional SharePoint site ID hint (from parse_sharepoint_url)")
    category: Optional[str] = Field(None, description="Optional category filter for specific payer accounts")


class ParseSharePointURLInput(BaseModel):
    """Input for parse_sharepoint_url tool."""

    url: str = Field(..., description="SharePoint URL to parse")
    return_type: Literal["metadata", "executive_summary", "full"] = Field(
        "metadata", description="Type of data to return"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URL is a valid SharePoint URL."""
        if not v.startswith("https://") or "sharepoint.com" not in v:
            raise ValueError("Must be a valid SharePoint URL")
        return v


# Output Models (simplified - only what's needed for MCP responses)


class ToolResponse(BaseModel):
    """Generic tool response wrapper."""

    success: bool = True
    data: dict = Field(default_factory=dict)
    error: Optional[str] = None

    model_config = {
        "json_schema_extra": {"examples": [{"success": True, "data": {"reports": [], "total_count": 0}, "error": None}]}
    }


# Made with Bob
