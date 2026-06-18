"""Output models for MCP tools using Pydantic v1."""

from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any, Union
from datetime import datetime


class ReportMetadata(BaseModel):
    """Metadata for an assessment report."""

    file_id: Optional[str] = None  # SharePoint file ID
    file_name: str
    org_id: str
    org_name: str
    payer_account_id: str
    year: int
    month: int
    ri_purchase_option: str
    version_timestamp: datetime
    file_path: str
    file_size_bytes: int
    sharepoint_site_id: str
    sharepoint_site_name: str


class ListAssessmentReportsOutput(BaseModel):
    """Output for list_assessment_reports tool."""

    reports: List[ReportMetadata]
    total_count: int
    filters_applied: Dict[str, Any]


class PaginationMetadata(BaseModel):
    """Pagination information."""

    page: int
    page_size: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool


class SheetMetadata(BaseModel):
    """Metadata about a sheet."""

    total_rows: int
    total_columns: int
    has_headers: bool
    data_type: Literal["csv", "formatted", "empty"]
    column_names: Optional[List[str]] = None


class GetAssessmentSheetOutput(BaseModel):
    """Output for get_assessment_sheet tool."""

    report_metadata: Dict[str, Any]
    sheet_metadata: SheetMetadata
    pagination: PaginationMetadata
    data: Union[str, List[Dict[str, Any]]]  # CSV string or JSON array
    format: Literal["csv", "json"]

class GetAssessmentSheetNamesOutput(BaseModel):
    """Output for get_assessment_sheet_names tool."""

    report_metadata: Dict[str, Any]
    sheet_names: List[str]
    total_sheets: int



class AnalyzedFacts(BaseModel):
    """Key facts from Analyzed Facts sheet."""

    total_public_pricing_cost: Optional[float] = None
    current_coverage: Optional[float] = None
    savings_model_1: Optional[float] = None
    net_effective_discount_model_1: Optional[float] = None
    stable_workload_percentage: Optional[float] = None
    additional_savings: Optional[float] = None
    non_ec2_savings_1yr_ris: Optional[float] = None
    non_ec2_savings_3yr_ris: Optional[float] = None
    current_coverage_percentage: Optional[float] = None
    dh_coverage: Optional[float] = None
    net_effective_discount_current_state: Optional[float] = None
    fluctuation_workload_percentage: Optional[float] = None


class SIPerformance(BaseModel):
    """SI Performance metrics."""

    type: str
    class_: str = Field(..., alias="class")
    term: str
    covered_cost: float
    actual_cost: float
    discount: float
    utilization: float
    coverage: float

    class Config:
        allow_population_by_field_name = True


class SavingsPlan(BaseModel):
    """Savings Plan details."""

    offering_type: str
    payment_option: str
    term: str
    end_date: str
    monthly_commitment: float
    hourly_commitment: Optional[float] = None
    amortized_fee: Optional[float] = None


class ReservedInstance(BaseModel):
    """Reserved Instance details."""

    product_region: str
    offering_type: str
    purchase_option: str
    term: str
    end_date: str
    instance_type: Optional[str] = None
    instance_count: Optional[int] = None
    hourly_fee: Optional[float] = None
    monthly_fee: float


class ExecutiveSummaryData(BaseModel):
    """
    Executive summary structured data.
    
    The executive_summary_sections field contains a well-structured dictionary
    organized by section with semantic keys and logical groupings:
    
    Structure:
    {
        "summary": {
            "current_metrics": {
                "unused_contract_cost": float,
                "primary_regions_cost": float,
                "compute_hourly_pattern": str,
                ...
            },
            "edp_discounts": {
                "on_demand_usage": float,
                "ri_fees": float,
                "compute_sp_fees": float,
                ...
            },
            "coverage_metrics": {
                "max_savings_level": float,
                "average_coverage": float,
                "current_coverage": float,
                ...
            },
            "workload_analysis": {
                "stable_workload_percentage": float,
                "fluctuation_workload_percentage": float,
                ...
            }
        },
        "spot": {
            "discount_metrics": {
                "with_edp": float,
                "net_effective_discount": float,
                "projected_net_effective_discount": float,
                ...
            },
            "commitment_analysis": {
                "additional_commitment_per_hour": float,
                "additional_commitment_per_month": float,
                ...
            },
            "flexibility_metrics": {
                "commitment_cash_flow_flexibility_as_is": float,
                "commitment_cash_flow_flexibility": float,
                ...
            }
        }
    }
    
    Each metric has a descriptive key name and consistent data type.
    Related metrics are grouped together for easier AI agent consumption.
    """

    executive_summary_sections: Dict[str, Any] = Field(default_factory=dict)
    analyzed_facts: AnalyzedFacts
    si_performance: List[SIPerformance]
    current_commitments: Dict[str, Any]
    key_recommendations: Dict[str, Any]


class GetAssessmentExecutiveSummaryOutput(BaseModel):
    """Output for get_assessment_executive_summary tool."""

    report_metadata: Dict[str, Any]
    executive_summary: ExecutiveSummaryData
    sheets_included: List[str]


class MasterReportAccount(BaseModel):
    """Account data from Master Report."""

    org_id: str
    org_name: str
    account_id: str
    category: str
    currency_code: str
    savings_metrics: Dict[str, Any]
    cost_metrics: Dict[str, Any]
    coverage_metrics: Dict[str, Any]
    discount_metrics: Dict[str, Any]
    workload_metrics: Dict[str, Any]
    report_quality: Dict[str, Any]
    urls: Dict[str, Any]


class GetMasterReportSummaryOutput(BaseModel):
    """Output for get_master_report_summary tool."""

    master_report_metadata: Dict[str, Any]
    accounts: List[MasterReportAccount]
    summary_statistics: Dict[str, Any]


class SharePointURLInfo(BaseModel):
    """Parsed SharePoint URL information."""

    url_type: Literal["sharing_link", "direct_file_url"]
    site_id: str
    file_id: Optional[str] = None  # SharePoint file ID
    file_path: str
    file_name: str
    is_master_report: bool
    is_assessment_report: bool


class ParseSharePointURLOutput(BaseModel):
    """Output for parse_sharepoint_url tool."""

    url_info: SharePointURLInfo
    report_metadata: Dict[str, Any]
    file_info: Dict[str, Any]


# Made with Bob
