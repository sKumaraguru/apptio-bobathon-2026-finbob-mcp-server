"""Data models for CSA Assessment Reports MCP Server."""

from .inputs import (
    ListAssessmentReportsInput,
    GetAssessmentSheetInput,
    GetAssessmentExecutiveSummaryInput,
    GetMasterReportSummaryInput,
    ParseSharePointURLInput,
)
from .outputs import (
    ReportMetadata,
    ListAssessmentReportsOutput,
    PaginationMetadata,
    SheetMetadata,
    GetAssessmentSheetOutput,
    AnalyzedFacts,
    SIPerformance,
    SavingsPlan,
    ReservedInstance,
    ExecutiveSummaryData,
    GetAssessmentExecutiveSummaryOutput,
    MasterReportAccount,
    GetMasterReportSummaryOutput,
    SharePointURLInfo,
    ParseSharePointURLOutput,
)
from .internal import (
    SharePointSiteConfig,
    CacheEntry,
    FileSearchPattern,
    ParsedFilename,
    SheetInfo,
)

__all__ = [
    # Input models
    "ListAssessmentReportsInput",
    "GetAssessmentSheetInput",
    "GetAssessmentExecutiveSummaryInput",
    "GetMasterReportSummaryInput",
    "ParseSharePointURLInput",
    # Output models
    "ReportMetadata",
    "ListAssessmentReportsOutput",
    "PaginationMetadata",
    "SheetMetadata",
    "GetAssessmentSheetOutput",
    "AnalyzedFacts",
    "SIPerformance",
    "SavingsPlan",
    "ReservedInstance",
    "ExecutiveSummaryData",
    "GetAssessmentExecutiveSummaryOutput",
    "MasterReportAccount",
    "GetMasterReportSummaryOutput",
    "SharePointURLInfo",
    "ParseSharePointURLOutput",
    # Internal models
    "SharePointSiteConfig",
    "CacheEntry",
    "FileSearchPattern",
    "ParsedFilename",
    "SheetInfo",
]

# Made with Bob
