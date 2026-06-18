"""Input models for MCP tools using Pydantic v1."""

from pydantic import BaseModel, Field, validator
from typing import Optional, Literal


class ListAssessmentReportsInput(BaseModel):
    """Input for list_assessment_reports tool."""

    org_id: str = Field(..., description="Organization ID")
    org_name: Optional[str] = Field(None, description="Organization name (partial match)")
    payer_account_id: str = Field(..., description="AWS payer account ID")
    year: int = Field(..., ge=2020, le=2030, description="Year")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
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
    category: Optional[str] = Field(None, description="Optional category filter")


class ParseSharePointURLInput(BaseModel):
    """Input for parse_sharepoint_url tool."""

    url: str = Field(..., description="SharePoint URL to parse")
    return_type: Literal["metadata", "executive_summary", "full"] = Field(
        "metadata", description="Type of data to return"
    )

    @validator("url")
    def validate_url(cls, v):
        """Validate that URL is a valid SharePoint URL."""
        if not v.startswith("https://") or "sharepoint.com" not in v:
            raise ValueError("Must be a valid SharePoint URL")
        return v


# Made with Bob
