"""
S3-based cache backend for SharePoint file caching.

This module provides persistent caching using AWS S3, enabling cache persistence
across Lambda invocations. Files and metadata are stored in S3 with a
structured layout for efficient retrieval and management.
"""

import json
import hashlib
import tempfile
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..models.internal import CacheEntry

logger = logging.getLogger(__name__)


class S3CacheBackend:
    """
    S3-based cache backend for SharePoint files.
    
    Stores cache metadata and files in S3 with the following structure:
    s3://{bucket}/
    ├── metadata/
    │   └── {sha256(file_path)}.json  # Contains CacheEntry as JSON
    └── files/
        └── {sha256(file_path)}/{original_filename}
    
    Attributes:
        bucket_name: S3 bucket name for cache storage
        cache_ttl: Time-to-live for cache entries
        s3_client: Boto3 S3 client
        temp_dir: Local temporary directory for downloaded files
    """

    def __init__(self, bucket_name: str, cache_ttl_hours: int = 4):
        """
        Initialize S3 cache backend.

        Args:
            bucket_name: S3 bucket name for cache storage
            cache_ttl_hours: Cache TTL in hours (default: 4)
            
        Raises:
            NoCredentialsError: If AWS credentials are not configured
        """
        self.bucket_name = bucket_name
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        # Initialize S3 client
        region = os.environ.get('AWS_REGION', 'us-east-1')
        try:
            self.s3_client = boto3.client('s3', region_name=region)
        except NoCredentialsError:
            logger.error("AWS credentials not configured")
            raise
            
        # Setup local temp directory
        self.temp_dir = Path(tempfile.gettempdir()) / "csa_assessments_cache"
        self.temp_dir.mkdir(exist_ok=True)
        
        logger.info(f"Initialized S3 cache backend with bucket: {bucket_name}, TTL: {cache_ttl_hours}h")

    def _get_file_hash(self, file_path: str) -> str:
        """
        Generate SHA256 hash of file path for S3 key.
        
        Args:
            file_path: SharePoint file path
            
        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(file_path.encode('utf-8')).hexdigest()

    def _get_metadata_key(self, file_path: str) -> str:
        """
        Get S3 key for metadata file.
        
        Args:
            file_path: SharePoint file path
            
        Returns:
            S3 key for metadata
        """
        file_hash = self._get_file_hash(file_path)
        return f"metadata/{file_hash}.json"

    def _get_file_key(self, file_path: str) -> str:
        """
        Get S3 key for cached file.
        
        Args:
            file_path: SharePoint file path
            
        Returns:
            S3 key for file
        """
        file_hash = self._get_file_hash(file_path)
        filename = Path(file_path).name
        return f"files/{file_hash}/{filename}"

    def _get_local_path(self, file_path: str) -> str:
        """
        Get local temporary path for cached file.
        
        Args:
            file_path: SharePoint file path
            
        Returns:
            Local file path
        """
        file_hash = self._get_file_hash(file_path)
        filename = Path(file_path).name
        return str(self.temp_dir / f"{file_hash}_{filename}")

    def _cache_entry_to_dict(self, entry: CacheEntry) -> Dict[str, Any]:
        """
        Convert CacheEntry to dictionary for JSON serialization.
        
        Args:
            entry: Cache entry to convert
            
        Returns:
            Dictionary representation
        """
        return {
            "file_path": entry.file_path,
            "local_path": entry.local_path,
            "cached_at": entry.cached_at.isoformat(),
            "expires_at": entry.expires_at.isoformat(),
            "file_size_bytes": entry.file_size_bytes,
            "report_metadata": entry.report_metadata
        }

    def _dict_to_cache_entry(self, data: Dict[str, Any]) -> CacheEntry:
        """
        Convert dictionary to CacheEntry.
        
        Args:
            data: Dictionary representation
            
        Returns:
            CacheEntry object
        """
        return CacheEntry(
            file_path=data["file_path"],
            local_path=data["local_path"],
            cached_at=datetime.fromisoformat(data["cached_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            file_size_bytes=data["file_size_bytes"],
            report_metadata=data["report_metadata"]
        )

    def get(self, file_path: str) -> Optional[str]:
        """
        Get cached file local path if exists and not expired.
        
        Downloads file from S3 to local temp directory if valid cache entry exists.
        
        Args:
            file_path: SharePoint file path
            
        Returns:
            Local file path if cached and valid, None otherwise
        """
        try:
            # Get metadata from S3
            metadata_key = self._get_metadata_key(file_path)
            
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=metadata_key)
                metadata_json = response['Body'].read().decode('utf-8')
                metadata = json.loads(metadata_json)
                entry = self._dict_to_cache_entry(metadata)
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    logger.debug(f"No cache metadata found for: {file_path}")
                    return None
                else:
                    logger.error(f"Error retrieving cache metadata for {file_path}: {e}")
                    return None
            
            # Check if expired
            if datetime.now() > entry.expires_at:
                logger.debug(f"Cache entry expired for: {file_path}")
                self.invalidate(file_path)
                return None
            
            # Get local path and check if file already exists locally
            local_path = self._get_local_path(file_path)
            if Path(local_path).exists():
                logger.debug(f"Cache hit (local file exists): {file_path}")
                return local_path
            
            # Download file from S3 to local temp
            file_key = self._get_file_key(file_path)
            try:
                self.s3_client.download_file(self.bucket_name, file_key, local_path)
                logger.debug(f"Cache hit (downloaded from S3): {file_path}")
                return local_path
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    logger.warning(f"Cache metadata exists but file missing in S3: {file_path}")
                    self.invalidate(file_path)
                    return None
                else:
                    logger.error(f"Error downloading cached file from S3: {e}")
                    return None
                    
        except Exception as e:
            logger.error(f"Unexpected error in cache get for {file_path}: {e}")
            return None

    def put(self, file_path: str, local_path: str, file_size_bytes: int, report_metadata: dict) -> None:
        """
        Add file to S3 cache.
        
        Uploads both the file and its metadata to S3.
        
        Args:
            file_path: SharePoint file path
            local_path: Local file path to cache
            file_size_bytes: File size in bytes
            report_metadata: Report metadata dictionary
        """
        try:
            now = datetime.now()
            
            # Create cache entry
            cache_local_path = self._get_local_path(file_path)
            entry = CacheEntry(
                file_path=file_path,
                local_path=cache_local_path,
                cached_at=now,
                expires_at=now + self.cache_ttl,
                file_size_bytes=file_size_bytes,
                report_metadata=report_metadata,
            )
            
            # Upload file to S3
            file_key = self._get_file_key(file_path)
            self.s3_client.upload_file(local_path, self.bucket_name, file_key)
            
            # Upload metadata to S3
            metadata_key = self._get_metadata_key(file_path)
            metadata_json = json.dumps(self._cache_entry_to_dict(entry), indent=2)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=metadata_json.encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.debug(f"Cached file to S3: {file_path}")
            
        except Exception as e:
            logger.error(f"Error caching file to S3 {file_path}: {e}")
            raise

    def invalidate(self, file_path: str) -> None:
        """
        Invalidate cache entry for a specific file.
        
        Removes both file and metadata from S3, and local temp file if it exists.
        
        Args:
            file_path: SharePoint file path
        """
        try:
            # Delete from S3
            metadata_key = self._get_metadata_key(file_path)
            file_key = self._get_file_key(file_path)
            
            # Delete metadata
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=metadata_key)
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchKey':
                    logger.warning(f"Error deleting metadata from S3: {e}")
            
            # Delete file
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchKey':
                    logger.warning(f"Error deleting file from S3: {e}")
            
            # Delete local temp file
            local_path = self._get_local_path(file_path)
            try:
                Path(local_path).unlink(missing_ok=True)
            except Exception:
                pass  # Ignore errors during local cleanup
                
            logger.debug(f"Invalidated cache entry: {file_path}")
            
        except Exception as e:
            logger.error(f"Error invalidating cache entry {file_path}: {e}")

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries from S3.
        
        Lists all metadata files, checks expiration, and removes expired entries.
        
        Returns:
            Number of entries removed
        """
        removed_count = 0
        
        try:
            # List all metadata files
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix='metadata/')
            
            now = datetime.now()
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    metadata_key = obj['Key']
                    
                    try:
                        # Get metadata
                        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=metadata_key)
                        metadata_json = response['Body'].read().decode('utf-8')
                        metadata = json.loads(metadata_json)
                        entry = self._dict_to_cache_entry(metadata)
                        
                        # Check if expired
                        if now > entry.expires_at:
                            self.invalidate(entry.file_path)
                            removed_count += 1
                            
                    except Exception as e:
                        logger.warning(f"Error processing metadata file {metadata_key}: {e}")
                        continue
            
            logger.info(f"Cleaned up {removed_count} expired cache entries")
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            
        return removed_count

    def clear(self) -> None:
        """
        Remove all cache entries from S3.
        
        Deletes all files and metadata from the S3 bucket cache.
        """
        try:
            # List and delete all objects with metadata/ and files/ prefixes
            for prefix in ['metadata/', 'files/']:
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
                
                for page in pages:
                    if 'Contents' not in page:
                        continue
                        
                    # Delete objects in batches
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                    
                    if objects_to_delete:
                        self.s3_client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': objects_to_delete}
                        )
            
            # Clear local temp directory
            if self.temp_dir.exists():
                for file_path in self.temp_dir.glob("*"):
                    try:
                        file_path.unlink()
                    except Exception:
                        pass  # Ignore errors during cleanup
            
            logger.info("Cleared all cache entries from S3")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def get_stats(self) -> dict:
        """
        Get cache statistics by querying S3.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            # List all metadata files to get statistics
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix='metadata/')
            
            total_entries = 0
            expired_entries = 0
            total_size = 0
            now = datetime.now()
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    total_entries += 1
                    
                    try:
                        # Get metadata to check expiration and size
                        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=obj['Key'])
                        metadata_json = response['Body'].read().decode('utf-8')
                        metadata = json.loads(metadata_json)
                        entry = self._dict_to_cache_entry(metadata)
                        
                        if now > entry.expires_at:
                            expired_entries += 1
                        
                        total_size += entry.file_size_bytes
                        
                    except Exception as e:
                        logger.warning(f"Error processing metadata for stats: {e}")
                        continue
            
            return {
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "valid_entries": total_entries - expired_entries,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600,
                "backend_type": "s3",
                "bucket_name": self.bucket_name,
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "total_entries": 0,
                "expired_entries": 0,
                "valid_entries": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
                "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600,
                "backend_type": "s3",
                "bucket_name": self.bucket_name,
                "error": str(e),
            }


# Made with Bob