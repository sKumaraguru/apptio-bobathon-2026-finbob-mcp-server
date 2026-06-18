"""Cache manager for downloaded files with TTL support."""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path
import tempfile
import shutil

from ..models.internal import CacheEntry

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Cache manager with automatic backend selection.
    
    Automatically selects between local temp storage (development) and S3 storage (AWS Lambda)
    based on environment detection.

    Attributes:
        cache_ttl: Time-to-live for cache entries in hours
        use_s3: Whether S3 backend is being used
        backend: The actual cache backend (self for local, S3CacheBackend for S3)
        cache: Dictionary storing cache entries (local mode only)
        temp_dir: Local temporary directory (local mode only)
    """

    def __init__(self, cache_ttl_hours: int = 4, use_s3: Optional[bool] = None, s3_bucket: Optional[str] = None):
        """
        Initialize cache manager with automatic backend selection.

        Args:
            cache_ttl_hours: Cache TTL in hours (default: 4)
            use_s3: Force S3 backend (None = auto-detect, True = S3, False = local)
            s3_bucket: S3 bucket name (overrides S3_CACHE_BUCKET env var)
            
        Raises:
            ValueError: If S3 is enabled but bucket is not configured
        """
        # Auto-detect backend if not specified
        if use_s3 is None:
            use_s3 = self._should_use_s3()
        
        self.use_s3 = use_s3
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        if self.use_s3:
            # Initialize S3 backend
            bucket = s3_bucket or os.getenv("S3_CACHE_BUCKET")
            if not bucket:
                raise ValueError("S3 cache enabled but S3_CACHE_BUCKET not set")
            
            from .s3_cache import S3CacheBackend
            self.backend = S3CacheBackend(bucket_name=bucket, cache_ttl_hours=cache_ttl_hours)
            logger.info(f"Using S3 cache backend with bucket: {bucket}")
        else:
            # Use local cache (self as backend)
            self.backend = self
            self.cache: Dict[str, CacheEntry] = {}
            self.temp_dir = Path(tempfile.gettempdir()) / "csa_assessments_cache"
            self.temp_dir.mkdir(exist_ok=True)
            logger.info("Using local temp directory cache backend")
    
    @staticmethod
    def _should_use_s3() -> bool:
        """
        Determine if S3 backend should be used based on environment.
        
        Returns:
            True if running in Lambda with S3 bucket configured, False otherwise
        """
        # Check if running in Lambda
        is_lambda = (
            os.getenv("AWS_EXECUTION_ENV") is not None or
            os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
        )
        # Check if S3 bucket is configured
        has_s3_bucket = os.getenv("S3_CACHE_BUCKET") is not None
        
        return is_lambda and has_s3_bucket

    def get(self, file_path: str) -> Optional[str]:
        """
        Get cached file local path if exists and not expired.

        Args:
            file_path: SharePoint file path

        Returns:
            Local file path if cached and valid, None otherwise
        """
        # Delegate to backend if using S3
        if self.use_s3:
            cached_path = self.backend.get(file_path)
            if cached_path:
                logger.info(f"✓ Cache HIT for file_path={file_path}")
            else:
                logger.info(f"✗ Cache MISS for file_path={file_path}")
            return cached_path
        
        # Local implementation
        stats = self.get_stats()
        logger.debug(f"Cache stats: {stats}")
        
        entry = self.cache.get(file_path)

        if entry is None:
            logger.info(f"✗ Cache MISS for file_path={file_path} (not in cache)")
            return None

        # Check if expired
        if datetime.now() > entry.expires_at:
            logger.info(f"✗ Cache MISS for file_path={file_path} (expired)")
            self._remove_entry(file_path)
            return None

        # Check if local file still exists
        if not Path(entry.local_path).exists():
            logger.info(f"✗ Cache MISS for file_path={file_path} (file not found)")
            self._remove_entry(file_path)
            return None

        logger.info(f"✓ Cache HIT for file_path={file_path}, local_path={entry.local_path}")
        return entry.local_path

    def put(self, file_path: str, local_path: str, file_size_bytes: int, report_metadata: dict) -> None:
        """
        Add file to cache.

        Args:
            file_path: SharePoint file path
            local_path: Local file path
            file_size_bytes: File size in bytes
            report_metadata: Report metadata dictionary
        """
        # Delegate to backend if using S3
        if self.use_s3:
            return self.backend.put(file_path, local_path, file_size_bytes, report_metadata)
        
        # Local implementation
        now = datetime.now()
        entry = CacheEntry(
            file_path=file_path,
            local_path=local_path,
            cached_at=now,
            expires_at=now + self.cache_ttl,
            file_size_bytes=file_size_bytes,
            report_metadata=report_metadata,
        )
        self.cache[file_path] = entry

    def _remove_entry(self, file_path: str) -> None:
        """
        Remove entry from cache (internal, assumes lock is held).

        Args:
            file_path: SharePoint file path
        """
        entry = self.cache.pop(file_path, None)
        if entry:
            # Try to delete local file
            try:
                Path(entry.local_path).unlink(missing_ok=True)
            except Exception:
                pass  # Ignore errors during cleanup

    def invalidate(self, file_path: str) -> None:
        """
        Invalidate cache entry for a specific file.

        Args:
            file_path: SharePoint file path
        """
        # Delegate to backend if using S3
        if self.use_s3:
            return self.backend.invalidate(file_path)
        
        # Local implementation
        self._remove_entry(file_path)

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        # Delegate to backend if using S3
        if self.use_s3:
            return self.backend.cleanup_expired()
        
        # Local implementation
        now = datetime.now()
        expired_keys = [key for key, entry in self.cache.items() if now > entry.expires_at]

        for key in expired_keys:
            self._remove_entry(key)

        return len(expired_keys)

    def clear(self) -> None:
        """Clear all cache entries."""
        # Delegate to backend if using S3
        if self.use_s3:
            return self.backend.clear()
        
        # Local implementation
        for file_path in list(self.cache.keys()):
            self._remove_entry(file_path)

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        # Delegate to backend if using S3
        if self.use_s3:
            return self.backend.get_stats()
        
        # Local implementation
        now = datetime.now()
        total_entries = len(self.cache)
        expired_entries = sum(1 for entry in self.cache.values() if now > entry.expires_at)
        total_size = sum(entry.file_size_bytes for entry in self.cache.values())

        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "valid_entries": total_entries - expired_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600,
            "backend_type": "local",
        }

    def __del__(self):
        """Cleanup on deletion."""
        try:
            # Only cleanup local resources if not using S3
            if not self.use_s3:
                self.clear()
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass  # Ignore errors during cleanup


# Made with Bob
