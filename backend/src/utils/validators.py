"""Custom validators for input validation."""

from typing import Optional


def validate_year_month(year: Optional[int], month: Optional[int]) -> None:
    """
    Validate year and month combination.

    Args:
        year: Year value (2020-2030)
        month: Month value (1-12)

    Raises:
        ValueError: If validation fails
    """
    if month is not None and year is None:
        raise ValueError("Year must be provided when month is specified")

    if year is not None and (year < 2020 or year > 2030):
        raise ValueError("Year must be between 2020 and 2030")

    if month is not None and (month < 1 or month > 12):
        raise ValueError("Month must be between 1 and 12")


def validate_page_size(page_size: int, max_size: int = 5000) -> None:
    """
    Validate page size parameter.

    Args:
        page_size: Requested page size
        max_size: Maximum allowed page size

    Raises:
        ValueError: If page size is invalid
    """
    if page_size < 1:
        raise ValueError("Page size must be at least 1")

    if page_size > max_size:
        raise ValueError(f"Page size cannot exceed {max_size}")


def validate_sharepoint_url(url: str) -> None:
    """
    Validate SharePoint URL format.

    Args:
        url: URL to validate

    Raises:
        ValueError: If URL is invalid
    """
    if not url.startswith("https://"):
        raise ValueError("URL must start with https://")

    if "sharepoint.com" not in url:
        raise ValueError("URL must be a SharePoint URL")


def sanitize_sheet_name(sheet_name: str) -> str:
    """
    Sanitize sheet name for safe file operations.

    Args:
        sheet_name: Original sheet name

    Returns:
        Sanitized sheet name
    """
    # Remove or replace problematic characters
    sanitized = sheet_name.replace("/", "_").replace("\\", "_")
    sanitized = sanitized.replace(":", "_").replace("*", "_")
    sanitized = sanitized.replace("?", "_").replace('"', "_")
    sanitized = sanitized.replace("<", "_").replace(">", "_")
    sanitized = sanitized.replace("|", "_")

    return sanitized.strip()


# Made with Bob
