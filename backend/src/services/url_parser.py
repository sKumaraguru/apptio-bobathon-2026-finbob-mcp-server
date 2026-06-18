"""SharePoint URL parsing service."""

import logging
import re
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs

from ..models.inputs import ParseSharePointURLInput
from ..models.outputs import ParseSharePointURLOutput, SharePointURLInfo
from ..sharepoint import SharePointClient
from ..utils.filename_parser import is_assessment_report, is_master_report

logger = logging.getLogger(__name__)


class SharePointURLParser:
    """
    Parse and validate SharePoint URLs.

    Supports both sharing links and direct file URLs.
    """

    def __init__(self, sharepoint_client: SharePointClient):
        """
        Initialize URL parser.

        Args:
            sharepoint_client: SharePoint client instance
        """
        self.sp_client = sharepoint_client

    def parse(self, input_data: ParseSharePointURLInput) -> ParseSharePointURLOutput:
        """
        Parse SharePoint URL and extract information.

        Args:
            input_data: URL parsing input parameters

        Returns:
            ParseSharePointURLOutput with parsed information

        Raises:
            ValueError: If URL is invalid or cannot be parsed
        """
        url = input_data.url.strip()

        # Determine URL type
        if self._is_sharing_link(url):
            url_type = "sharing_link"
            url_info = self._parse_sharing_link(url)
        else:
            url_type = "direct_file_url"
            url_info = self._parse_direct_url(url)

        # Determine report type
        filename = url_info["file_name"]
        is_master = is_master_report(filename)
        is_assessment = is_assessment_report(filename)

        # Create URL info
        sharepoint_url_info = SharePointURLInfo(
            url_type=url_type,
            site_id=url_info["site_id"],
            file_path=url_info["file_path"],
            file_name=filename,
            is_master_report=is_master,
            is_assessment_report=is_assessment,
        )

        # Get file info from SharePoint when a file_id is available
        try:
            file_id = url_info.get("file_id")
            if file_id:
                file_info = self.sp_client.get_file_info(file_id=file_id, site_id=url_info["site_id"])
            else:
                file_info = {
                    "warning": "File ID not available from URL; SharePoint metadata lookup skipped",
                    "file_path": url_info["file_path"],
                }
        except Exception as e:
            logger.exception(
                "Could not retrieve file info for parsed SharePoint URL (site_id=%s, file_path=%s, file_id=%s): %s",
                url_info["site_id"],
                url_info["file_path"],
                url_info.get("file_id"),
                e,
            )
            file_info = {"error": f"Could not retrieve file info: {e}", "file_path": url_info["file_path"]}

        # Build report metadata
        report_metadata = {"file_name": filename, "is_master_report": is_master, "is_assessment_report": is_assessment}

        return ParseSharePointURLOutput(
            url_info=sharepoint_url_info, report_metadata=report_metadata, file_info=file_info
        )

    def _parse_sharing_link(self, url: str) -> Dict[str, Any]:
        """
        Parse SharePoint sharing link.

        Args:
            url: Sharing link URL

        Returns:
            Dictionary with site_id, file_path, and file_name

        Raises:
            ValueError: If URL cannot be parsed
        """
        # Example: https://company.sharepoint.com/personal/user/_layouts/15/onedrive.aspx?id=/path/to/file.xlsx

        parsed = urlparse(url)
        if not parsed.hostname:
            raise ValueError("Invalid SharePoint URL hostname")

        query_params = parse_qs(parsed.query)

        file_path = None
        if "id" in query_params:
            file_path = query_params["id"][0]
        elif "RootFolder" in query_params:
            file_path = query_params["RootFolder"][0]
        elif "file" in query_params:
            file_path = f"{parsed.path}?{parsed.query}"

        file_id = None
        if "UniqueId" in query_params:
            file_id = query_params["UniqueId"][0]
        elif "sourcedoc" in query_params:
            file_id = query_params["sourcedoc"][0].strip("{}")

        filename = None
        if "file" in query_params:
            filename = query_params["file"][0]
        elif file_path:
            filename = file_path.split("/")[-1]

        if not filename:
            raise ValueError("Could not extract file name from sharing link")

        if not file_path:
            file_path = parsed.path

        site_id = self._match_site_from_url(url)

        return {"site_id": site_id, "file_id": file_id, "file_path": file_path, "file_name": filename}

    def _parse_direct_url(self, url: str) -> Dict[str, Any]:
        """
        Parse direct SharePoint file URL.

        Args:
            url: Direct file URL

        Returns:
            Dictionary with site_id, file_path, and file_name

        Raises:
            ValueError: If URL cannot be parsed
        """
        # Example: https://company.sharepoint.com/sites/sitename/Shared%20Documents/file.xlsx

        parsed = urlparse(url)

        # Extract path
        path = parsed.path

        # Extract filename
        filename = path.split("/")[-1]

        # Try to determine site_id
        site_id = self._match_site_from_url(url)

        # File ID would need to be retrieved from SharePoint API
        # For direct URLs, we typically don't have it in the URL itself

        return {
            "site_id": site_id,
            "file_id": None,  # Would need SharePoint API call to get this
            "file_path": path,
            "file_name": filename,
        }

    def _is_sharing_link(self, url: str) -> bool:
        """Determine whether a SharePoint URL is a sharing/document link."""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        return (
            "/personal/" in url
            or "/:x:/" in url
            or parsed.path.endswith("/Doc.aspx")
            or "sourcedoc" in query_params
            or "file" in query_params
        )

    def _match_site_from_url(self, url: str) -> str:
        """
        Try to match URL to a known SharePoint site.

        Args:
            url: SharePoint URL

        Returns:
            Site ID if matched, empty string otherwise
        """
        # Get all configured sites
        site_configs = self.sp_client.get_all_site_configs()

        # Try to match by site name in URL
        for config in site_configs:
            if config.site_name.lower() in url.lower():
                return config.site_id

        # If no match, return first site as default (or could raise error)
        if site_configs:
            return site_configs[0].site_id

        return ""


# Made with Bob
