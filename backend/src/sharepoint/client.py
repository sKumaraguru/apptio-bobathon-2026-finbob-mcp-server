"""SharePoint client wrapper using cwshareddriveutils."""

import logging
from typing import List, Optional
from pathlib import Path
import tempfile
from urllib.parse import urlparse, unquote, parse_qs

from cwshareddriveutils.sharepoint.sharepoint import SharePointClientProvider, SharePointExcelManager
from cwshareddriveutils.sharepoint.clients import MicrosoftSharepointAuth, SharePointNetworkClient
from cwshareddriveutils.sharepoint.models import AzureAppCredentials

from ..models.internal import SharePointSiteConfig
from .cache import CacheManager

logger = logging.getLogger(__name__)


class SharePointClient:
    """
    Wrapper around cwshareddriveutils SharePoint functionality.

    Provides a consistent API for file operations across multiple SharePoint sites
    with caching support.
    
    Note: The cwshareddriveutils library does not have a SharePointClient class.
    This wrapper uses SharePointClientProvider and SharePointExcelManager instead.
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        site_configs: List[SharePointSiteConfig],
        cache_manager: Optional[CacheManager] = None,
    ):
        """
        Initialize SharePoint client.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD client ID
            client_secret: Azure AD client secret
            site_configs: List of SharePoint site configurations
            cache_manager: Optional cache manager instance
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.site_configs = {config.site_id: config for config in site_configs}
        self.cache_manager = cache_manager or CacheManager()

        # Create credentials
        credentials = AzureAppCredentials(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id
        )

        # Create auth and network client
        self.auth = MicrosoftSharepointAuth(credentials)
        self.network_client = SharePointNetworkClient()

        # Create provider
        self.provider = SharePointClientProvider(self.network_client, self.auth)

        # Cache clients for each site
        self.clients = {}
        for site_id in self.site_configs.keys():
            self.clients[site_id] = self.provider.client(site_id)

    def list_files(self, folder_path: str, site_id: Optional[str] = None, pattern: Optional[str] = None) -> List[dict]:
        """
        List files in a folder across one or all sites.

        Args:
            folder_path: Folder path to list
            site_id: Optional site ID to search (searches all if None)
            pattern: Optional filename pattern to filter

        Returns:
            List of file information dictionaries
        """
        results = []

        # Determine which sites to search
        site_ids = [site_id] if site_id else list(self.clients.keys())

        for sid in site_ids:
            client = self.clients.get(sid)
            if not client:
                continue

            try:
                # Get folder reference
                folder_ref = client.get_or_create_folder_details(folder_path)
                
                # List files in folder
                files = client.workbook_manager.list_folder_items(folder_ref.id)

                for file_info in files:
                    # Add site information
                    file_info["site_id"] = sid
                    file_info["site_name"] = self.site_configs[sid].site_name

                    # Filter by pattern if provided
                    if pattern:
                        import re

                        if not re.search(pattern, file_info.get("name", "")):
                            continue

                    results.append(file_info)

            except Exception as e:
                logger.exception(
                    "Error listing files in site '%s' (folder_path=%r, pattern=%r): %s",
                    sid,
                    folder_path,
                    pattern,
                    e,
                )
                continue

        return results

    def download_file(self, file_id: str, site_id: str, use_cache: bool = True) -> str:
        """
        Download a file from SharePoint.

        Args:
            file_id: SharePoint file ID (item ID)
            site_id: Site ID where file is located
            use_cache: Whether to use cache (default: True)

        Returns:
            Local file path

        Raises:
            ValueError: If site_id is invalid
            Exception: If download fails
        """
        # Check cache first (using file_id as key)
        if use_cache:
            logger.info(f"Checking cache for file_id={file_id}")
            cached_path = self.cache_manager.get(file_id)
            if cached_path:
                logger.info(f"✓ CACHE HIT for file_id={file_id}, path={cached_path}")
                return cached_path
            logger.info(f"✗ CACHE MISS for file_id={file_id}")

        # Get client for site
        client = self.clients.get(site_id)
        if not client:
            raise ValueError(f"Invalid site_id: {site_id}")

        # Download file to temp location
        temp_dir = Path(tempfile.gettempdir()) / "csa_assessments_cache"
        temp_dir.mkdir(exist_ok=True)

        # Get file metadata to derive a safe local filename
        try:
            workbook_url = client.get_workbook_url(file_id)
            parsed_url = urlparse(workbook_url) if workbook_url else None
            filename = unquote(Path(parsed_url.path).name) if parsed_url and parsed_url.path else f"{file_id}.xlsx"

            if not filename.lower().endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
                logger.warning(
                    "Derived invalid workbook filename from URL for file_id=%s site_id=%s url=%s; falling back to default name",
                    file_id,
                    site_id,
                    workbook_url,
                )
                filename = f"{file_id}.xlsx"
        except Exception as e:
            logger.exception(
                "Failed to derive workbook filename for file_id=%s site_id=%s: %s",
                file_id,
                site_id,
                e,
            )
            filename = f"{file_id}.xlsx"

        # Generate unique local filename
        local_path = temp_dir / f"{site_id}_{filename}"
        logger.info("Downloading SharePoint file to temp path: %s", local_path)

        # Download using cwshareddriveutils
        with client.workbook_session(file_id):
            response = client.download_workbook()

            # Save to local file
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Get file size
        file_size = local_path.stat().st_size

        # Add to cache
        if use_cache:
            self.cache_manager.put(
                file_path=file_id,  # Use file_id as cache key
                local_path=str(local_path),
                file_size_bytes=file_size,
                report_metadata={"site_id": site_id, "file_id": file_id},
            )
            logger.info(f"✓ Cached file_id={file_id} at path={local_path}")

        return str(local_path)

    def get_file_info(self, file_id: str, site_id: str) -> dict:
        """
        Get file metadata from SharePoint.

        Args:
            file_id: SharePoint file ID (item ID)
            site_id: Site ID where file is located

        Returns:
            File information dictionary

        Raises:
            ValueError: If site_id is invalid
        """
        client = self.clients.get(site_id)
        if not client:
            raise ValueError(f"Invalid site_id: {site_id}")

        # Get workbook URL and other metadata
        try:
            workbook_url = client.get_workbook_url(file_id)
            parent_folder_id = client.get_parent_folder_id(file_id)

            filename = ""
            if workbook_url:
                parsed_url = urlparse(workbook_url)
                query_params = parse_qs(parsed_url.query)

                if "file" in query_params and query_params["file"]:
                    filename = unquote(query_params["file"][0])
                elif parsed_url.path:
                    filename = unquote(Path(parsed_url.path).name)

                if filename == "Doc.aspx":
                    filename = ""

            return {
                "id": file_id,
                "name": filename,
                "webUrl": workbook_url,
                "parentFolderId": parent_folder_id,
                "site_id": site_id,
            }
        except Exception as e:
            raise Exception(f"Failed to get file info: {e}")

    def search_files(self, query: str, site_id: Optional[str] = None) -> List[dict]:
        """
        Search for files across sites.
        
        Note: cwshareddriveutils doesn't have built-in search.
        This implementation lists all files and filters by query.

        Args:
            query: Search query (regex pattern)
            site_id: Optional site ID to search (searches all if None)

        Returns:
            List of matching file information dictionaries
        """
        results = []

        # Determine which sites to search
        site_ids = [site_id] if site_id else list(self.clients.keys())

        for sid in site_ids:
            client = self.clients.get(sid)
            if not client:
                continue

            try:
                # For each configured folder path, list and search
                config = self.site_configs[sid]
                
                # Try to list files from root or configured paths
                # This is a simplified implementation - you may need to adjust based on your folder structure
                folder_paths = getattr(config, 'folder_paths', [''])
                
                for folder_path in folder_paths:
                    try:
                        folder_ref = client.get_or_create_folder_details(folder_path)
                        files = client.workbook_manager.list_folder_items(folder_ref.id)
                        
                        import re
                        for file_info in files:
                            # Search in filename
                            if re.search(query, file_info.get("name", ""), re.IGNORECASE):
                                file_info["site_id"] = sid
                                file_info["site_name"] = config.site_name
                                results.append(file_info)
                    except Exception:
                        # Skip folders that don't exist or can't be accessed
                        continue

            except Exception as e:
                logger.exception(
                    "Error searching files in site '%s' (query=%r): %s",
                    sid,
                    query,
                    e,
                )
                continue

        return results

    def get_site_config(self, site_id: str) -> Optional[SharePointSiteConfig]:
        """Get site configuration by ID."""
        return self.site_configs.get(site_id)

    def get_all_site_configs(self) -> List[SharePointSiteConfig]:
        """Get all site configurations."""
        # logger.info(f"Site configs: {self.site_configs}")
        return list(self.site_configs.values())


# Made with Bob
