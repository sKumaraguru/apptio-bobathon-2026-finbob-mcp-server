"""Internal models for MCP server using Pydantic v1."""
from pydantic import BaseModel
from typing import Literal, Dict, Any, List
from datetime import datetime


class SharePointSiteConfig(BaseModel):
    """SharePoint site configuration."""
    site_id: str
    site_name: str
    site_type: Literal["primary", "assessment"]


class CacheEntry(BaseModel):
    """Cache entry for downloaded files."""
    file_path: str
    local_path: str
    cached_at: datetime
    expires_at: datetime
    file_size_bytes: int
    report_metadata: Dict[str, Any]


class FileSearchPattern(BaseModel):
    """Pattern for searching files."""
    folder_path: str
    filename_pattern: str
    site_ids: List[str]


class ParsedFilename(BaseModel):
    """Parsed assessment report filename."""
    org_id: str
    org_name: str
    payer_account_id: str
    year: int
    month: int
    jira_ticket: str
    ri_purchase_option: str
    version_timestamp: datetime
    is_master_report: bool = False


class SheetInfo(BaseModel):
    """Information about an Excel sheet."""
    name: str
    row_count: int
    column_count: int
    has_headers: bool
    is_empty: bool

# Made with Bob
