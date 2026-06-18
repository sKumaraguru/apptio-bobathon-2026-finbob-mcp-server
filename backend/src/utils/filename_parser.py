"""Parse assessment report filenames to extract metadata."""

import re
from datetime import datetime
from typing import Optional
from ..models.internal import ParsedFilename


# Regex patterns for parsing filenames
ASSESSMENT_REPORT_PATTERN = re.compile(
    r"Financial Planning Report - "
    r"(?P<org_id>\d+) - "
    r"(?P<org_name>[^-]+) - "
    r"(?P<payer_account_id>\d+) - "
    r"(?P<year>\d{4})-(?P<month>\d{2}) - "
    r"(?P<jira_ticket>(?:CSASA-\d+|None)) - "
    r"(?P<ri_purchase_option>[^-]+) - "
    r"v(?P<timestamp>\d{4}[:\-]\d{2}[:\-]\d{2}[ T]\d{2}-\d{2}-\d{2})"
    r"\.xlsx"
)

MASTER_REPORT_PATTERN = re.compile(
    r"Master Report " r"(?P<year>\d{4})-(?P<month>\d{2}) " r"(?P<uuid>[a-f0-9-]+)" r"\.xlsx"
)


def parse_assessment_filename(filename: str) -> Optional[ParsedFilename]:
    """
    Parse an assessment report filename to extract metadata.

    Args:
        filename: The filename to parse

    Returns:
        ParsedFilename object if successful, None otherwise

    Example:
        >>> parse_assessment_filename(
        ...     "Financial Planning Report - 113798 - Danaher Corporation - "
        ...     "788915724807 - 2026-05 - CSASA-1340 - No Upfront - "
        ...     "v2026-06-03 17-23-54.xlsx"
        ... )
        ParsedFilename(org_id='113798', org_name='Danaher Corporation', ...)
    """
    match = ASSESSMENT_REPORT_PATTERN.match(filename)
    if not match:
        return None

    groups = match.groupdict()

    # Parse timestamp from filename formats such as:
    # - YYYY-MM-DD HH-MM-SS
    # - YYYY:MM:DDT HH-MM-SS / YYYY:MM:DDTHH-MM-SS
    timestamp_str = groups["timestamp"].strip().replace("T ", "T")
    normalized_timestamp = timestamp_str.replace(":", "-", 2).replace("T", " ")
    version_timestamp = datetime.strptime(normalized_timestamp, "%Y-%m-%d %H-%M-%S")

    return ParsedFilename(
        org_id=groups["org_id"],
        org_name=groups["org_name"].strip(),
        payer_account_id=groups["payer_account_id"],
        year=int(groups["year"]),
        month=int(groups["month"]),
        jira_ticket=groups["jira_ticket"],
        ri_purchase_option=groups["ri_purchase_option"].strip(),
        version_timestamp=version_timestamp,
        is_master_report=False,
    )


def parse_master_report_filename(filename: str) -> Optional[dict]:
    """
    Parse a master report filename to extract metadata.

    Args:
        filename: The filename to parse

    Returns:
        Dictionary with year, month, and uuid if successful, None otherwise

    Example:
        >>> parse_master_report_filename(
        ...     "Master Report 2026-05 8cd594a0-6213-11f1-8ff2-0f47e373d8d7.xlsx"
        ... )
        {'year': 2026, 'month': 5, 'uuid': '8cd594a0-6213-11f1-8ff2-0f47e373d8d7'}
    """
    match = MASTER_REPORT_PATTERN.match(filename)
    if not match:
        return None

    groups = match.groupdict()
    return {
        "year": int(groups["year"]),
        "month": int(groups["month"]),
        "uuid": groups["uuid"],
        "is_master_report": True,
    }


def is_assessment_report(filename: str) -> bool:
    """Check if filename matches assessment report pattern."""
    return ASSESSMENT_REPORT_PATTERN.match(filename) is not None


def is_master_report(filename: str) -> bool:
    """Check if filename matches master report pattern."""
    return MASTER_REPORT_PATTERN.match(filename) is not None


# Made with Bob
