"""Assessment report service for business logic."""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..models.inputs import (
    ListAssessmentReportsInput,
    GetAssessmentSheetInput,
    GetAssessmentSheetNamesInput,
    GetAssessmentExecutiveSummaryInput,
)
from ..models.outputs import (
    ListAssessmentReportsOutput,
    GetAssessmentSheetOutput,
    GetAssessmentSheetNamesOutput,
    GetAssessmentExecutiveSummaryOutput,
    ReportMetadata,
    SheetMetadata,
    PaginationMetadata,
)
from ..sharepoint import SharePointClient, FileDiscoveryService
from ..processing import ExcelProcessor, CSVPaginator, ExecutiveSummaryExtractor

logger = logging.getLogger(__name__)


class AssessmentReportService:
    """
    Service for assessment report operations.

    Handles business logic for listing, retrieving, and processing
    assessment reports.
    """

    def __init__(self, sharepoint_client: SharePointClient, discovery_service: FileDiscoveryService):
        """
        Initialize assessment report service.

        Args:
            sharepoint_client: SharePoint client instance
            discovery_service: File discovery service instance
        """
        self.sp_client = sharepoint_client
        self.discovery = discovery_service

    def list_reports(self, input_data: ListAssessmentReportsInput) -> ListAssessmentReportsOutput:
        """
        List assessment reports with optional filtering.

        Args:
            input_data: List reports input parameters

        Returns:
            ListAssessmentReportsOutput with matching reports
        """
        # Discover reports using filters
        reports = self.discovery.discover_assessment_reports(
            org_id=input_data.org_id,
            org_name=input_data.org_name,
            payer_account_id=input_data.payer_account_id,
            year=input_data.year,
            month=input_data.month,
            ri_purchase_option=input_data.ri_purchase_option,
        )

        # Build filters_applied dict
        filters_applied = {}
        if input_data.org_id:
            filters_applied["org_id"] = input_data.org_id
        if input_data.org_name:
            filters_applied["org_name"] = input_data.org_name
        if input_data.payer_account_id:
            filters_applied["payer_account_id"] = input_data.payer_account_id
        if input_data.year:
            filters_applied["year"] = input_data.year
        if input_data.month:
            filters_applied["month"] = input_data.month
        if input_data.ri_purchase_option:
            filters_applied["ri_purchase_option"] = input_data.ri_purchase_option

        return ListAssessmentReportsOutput(reports=reports, total_count=len(reports), filters_applied=filters_applied)

    def get_executive_summary(
        self, input_data: GetAssessmentExecutiveSummaryInput
    ) -> GetAssessmentExecutiveSummaryOutput:
        """
        Get executive summary from an assessment report.

        Args:
            input_data: Executive summary input parameters

        Returns:
            GetAssessmentExecutiveSummaryOutput with structured data

        Raises:
            ValueError: If report not found
        """
        # Check cache first using file_id
        logger.info(f"Checking cache for file_id={input_data.file_id}")
        cached_path = self.sp_client.cache_manager.get(input_data.file_id)
        
        if cached_path:
            # Cache hit - use cached file directly, no SharePoint operations needed
            logger.info(f"✓ Using cached file for file_id={input_data.file_id}")
            local_path = cached_path
            
            # Create minimal report object for cached case
            class CachedReport:
                def __init__(self):
                    self.file_id = input_data.file_id
                    self.file_name = Path(cached_path).name
                    self.org_id = input_data.org_id or 'unknown'
                    self.org_name = 'unknown'
                    self.payer_account_id = 'unknown'
                    self.year = 0
                    self.month = 0
            
            report = CachedReport()
        else:
            # Cache miss - perform full SharePoint discovery and download
            logger.info(f"✗ Cache miss for file_id={input_data.file_id}, performing SharePoint discovery")
            
            # Find report by SharePoint file ID, using optional hints to prioritize site lookup
            report = self.discovery.find_report_by_file_id(
                input_data.file_id,
                org_id=input_data.org_id,
                sharepoint_site_name=input_data.sharepoint_site_name,
            )

            if not report:
                raise ValueError("Assessment report not found")
            if not report.file_id:
                raise ValueError(f"Assessment report is missing SharePoint file_id")

            # Download file (will cache it)
            local_path = self.sp_client.download_file(
                file_id=report.file_id, site_id=report.sharepoint_site_id, use_cache=True
            )

        # Process Excel file
        with ExcelProcessor(local_path) as processor:
            extractor = ExecutiveSummaryExtractor(processor)
            executive_summary = extractor.extract()
            sheets_included = extractor.get_sheets_included()

        # Build report metadata
        report_metadata = {
            "file_id": report.file_id,
            "file_name": report.file_name,
            "org_id": report.org_id,
            "org_name": report.org_name,
            "payer_account_id": report.payer_account_id,
            "year_month": f"{report.year}-{report.month:02d}",
        }

        return GetAssessmentExecutiveSummaryOutput(
            report_metadata=report_metadata, executive_summary=executive_summary, sheets_included=sheets_included
        )

    def get_sheet(self, input_data: GetAssessmentSheetInput) -> GetAssessmentSheetOutput:
        """
        Get a sheet from an assessment report with pagination.

        Args:
            input_data: Sheet retrieval input parameters

        Returns:
            GetAssessmentSheetOutput with sheet data

        Raises:
            ValueError: If report or sheet not found
        """
        # Check cache FIRST to avoid expensive SharePoint API calls
        logger.info(f"Checking cache for file_id={input_data.file_id}")
        cached_path = self.sp_client.cache_manager.get(input_data.file_id)
        
        if cached_path:
            # Cache hit - use cached file directly, no SharePoint operations needed
            logger.info(f"✓ Using cached file for file_id={input_data.file_id}")
            local_path = cached_path
            
            # Create minimal report object for cached case
            class CachedReport:
                def __init__(self):
                    self.file_id = input_data.file_id
                    self.file_name = Path(cached_path).name
                    self.org_id = input_data.org_id or 'unknown'
            
            report = CachedReport()
        else:
            # Cache miss - perform full SharePoint discovery and download
            logger.info(f"✗ Cache miss for file_id={input_data.file_id}, performing SharePoint discovery")
            
            # Find report by SharePoint file ID, using optional hints to prioritize site lookup
            report = self.discovery.find_report_by_file_id(
                input_data.file_id,
                org_id=input_data.org_id,
                sharepoint_site_name=input_data.sharepoint_site_name,
            )

            if not report:
                raise ValueError(f"Report not found: {input_data.file_id}")
            if not report.file_id:
                raise ValueError(f"Report is missing SharePoint file_id")

            # Download file (will cache it)
            local_path = self.sp_client.download_file(
                file_id=report.file_id, site_id=report.sharepoint_site_id, use_cache=True
            )

        # Process Excel file
        with ExcelProcessor(local_path) as processor:
            # Check if sheet exists
            if input_data.sheet_name not in processor.get_sheet_names():
                available_sheets = processor.get_sheet_names()
                raise ValueError(
                    f"Sheet '{input_data.sheet_name}' not found. " f"Available sheets: {', '.join(available_sheets)}"
                )

            # Get sheet info
            sheet_info = processor.get_sheet_info(input_data.sheet_name)

            # Get sheet data based on format
            if input_data.format == "csv":
                # Get full CSV
                csv_data = processor.sheet_to_csv(
                    sheet_name=input_data.sheet_name, include_headers=sheet_info.has_headers
                )

                # Paginate CSV
                paginator = CSVPaginator(csv_data, input_data.page_size)
                page_data, pagination = paginator.get_page(input_data.page)

                data = page_data
            else:  # json
                # Get JSON data
                json_data = processor.sheet_to_json(
                    sheet_name=input_data.sheet_name, include_headers=sheet_info.has_headers
                )

                # Manual pagination for JSON
                start_idx = (input_data.page - 1) * input_data.page_size
                end_idx = start_idx + input_data.page_size
                page_data = json_data[start_idx:end_idx]

                total_pages = (len(json_data) + input_data.page_size - 1) // input_data.page_size
                pagination = PaginationMetadata(
                    page=input_data.page,
                    page_size=input_data.page_size,
                    total_pages=total_pages,
                    has_next_page=input_data.page < total_pages,
                    has_previous_page=input_data.page > 1,
                )

                data = page_data

            # Build sheet metadata
            sheet_metadata = SheetMetadata(
                total_rows=sheet_info.row_count,
                total_columns=sheet_info.column_count,
                has_headers=sheet_info.has_headers,
                data_type="csv" if not sheet_info.is_empty else "empty",
                column_names=None,  # Could extract from first row if needed
            )

            # Build report metadata
            report_metadata = {
                "file_id": report.file_id,
                "file_name": report.file_name,
                "org_id": report.org_id,
                "sheet_name": input_data.sheet_name,
            }

        return GetAssessmentSheetOutput(
            report_metadata=report_metadata,
            sheet_metadata=sheet_metadata,
            pagination=pagination,
            data=data,
            format=input_data.format,
        )

    def get_sheet_names(self, input_data: GetAssessmentSheetNamesInput) -> GetAssessmentSheetNamesOutput:
        """
        Get list of sheet names from an assessment report.

        Args:
            input_data: Sheet names retrieval input parameters

        Returns:
            GetAssessmentSheetNamesOutput with list of sheet names

        Raises:
            ValueError: If report not found
        """
        # Check cache FIRST to avoid expensive SharePoint API calls
        logger.info(f"Checking cache for file_id={input_data.file_id}")
        cached_path = self.sp_client.cache_manager.get(input_data.file_id)
        
        if cached_path:
            # Cache hit - use cached file directly, no SharePoint operations needed
            logger.info(f"✓ Using cached file for file_id={input_data.file_id}")
            local_path = cached_path
            
            # Create minimal report object for cached case
            class CachedReport:
                def __init__(self):
                    self.file_id = input_data.file_id
                    self.file_name = Path(cached_path).name
                    self.org_id = input_data.org_id or 'unknown'
            
            report = CachedReport()
        else:
            # Cache miss - perform full SharePoint discovery and download
            logger.info(f"✗ Cache miss for file_id={input_data.file_id}, performing SharePoint discovery")
            
            # Find report by SharePoint file ID, using optional hints to prioritize site lookup
            report = self.discovery.find_report_by_file_id(
                input_data.file_id,
                org_id=input_data.org_id,
                sharepoint_site_name=input_data.sharepoint_site_name,
            )

            if not report:
                raise ValueError(f"Report not found: {input_data.file_id}")
            if not report.file_id:
                raise ValueError(f"Report is missing SharePoint file_id")

            # Download file (will cache it)
            local_path = self.sp_client.download_file(
                file_id=report.file_id, site_id=report.sharepoint_site_id, use_cache=True
            )

        # Process Excel file to get sheet names
        with ExcelProcessor(local_path) as processor:
            sheet_names = processor.get_sheet_names()

        # Build report metadata
        report_metadata = {
            "file_id": report.file_id,
            "file_name": report.file_name,
            "org_id": report.org_id,
        }

        return GetAssessmentSheetNamesOutput(
            report_metadata=report_metadata,
            sheet_names=sheet_names,
            total_sheets=len(sheet_names),
        )



# Made with Bob
