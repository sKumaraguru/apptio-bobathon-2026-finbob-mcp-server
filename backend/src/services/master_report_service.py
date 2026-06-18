"""Master report service for business logic."""

from typing import List, Optional, Dict, Any
import logging
import pandas as pd

from ..models.inputs import GetMasterReportSummaryInput
from ..models.outputs import GetMasterReportSummaryOutput, MasterReportAccount
from ..sharepoint import SharePointClient, FileDiscoveryService
from ..processing import ExcelProcessor
from ..utils.filename_parser import parse_master_report_filename

logger = logging.getLogger(__name__)


class MasterReportService:
    """
    Service for master report operations.

    Handles business logic for retrieving and processing master reports.
    """

    def __init__(self, sharepoint_client: SharePointClient, discovery_service: FileDiscoveryService):
        """
        Initialize master report service.

        Args:
            sharepoint_client: SharePoint client instance
            discovery_service: File discovery service instance
        """
        self.sp_client = sharepoint_client
        self.discovery = discovery_service

    def get_summary(self, input_data: GetMasterReportSummaryInput) -> GetMasterReportSummaryOutput:
        """
        Get master report summary using file_id.

        Args:
            input_data: Master report input parameters (file_id required)

        Returns:
            GetMasterReportSummaryOutput with account data

        Raises:
            ValueError: If master report not found or file_id is invalid
        """
        # Find master report by file_id across sites
        file_info = self._find_master_report_by_file_id(input_data.file_id, input_data.site_id)
        
        if not file_info:
            raise ValueError(f"Master report not found with file_id: {input_data.file_id}")

        # Download file
        local_path = self.sp_client.download_file(
            file_id=file_info["id"], site_id=file_info["site_id"], use_cache=True
        )

        # Process Excel file
        with ExcelProcessor(local_path) as processor:
            # Master report has only one sheet
            sheet_names = processor.get_sheet_names()
            if not sheet_names:
                raise ValueError("Master report has no sheets")

            master_sheet = sheet_names[0]

            # Read as JSON for easier processing
            data = processor.sheet_to_json(master_sheet, include_headers=True)

        # Parse accounts
        accounts = []
        for row in data:
            # Apply category filter if provided
            if input_data.category and row.get("category") != input_data.category:
                continue

            # Build account object
            account = MasterReportAccount(
                org_id=str(row.get("org_id", "")),
                org_name=str(row.get("org_name", "")),
                account_id=str(row.get("account_id", "")),
                category=str(row.get("category", "")),
                currency_code=str(row.get("currency_code", "USD")),
                savings_metrics=self._extract_savings_metrics(row),
                cost_metrics=self._extract_cost_metrics(row),
                coverage_metrics=self._extract_coverage_metrics(row),
                discount_metrics=self._extract_discount_metrics(row),
                workload_metrics=self._extract_workload_metrics(row),
                report_quality=self._extract_report_quality(row),
                urls=self._extract_urls(row),
            )
            accounts.append(account)

        # Calculate summary statistics
        summary_stats = self._calculate_summary_statistics(accounts)

        # Extract year/month from filename if available
        filename = file_info.get("name", "")
        parsed_filename = parse_master_report_filename(filename)
        year = parsed_filename.get("year") if parsed_filename else None
        month = parsed_filename.get("month") if parsed_filename else None

        # Build master report metadata
        master_report_metadata = {
            "year": year,
            "month": month,
            "year_month": f"{year}-{month:02d}" if year and month else None,
            "total_accounts": len(accounts),
            "file_name": filename,
            "file_path": file_info.get("webUrl", ""),
            "site_id": file_info["site_id"],
            "file_id": file_info["id"],
        }

        return GetMasterReportSummaryOutput(
            master_report_metadata=master_report_metadata, accounts=accounts, summary_statistics=summary_stats
        )

    def _extract_savings_metrics(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract savings-related metrics from row."""
        return {
            "additional_savings": self._get_float(row, "additional_savings"),
            "non_ec2_savings_1yr_ris": self._get_float(row, "non_ec2_savings_1yr_ris"),
            "non_ec2_savings_3yr_ris": self._get_float(row, "non_ec2_savings_3yr_ris"),
            "savings_model_1": self._get_float(row, "savings_model_1"),
            "savings_current_state": self._get_float(row, "savings_current_state"),
        }

    def _extract_cost_metrics(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract cost-related metrics from row."""
        return {
            "total_public_pricing_cost": self._get_float(row, "total_public_pricing_cost"),
            "public_pricing_cost_5percentile": self._get_float(row, "public_pricing_cost_5percentile"),
            "base_fee": self._get_float(row, "base_fee"),
            "extra_mile_fee": self._get_float(row, "extra_mile_fee"),
            "total_fee": self._get_float(row, "total_fee"),
        }

    def _extract_coverage_metrics(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract coverage-related metrics from row."""
        return {
            "current_coverage": self._get_float(row, "current_coverage"),
            "current_coverage_percentage": self._get_float(row, "current_coverage_percentage"),
            "dh_coverage": self._get_float(row, "dh_coverage"),
            "cri_coverage_constraint": self._get_float(row, "cri_coverage_constraint"),
        }

    def _extract_discount_metrics(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract discount-related metrics from row."""
        return {
            "net_effective_discount_current_state": self._get_float(row, "net_effective_discount_current_state"),
            "net_effective_discount_model_1": self._get_float(row, "net_effective_discount_model_1"),
            "net_effective_discount_model_2": self._get_float(row, "net_effective_discount_model_2"),
        }

    def _extract_workload_metrics(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract workload-related metrics from row."""
        return {
            "stable_workload_percentage": self._get_float(row, "stable_workload_percentage"),
            "fluctuation_workload_percentage": self._get_float(row, "fluctuation_workload_percentage"),
            "cri_coverable_stable_usage": self._get_float(row, "cri_coverable_stable_usage"),
        }

    def _extract_report_quality(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract report quality indicators from row."""
        return {
            "report_quality": row.get("report_quality"),
            "report_type": row.get("report_type"),
            "report_status": row.get("report_status"),
            "execution_status": row.get("execution_status"),
        }

    def _extract_urls(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract URLs from row."""
        return {
            "excel_spreadsheet_url": row.get("excel_spreadsheet_url"),
            "sharepoint_site_url": row.get("sharepoint_site_url"),
            "jira_ticket": row.get("jira_ticket"),
        }

    def _get_float(self, data: Dict[str, Any], key: str) -> Optional[float]:
        """Safely get float value from dictionary."""
        value = data.get(key)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _calculate_summary_statistics(self, accounts: List[MasterReportAccount]) -> Dict[str, Any]:
        """Calculate summary statistics across all accounts."""
        if not accounts:
            return {}

        total_savings = sum(acc.savings_metrics.get("savings_model_1", 0) or 0 for acc in accounts)

        total_cost = sum(acc.cost_metrics.get("total_public_pricing_cost", 0) or 0 for acc in accounts)

        avg_coverage = (
            sum(acc.coverage_metrics.get("current_coverage_percentage", 0) or 0 for acc in accounts) / len(accounts)
            if accounts
            else 0
        )

        return {
            "total_accounts": len(accounts),
            "total_savings_opportunity": total_savings,
            "total_public_pricing_cost": total_cost,
            "average_coverage_percentage": avg_coverage,
            "categories": list(set(acc.category for acc in accounts)),
            "organizations": list(set(acc.org_name for acc in accounts)),
        }

    def _find_master_report_by_file_id(self, file_id: str, site_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find master report by file_id, searching across sites.

        Args:
            file_id: SharePoint file ID
            site_id: Optional site ID hint to prioritize lookup

        Returns:
            File info dictionary if found, None otherwise
        """
        # Get all site configs (master reports are typically in primary site)
        all_sites = self.sp_client.get_all_site_configs()
        
        # Order sites: if site_id provided, try it first
        ordered_sites = all_sites
        if site_id:
            matching_sites = [site for site in all_sites if site.site_id == site_id]
            other_sites = [site for site in all_sites if site.site_id != site_id]
            ordered_sites = matching_sites + other_sites

        logger.info(
            "Searching for master report by file_id=%s across %d site(s) (site_id_hint=%r)",
            file_id,
            len(all_sites),
            site_id,
        )

        for index, site_config in enumerate(ordered_sites, start=1):
            logger.info(
                "Attempting file_id lookup for site %d/%d: '%s' (site_id=%s, file_id=%s)",
                index,
                len(ordered_sites),
                site_config.site_name,
                site_config.site_id,
                file_id,
            )
            try:
                # Try to get file info directly by ID
                file_info = self.sp_client.get_file_info(file_id, site_config.site_id)

                if not file_info:
                    logger.warning(
                        "No file info returned for site '%s' (site_id=%s, file_id=%s)",
                        site_config.site_name,
                        site_config.site_id,
                        file_id,
                    )
                    continue

                logger.info(
                    "Found master report in site '%s' (site_id=%s, file_id=%s, name=%s)",
                    site_config.site_name,
                    site_config.site_id,
                    file_id,
                    file_info.get("name", ""),
                )
                return file_info

            except Exception as e:
                logger.debug(
                    "File not found in site '%s' (site_id=%s, file_id=%s): %s",
                    site_config.site_name,
                    site_config.site_id,
                    file_id,
                    e,
                )
                continue

        logger.error("Master report not found with file_id=%s across %d site(s)", file_id, len(all_sites))
        return None


# Made with Bob
