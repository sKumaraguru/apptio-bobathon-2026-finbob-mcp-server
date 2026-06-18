"""File discovery service for finding assessment reports."""

import logging
from typing import List, Optional, Dict, Any

from ..models.outputs import ReportMetadata
from ..utils.filename_parser import (
    parse_assessment_filename,
    parse_master_report_filename,
    is_assessment_report,
    is_master_report,
)
from .client import SharePointClient

logger = logging.getLogger(__name__)


class FileDiscoveryService:
    """
    Service for discovering and filtering assessment reports.

    Searches across multiple SharePoint sites and parses filenames
    to extract metadata.
    """

    def __init__(self, sharepoint_client: SharePointClient):
        """
        Initialize file discovery service.

        Args:
            sharepoint_client: SharePoint client instance
        """
        self.client = sharepoint_client

    def discover_assessment_reports(
        self,
        org_id: Optional[str] = None,
        org_name: Optional[str] = None,
        payer_account_id: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        ri_purchase_option: Optional[str] = None,
    ) -> List[ReportMetadata]:
        """
        Discover assessment reports matching filters.

        Args:
            org_id: Filter by organization ID
            org_name: Filter by organization name (partial match)
            payer_account_id: Filter by payer account ID
            year: Filter by year
            month: Filter by month
            ri_purchase_option: Filter by RI purchase option

        Returns:
            List of ReportMetadata objects
        """
        # Build search pattern and exact assessment folder path
        pattern = self._build_search_pattern(org_id=org_id, payer_account_id=payer_account_id, year=year, month=month)
        folder_path = self._build_assessment_folder_path(
            org_id=org_id,
            payer_account_id=payer_account_id,
            year=year,
            month=month,
        )

        # Search assessment sites, preferring the likely site derived from org_id
        assessment_sites = [site for site in self.client.get_all_site_configs() if site.site_type == "assessment"]
        all_files = []
        ordered_sites = assessment_sites
        if org_id and assessment_sites:
            preferred_index = int(org_id) % len(assessment_sites)
            ordered_sites = assessment_sites[preferred_index:] + assessment_sites[:preferred_index]

        for site_config in ordered_sites:
            try:
                logger.info(
                    "Searching for assessment files in site '%s' (site_id=%s, folder_path=%s, pattern=%r)",
                    site_config.site_name,
                    site_config.site_id,
                    folder_path,
                    pattern,
                )
                files = self.client.list_files(
                    folder_path=folder_path,
                    site_id=site_config.site_id,
                    pattern=pattern,
                )
                all_files.extend(files)
                if files:
                    logger.info(
                        "Found %d assessment file(s) in preferred search order at site '%s' (site_id=%s)",
                        len(files),
                        site_config.site_name,
                        site_config.site_id,
                    )
                    break
            except Exception as e:
                logger.exception(
                    "Error listing assessment files in site '%s' (site_id=%s, folder_path=%s, pattern=%r): %s",
                    site_config.site_name,
                    site_config.site_id,
                    folder_path,
                    pattern,
                    e,
                )
                continue

        # Parse filenames and filter
        reports = []
        for file_info in all_files:
            filename = file_info.get("name", "")

            # Only process assessment reports
            if not is_assessment_report(filename):
                continue

            parsed = parse_assessment_filename(filename)
            if not parsed:
                continue

            # Apply filters
            if org_id and parsed.org_id != org_id:
                continue

            if org_name and org_name.lower() not in parsed.org_name.lower():
                continue

            if payer_account_id and parsed.payer_account_id != payer_account_id:
                continue

            if year and parsed.year != year:
                continue

            if month and parsed.month != month:
                continue

            if ri_purchase_option and parsed.ri_purchase_option != ri_purchase_option:
                continue

            # Create ReportMetadata
            # Note: file_info from Microsoft Graph API uses 'id', 'name', 'size', 'webUrl'
            report = ReportMetadata(
                file_id=file_info.get("id", ""),  # Microsoft Graph item ID
                file_name=filename,
                org_id=parsed.org_id,
                org_name=parsed.org_name,
                payer_account_id=parsed.payer_account_id,
                year=parsed.year,
                month=parsed.month,
                ri_purchase_option=parsed.ri_purchase_option,
                version_timestamp=parsed.version_timestamp,
                file_path=file_info.get("webUrl", ""),  # Use webUrl as file_path
                file_size_bytes=file_info.get("size", 0),
                sharepoint_site_id=file_info.get("site_id", ""),
                sharepoint_site_name=file_info.get("site_name", ""),
            )
            reports.append(report)

        # Sort by year-month descending, then version_timestamp descending
        reports.sort(key=lambda r: (r.year, r.month, r.version_timestamp), reverse=True)

        return reports

    def find_master_report(self, year: int, month: int) -> Optional[Dict[str, Any]]:
        """
        Find master report for a specific year-month.
        
        DEPRECATED: This method is deprecated. Use file_id from parse_sharepoint_url instead.
        Master report filenames do not contain org_id, making file_id the preferred lookup method.

        Args:
            year: Year
            month: Month

        Returns:
            File information dictionary if found, None otherwise
        """
        import warnings
        warnings.warn(
            "find_master_report is deprecated. Use file_id from parse_sharepoint_url instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Build filename pattern and exact master report folder path
        pattern = f"Master Report {year}-{month:02d}"
        folder_path = self._build_master_report_folder_path(year=year, month=month)

        # Search across all sites
        all_files = []
        for site_config in self.client.get_all_site_configs():
            try:
                logger.info(
                    "Searching for master report in site '%s' (site_id=%s, folder_path=%s, pattern=%r)",
                    site_config.site_name,
                    site_config.site_id,
                    folder_path,
                    pattern,
                )
                files = self.client.list_files(folder_path=folder_path, site_id=site_config.site_id, pattern=pattern)
                all_files.extend(files)
            except Exception as e:
                logger.exception(
                    "Error searching for master report in site '%s' (site_id=%s, folder_path=%s, pattern=%r): %s",
                    site_config.site_name,
                    site_config.site_id,
                    folder_path,
                    pattern,
                    e,
                )
                continue

        # Find matching master report
        for file_info in all_files:
            filename = file_info.get("name", "")

            if is_master_report(filename):
                parsed = parse_master_report_filename(filename)
                if parsed and parsed["year"] == year and parsed["month"] == month:
                    return file_info

        return None

    def find_report_by_file_id(
        self,
        file_id: str,
        org_id: Optional[str] = None,
        sharepoint_site_name: Optional[str] = None,
    ) -> Optional[ReportMetadata]:
        """
        Find a specific report by its SharePoint file ID.

        Args:
            file_id: SharePoint file ID
            org_id: Optional organization ID hint to prioritize assessment site lookup
            sharepoint_site_name: Optional SharePoint site name hint to prioritize assessment site lookup

        Returns:
            ReportMetadata if found, None otherwise
        """
        # Search only across assessment sites for the file
        assessment_sites = [
            site_config for site_config in self.client.get_all_site_configs() if site_config.site_type == "assessment"
        ]

        ordered_sites = assessment_sites

        if sharepoint_site_name:
            normalized_hint = sharepoint_site_name.strip().lower()
            matching_sites = [site for site in assessment_sites if normalized_hint in site.site_name.lower()]
            non_matching_sites = [site for site in assessment_sites if normalized_hint not in site.site_name.lower()]
            ordered_sites = matching_sites + non_matching_sites
        elif org_id and assessment_sites:
            preferred_index = int(org_id) % len(assessment_sites)
            ordered_sites = assessment_sites[preferred_index:] + assessment_sites[:preferred_index]

        logger.info(
            "Searching for assessment report by file_id=%s across %d assessment site(s): %s (org_id_hint=%r, sharepoint_site_name_hint=%r, ordered_sites=%s)",
            file_id,
            len(assessment_sites),
            [site.site_name for site in assessment_sites],
            org_id,
            sharepoint_site_name,
            [site.site_name for site in ordered_sites],
        )

        for index, site_config in enumerate(ordered_sites, start=1):
            logger.info(
                "Attempting file_id lookup for assessment site %d/%d: '%s' (site_id=%s, file_id=%s)",
                index,
                len(ordered_sites),
                site_config.site_name,
                site_config.site_id,
                file_id,
            )
            try:
                # Try to get file info directly by ID
                file_info = self.client.get_file_info(file_id, site_config.site_id)

                if not file_info:
                    logger.warning(
                        "No file info returned for assessment site '%s' (site_id=%s, file_id=%s)",
                        site_config.site_name,
                        site_config.site_id,
                        file_id,
                    )
                    continue

                logger.info(
                    "Received file info for assessment site '%s' (site_id=%s, file_id=%s, keys=%s)",
                    site_config.site_name,
                    site_config.site_id,
                    file_id,
                    sorted(file_info.keys()),
                )

                filename = file_info.get("name", "")
                if not filename:
                    logger.warning(
                        "File info for assessment site '%s' is missing filename (site_id=%s, file_id=%s, webUrl=%s)",
                        site_config.site_name,
                        site_config.site_id,
                        file_id,
                        file_info.get("webUrl", ""),
                    )
                    continue

                # Parse filename if it's an assessment report
                if not is_assessment_report(filename):
                    logger.warning(
                        "File found in assessment site '%s' but filename did not match assessment pattern "
                        "(site_id=%s, file_id=%s, filename=%r)",
                        site_config.site_name,
                        site_config.site_id,
                        file_id,
                        filename,
                    )
                    continue

                parsed = parse_assessment_filename(filename)
                if not parsed:
                    logger.warning(
                        "File found in assessment site '%s' but filename could not be parsed "
                        "(site_id=%s, file_id=%s, filename=%r)",
                        site_config.site_name,
                        site_config.site_id,
                        file_id,
                        filename,
                    )
                    continue

                logger.info(
                    "Matched assessment report by file_id=%s in site '%s' (site_id=%s, filename=%r)",
                    file_id,
                    site_config.site_name,
                    site_config.site_id,
                    filename,
                )
                return ReportMetadata(
                    file_id=file_id,
                    file_name=filename,
                    org_id=parsed.org_id,
                    org_name=parsed.org_name,
                    payer_account_id=parsed.payer_account_id,
                    year=parsed.year,
                    month=parsed.month,
                    ri_purchase_option=parsed.ri_purchase_option,
                    version_timestamp=parsed.version_timestamp,
                    file_path=file_info.get("webUrl", ""),  # Use webUrl
                    file_size_bytes=file_info.get("size", 0),
                    sharepoint_site_id=site_config.site_id,
                    sharepoint_site_name=site_config.site_name,
                )
            except Exception as e:
                logger.exception(
                    "Error finding file by ID in site '%s' (site_id=%s, file_id=%s): %s",
                    site_config.site_name,
                    site_config.site_id,
                    file_id,
                    e,
                )
                continue

        logger.warning("Assessment report not found by file_id=%s in any assessment site", file_id)
        return None

    def _build_assessment_folder_path(
        self,
        org_id: Optional[str] = None,
        payer_account_id: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> str:
        """
        Build exact folder path for assessment reports.

        Pattern: Assessment Reports/{org_id}/{payer_account_id}/{year}-{month-as-mm}
        """
        if not org_id or not payer_account_id or year is None or month is None:
            raise ValueError("org_id, payer_account_id, year, and month are required for assessment report discovery")

        return f"Assessment Reports/{org_id}/{payer_account_id}/{year}-{month:02d}"

    def _build_master_report_folder_path(self, year: int, month: int) -> str:
        """
        Build exact folder path for master reports.

        Pattern: Assessment Master Reports/{year}-{month-as-mm}
        """
        return f"Assessment Master Reports/{year}-{month:02d}"

    def _build_search_pattern(
        self,
        org_id: Optional[str] = None,
        payer_account_id: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> str:
        """
        Build regex pattern for file search.

        Args:
            org_id: Organization ID
            payer_account_id: Payer account ID
            year: Year
            month: Month

        Returns:
            Regex pattern string
        """
        pattern_parts = ["Financial Planning Report"]

        if org_id:
            pattern_parts.append(f" - {org_id} - ")

        if payer_account_id:
            pattern_parts.append(f"{payer_account_id}")

        if year and month:
            pattern_parts.append(f"{year}-{month:02d}")
        elif year:
            pattern_parts.append(f"{year}-")

        return ".*".join(pattern_parts) + ".*\\.xlsx"


# Made with Bob
