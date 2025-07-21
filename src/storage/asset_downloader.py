"""
Asset download manager for OneNote cache system.

Handles downloading of images, files, and other attachments from OneNote
with proper rate limiting, retry logic, and progress tracking.
"""

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

from ..config.settings import get_settings
from ..models.cache import AssetInfo, AssetDownloadResult, DownloadStatus
from .directory_utils import get_asset_storage_path, sanitize_filename

logger = logging.getLogger(__name__)


class AssetDownloadManager:
    """
    Manages downloading of assets (images, files) from OneNote.
    
    Handles concurrent downloads with rate limiting, retry logic,
    and progress tracking for bulk operations.
    """

    def __init__(self, max_concurrent_downloads: int = 3, 
                 max_retries: int = 3, timeout_seconds: int = 30):
        """
        Initialize the asset download manager.

        Args:
            max_concurrent_downloads: Maximum concurrent download operations
            max_retries: Maximum retry attempts per download
            timeout_seconds: Timeout for individual download operations
        """
        self.settings = get_settings()
        self.max_concurrent_downloads = max_concurrent_downloads
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Progress tracking
        self.download_stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'bytes_downloaded': 0,
            'current_downloads': 0
        }
        
        logger.debug(f"Initialized asset download manager (max concurrent: {max_concurrent_downloads})")

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            headers={
                'User-Agent': 'OneNote-Copilot/1.0'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def download_assets(self, assets: List[AssetInfo], 
                            attachments_dir: Path) -> AssetDownloadResult:
        """
        Download multiple assets to the specified directory.

        Args:
            assets: List of assets to download
            attachments_dir: Base attachments directory

        Returns:
            Download result with statistics
        """
        result = AssetDownloadResult()
        result.total_assets = len(assets)
        
        if not assets:
            result.status = DownloadStatus.COMPLETED
            return result

        try:
            logger.info(f"Starting download of {len(assets)} assets")
            
            # Reset stats
            self.download_stats = {
                'total_downloads': len(assets),
                'successful_downloads': 0,
                'failed_downloads': 0,
                'bytes_downloaded': 0,
                'current_downloads': 0
            }

            # Create semaphore for concurrent downloads
            semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
            
            # Create download tasks
            tasks = [
                self._download_single_asset(semaphore, asset, attachments_dir)
                for asset in assets
            ]

            # Execute downloads with progress tracking
            completed_assets = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, asset_result in enumerate(completed_assets):
                if isinstance(asset_result, Exception):
                    error_msg = f"Download failed for {assets[i].filename}: {asset_result}"
                    logger.error(error_msg)
                    result.failed_downloads.append({
                        'asset': assets[i],
                        'error': str(asset_result)
                    })
                    result.failed_count += 1
                else:
                    if asset_result.get('success', False):
                        result.successful_downloads.append({
                            'asset': assets[i],
                            'local_path': asset_result['local_path'],
                            'size_bytes': asset_result.get('size_bytes', 0)
                        })
                        result.successful_count += 1
                        result.total_bytes += asset_result.get('size_bytes', 0)
                    else:
                        result.failed_downloads.append({
                            'asset': assets[i],
                            'error': asset_result.get('error', 'Unknown error')
                        })
                        result.failed_count += 1

            # Determine final status
            if result.failed_count == 0:
                result.status = DownloadStatus.COMPLETED
            elif result.successful_count > 0:
                result.status = DownloadStatus.COMPLETED_WITH_ERRORS
            else:
                result.status = DownloadStatus.FAILED

            logger.info(f"Asset download completed: {result.successful_count}/{result.total_assets} successful, "
                       f"{result.total_bytes/1024/1024:.1f}MB downloaded")

        except Exception as e:
            result.status = DownloadStatus.FAILED
            error_msg = f"Asset download batch failed: {e}"
            logger.error(error_msg)
            
            # Mark all assets as failed if batch fails
            for asset in assets:
                result.failed_downloads.append({
                    'asset': asset,
                    'error': error_msg
                })
            result.failed_count = len(assets)

        return result

    async def _download_single_asset(self, semaphore: asyncio.Semaphore, 
                                   asset: AssetInfo, attachments_dir: Path) -> Dict[str, any]:
        """
        Download a single asset with retry logic.

        Args:
            semaphore: Concurrency control semaphore
            asset: Asset information
            attachments_dir: Base attachments directory

        Returns:
            Dictionary with download result
        """
        async with semaphore:
            self.download_stats['current_downloads'] += 1
            
            try:
                logger.debug(f"Downloading asset: {asset.filename}")

                # Determine storage path
                storage_path = get_asset_storage_path(
                    attachments_dir, asset.type, asset.filename
                )

                # Check if file already exists and is current
                if await self._is_asset_current(storage_path, asset):
                    logger.debug(f"Asset already current: {asset.filename}")
                    return {
                        'success': True,
                        'local_path': str(storage_path),
                        'size_bytes': storage_path.stat().st_size,
                        'cached': True
                    }

                # Attempt download with retries
                for attempt in range(self.max_retries + 1):
                    try:
                        result = await self._perform_download(asset, storage_path)
                        
                        if result['success']:
                            self.download_stats['successful_downloads'] += 1
                            self.download_stats['bytes_downloaded'] += result.get('size_bytes', 0)
                            
                            # Update asset info with local path
                            asset.local_path = str(storage_path)
                            asset.download_status = "completed"
                            
                            logger.debug(f"Downloaded: {asset.filename} ({result.get('size_bytes', 0)} bytes)")
                            return result
                        else:
                            if attempt < self.max_retries:
                                wait_time = 2 ** attempt  # Exponential backoff
                                logger.warning(f"Download attempt {attempt + 1} failed for {asset.filename}, "
                                             f"retrying in {wait_time}s: {result.get('error')}")
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                raise Exception(result.get('error', 'Download failed'))

                    except Exception as e:
                        if attempt < self.max_retries:
                            wait_time = 2 ** attempt
                            logger.warning(f"Download exception for {asset.filename}, "
                                         f"retrying in {wait_time}s: {e}")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise

                # If we get here, all retries failed
                self.download_stats['failed_downloads'] += 1
                return {'success': False, 'error': 'All retry attempts failed'}

            except Exception as e:
                self.download_stats['failed_downloads'] += 1
                logger.error(f"Download failed for {asset.filename}: {e}")
                return {'success': False, 'error': str(e)}
            
            finally:
                self.download_stats['current_downloads'] -= 1

    async def _perform_download(self, asset: AssetInfo, storage_path: Path) -> Dict[str, any]:
        """
        Perform the actual download operation.

        Args:
            asset: Asset information
            storage_path: Local storage path

        Returns:
            Dictionary with download result
        """
        try:
            if not self.session:
                raise Exception("HTTP session not initialized")

            # Make HTTP request
            async with self.session.get(asset.original_url) as response:
                if response.status != 200:
                    return {
                        'success': False,
                        'error': f"HTTP {response.status}: {response.reason}"
                    }

                # Get content type and size
                content_type = response.headers.get('content-type', '')
                content_length = response.headers.get('content-length')
                size_bytes = int(content_length) if content_length else 0

                # Validate content type if known
                if asset.mime_type and content_type:
                    if not self._is_compatible_mime_type(asset.mime_type, content_type):
                        logger.warning(f"MIME type mismatch for {asset.filename}: "
                                     f"expected {asset.mime_type}, got {content_type}")

                # Ensure storage directory exists
                storage_path.parent.mkdir(parents=True, exist_ok=True)

                # Download content
                with open(storage_path, 'wb') as f:
                    downloaded_bytes = 0
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded_bytes += len(chunk)

                # Verify download
                actual_size = storage_path.stat().st_size
                if size_bytes > 0 and actual_size != size_bytes:
                    logger.warning(f"Size mismatch for {asset.filename}: "
                                 f"expected {size_bytes}, got {actual_size}")

                # Update asset info
                if not asset.mime_type:
                    asset.mime_type = content_type
                asset.size_bytes = actual_size

                return {
                    'success': True,
                    'local_path': str(storage_path),
                    'size_bytes': actual_size,
                    'mime_type': content_type
                }

        except Exception as e:
            # Clean up partial download
            if storage_path.exists():
                try:
                    storage_path.unlink()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup partial download: {cleanup_error}")

            return {'success': False, 'error': str(e)}

    async def _is_asset_current(self, storage_path: Path, asset: AssetInfo) -> bool:
        """
        Check if a locally stored asset is current.

        Args:
            storage_path: Local storage path
            asset: Asset information

        Returns:
            True if asset is current, False otherwise
        """
        try:
            if not storage_path.exists():
                return False

            # Check file size if known
            if asset.size_bytes:
                actual_size = storage_path.stat().st_size
                if actual_size != asset.size_bytes:
                    logger.debug(f"Asset size changed: {asset.filename} "
                               f"({actual_size} vs {asset.size_bytes})")
                    return False

            # Could add more checks here (modification time, hash, etc.)
            
            return True

        except Exception as e:
            logger.warning(f"Failed to check asset currency: {e}")
            return False

    def _is_compatible_mime_type(self, expected: str, actual: str) -> bool:
        """
        Check if MIME types are compatible.

        Args:
            expected: Expected MIME type
            actual: Actual MIME type

        Returns:
            True if types are compatible
        """
        try:
            # Exact match
            if expected == actual:
                return True

            # Handle common variations
            expected_main = expected.split('/')[0]
            actual_main = actual.split('/')[0]
            
            # Allow any image type for images
            if expected_main == 'image' and actual_main == 'image':
                return True
                
            # Allow any text type for text
            if expected_main == 'text' and actual_main == 'text':
                return True

            return False

        except Exception:
            # If we can't parse, assume compatible
            return True

    def get_download_stats(self) -> Dict[str, any]:
        """
        Get current download statistics.

        Returns:
            Dictionary with download statistics
        """
        return self.download_stats.copy()

    async def download_single_asset(self, asset: AssetInfo, 
                                  attachments_dir: Path) -> Dict[str, any]:
        """
        Download a single asset (convenience method).

        Args:
            asset: Asset to download
            attachments_dir: Base attachments directory

        Returns:
            Download result dictionary
        """
        semaphore = asyncio.Semaphore(1)
        return await self._download_single_asset(semaphore, asset, attachments_dir)

    def estimate_download_time(self, assets: List[AssetInfo], 
                             avg_speed_mbps: float = 5.0) -> float:
        """
        Estimate total download time for assets.

        Args:
            assets: List of assets to download
            avg_speed_mbps: Average download speed in Mbps

        Returns:
            Estimated download time in seconds
        """
        try:
            total_bytes = sum(asset.size_bytes or 0 for asset in assets)
            if total_bytes == 0:
                # Estimate based on number of assets if sizes unknown
                estimated_bytes = len(assets) * 100 * 1024  # 100KB per asset average
                total_bytes = estimated_bytes

            # Convert to seconds (accounting for overhead and concurrency)
            bytes_per_second = (avg_speed_mbps * 1024 * 1024) / 8
            base_time = total_bytes / bytes_per_second
            
            # Add overhead for HTTP requests and processing
            overhead_factor = 1.5
            concurrent_factor = min(self.max_concurrent_downloads, len(assets)) / len(assets)
            
            return base_time * overhead_factor * concurrent_factor

        except Exception:
            # Fallback estimate
            return len(assets) * 2.0  # 2 seconds per asset

    async def cleanup_orphaned_downloads(self, attachments_dir: Path, 
                                       valid_assets: List[AssetInfo]) -> int:
        """
        Remove downloaded files that are no longer referenced.

        Args:
            attachments_dir: Base attachments directory
            valid_assets: List of currently valid assets

        Returns:
            Number of files cleaned up
        """
        try:
            if not attachments_dir.exists():
                return 0

            # Get set of valid local paths
            valid_paths = set()
            for asset in valid_assets:
                if asset.local_path:
                    valid_paths.add(Path(asset.local_path))

            # Find and remove orphaned files
            cleaned_count = 0
            for file_path in attachments_dir.rglob("*"):
                if file_path.is_file() and file_path not in valid_paths:
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.debug(f"Cleaned orphaned file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove orphaned file {file_path}: {e}")

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} orphaned asset files")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned downloads: {e}")
            return 0


# Utility functions for working with assets

def extract_assets_from_html(html_content: str, base_url: str = "") -> List[AssetInfo]:
    """
    Extract asset references from HTML content.

    Args:
        html_content: HTML content to scan
        base_url: Base URL for resolving relative links

    Returns:
        List of asset information objects
    """
    assets = []
    
    try:
        import re
        from urllib.parse import urljoin

        # Find image tags
        img_pattern = r'<img[^>]+src=[\'"]([^\'"]+)[\'"][^>]*>'
        for match in re.finditer(img_pattern, html_content, re.IGNORECASE):
            src = match.group(1)
            url = urljoin(base_url, src) if base_url else src
            
            # Extract filename from URL
            filename = Path(urlparse(url).path).name or f"image_{len(assets)}.png"
            
            asset = AssetInfo(
                type="image",
                original_url=url,
                local_path="",
                filename=sanitize_filename(filename),
                mime_type=mimetypes.guess_type(filename)[0]
            )
            assets.append(asset)

        # Find object/embed tags for files
        object_pattern = r'<(?:object|embed)[^>]+(?:src|data)=[\'"]([^\'"]+)[\'"][^>]*>'
        for match in re.finditer(object_pattern, html_content, re.IGNORECASE):
            src = match.group(1)
            url = urljoin(base_url, src) if base_url else src
            
            filename = Path(urlparse(url).path).name or f"file_{len(assets)}.bin"
            
            asset = AssetInfo(
                type="file",
                original_url=url,
                local_path="",
                filename=sanitize_filename(filename),
                mime_type=mimetypes.guess_type(filename)[0]
            )
            assets.append(asset)

        logger.debug(f"Extracted {len(assets)} assets from HTML content")

    except Exception as e:
        logger.error(f"Failed to extract assets from HTML: {e}")

    return assets


def get_asset_type_from_mime(mime_type: str) -> str:
    """
    Determine asset type from MIME type.

    Args:
        mime_type: MIME type string

    Returns:
        Asset type string ('image', 'file', etc.)
    """
    if not mime_type:
        return "file"
    
    if mime_type.startswith("image/"):
        return "image"
    elif mime_type.startswith("video/"):
        return "video"
    elif mime_type.startswith("audio/"):
        return "audio"
    else:
        return "file"
