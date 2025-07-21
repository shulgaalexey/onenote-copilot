"""
Integration tests for AssetDownloadManager.

Tests the real implementation with proper initialization and basic functionality.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.storage.asset_downloader import AssetDownloadManager, extract_assets_from_html
from src.models.cache import AssetInfo, DownloadStatus


class TestAssetDownloadManagerIntegration:
    """Test real AssetDownloadManager integration."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_assets(self):
        """Create sample asset info objects."""
        return [
            AssetInfo(
                type="image",
                original_url="https://example.com/image1.jpg",
                local_path="",
                filename="image1.jpg",
                mime_type="image/jpeg",
                size_bytes=1024
            ),
            AssetInfo(
                type="image", 
                original_url="https://example.com/image2.png",
                local_path="",
                filename="image2.png",
                mime_type="image/png",
                size_bytes=2048
            ),
            AssetInfo(
                type="file",
                original_url="https://example.com/document.pdf",
                local_path="",
                filename="document.pdf",
                mime_type="application/pdf",
                size_bytes=5000
            )
        ]

    def test_initialization(self):
        """Test that AssetDownloadManager can be initialized."""
        manager = AssetDownloadManager()
        
        assert manager is not None
        assert manager.max_concurrent_downloads == 3
        assert manager.max_retries == 3
        assert manager.timeout_seconds == 30
        assert manager.session is None

    def test_initialization_with_params(self):
        """Test initialization with custom parameters."""
        manager = AssetDownloadManager(
            max_concurrent_downloads=5,
            max_retries=2,
            timeout_seconds=60
        )
        
        assert manager.max_concurrent_downloads == 5
        assert manager.max_retries == 2
        assert manager.timeout_seconds == 60

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with AssetDownloadManager() as manager:
            assert manager.session is not None
            # Session should be an aiohttp ClientSession
            assert hasattr(manager.session, 'get')

    @pytest.mark.asyncio
    async def test_download_assets_empty_list(self, temp_dir):
        """Test download with empty asset list."""
        async with AssetDownloadManager() as manager:
            result = await manager.download_assets([], temp_dir / "attachments")
            
            assert result.status == DownloadStatus.COMPLETED
            assert result.total_assets == 0
            assert result.successful_count == 0
            assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_download_single_asset_mock(self, temp_dir, sample_assets):
        """Test download of single asset with mocked HTTP response."""
        asset = sample_assets[0]  # First image asset
        
        # Mock successful HTTP response with proper async iterator
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {
            'content-type': 'image/jpeg',
            'content-length': '1024'
        }
        
        # Create proper async iterator for chunks
        async def mock_chunk_iterator(chunk_size):
            chunks = [b'fake_image_data' for _ in range(10)]
            for chunk in chunks:
                yield chunk
        
        mock_response.content.iter_chunked = mock_chunk_iterator
        
        async with AssetDownloadManager() as manager:
            with patch.object(manager.session, 'get') as mock_get:
                mock_get.return_value.__aenter__.return_value = mock_response
                
                result = await manager.download_single_asset(asset, temp_dir / "attachments")
                
                assert result['success'] is True
                assert 'local_path' in result
                assert result['size_bytes'] > 0
                
                # Verify file was created
                local_path = Path(result['local_path'])
                assert local_path.exists()
                assert local_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_download_assets_mixed_success(self, temp_dir, sample_assets):
        """Test batch download with mixed success/failure."""
        # Mock responses - success for first two, failure for third
        responses = []
        
        # Successful responses
        for i in range(2):
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.headers = {
                'content-type': 'image/jpeg' if i == 0 else 'image/png',
                'content-length': str(1024 * (i + 1))
            }
            
            # Create proper async iterator for chunks
            async def mock_chunk_iterator(chunk_size, data_multiplier=i+1):
                chunks = [b'fake_data' * 10 for _ in range(data_multiplier * 5)]
                for chunk in chunks:
                    yield chunk
            
            mock_response.content.iter_chunked = mock_chunk_iterator
            responses.append(mock_response)
        
        # Failed response
        mock_failed_response = MagicMock()
        mock_failed_response.status = 404
        mock_failed_response.reason = "Not Found"
        responses.append(mock_failed_response)
        
        async with AssetDownloadManager() as manager:
            with patch.object(manager.session, 'get') as mock_get:
                # Configure mock to return different responses
                mock_get.return_value.__aenter__.side_effect = responses
                
                result = await manager.download_assets(sample_assets, temp_dir / "attachments")
                
                assert result.status == DownloadStatus.COMPLETED_WITH_ERRORS
                assert result.total_assets == 3
                assert result.successful_count == 2
                assert result.failed_count == 1
                assert len(result.successful_downloads) == 2
                assert len(result.failed_downloads) == 1

    @pytest.mark.asyncio
    async def test_download_with_retry(self, temp_dir, sample_assets):
        """Test download retry functionality."""
        asset = sample_assets[0]
        
        # Mock failed response that will trigger retry
        mock_failed_response = MagicMock()
        mock_failed_response.status = 503  # Service unavailable
        mock_failed_response.reason = "Service Unavailable"
        
        # Mock successful response after retry
        mock_success_response = MagicMock()
        mock_success_response.status = 200
        mock_success_response.headers = {
            'content-type': 'image/jpeg',
            'content-length': '1024'
        }
        
        # Create proper async iterator for success response
        async def mock_success_chunks(chunk_size):
            chunks = [b'success_data' for _ in range(10)]
            for chunk in chunks:
                yield chunk
        
        mock_success_response.content.iter_chunked = mock_success_chunks
        
        async with AssetDownloadManager(max_retries=2) as manager:
            with patch.object(manager.session, 'get') as mock_get:
                # First call fails, second succeeds
                mock_get.return_value.__aenter__.side_effect = [
                    mock_failed_response, mock_success_response
                ]
                
                # Speed up retry delay for testing
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    result = await manager.download_single_asset(asset, temp_dir / "attachments")
                
                assert result['success'] is True
                assert 'local_path' in result

    def test_get_download_stats(self):
        """Test download statistics tracking."""
        manager = AssetDownloadManager()
        stats = manager.get_download_stats()
        
        assert isinstance(stats, dict)
        assert 'total_downloads' in stats
        assert 'successful_downloads' in stats
        assert 'failed_downloads' in stats
        assert 'bytes_downloaded' in stats
        assert 'current_downloads' in stats

    def test_estimate_download_time(self, sample_assets):
        """Test download time estimation."""
        manager = AssetDownloadManager()
        estimated_time = manager.estimate_download_time(sample_assets)
        
        assert isinstance(estimated_time, float)
        assert estimated_time > 0

    def test_estimate_download_time_empty(self):
        """Test download time estimation with empty list."""
        manager = AssetDownloadManager()
        estimated_time = manager.estimate_download_time([])
        
        assert estimated_time == 0

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_downloads(self, temp_dir, sample_assets):
        """Test cleanup of orphaned download files."""
        attachments_dir = temp_dir / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some test files
        (attachments_dir / "images").mkdir(parents=True, exist_ok=True)
        (attachments_dir / "files").mkdir(parents=True, exist_ok=True)
        
        valid_file = attachments_dir / "images" / "valid.jpg"
        orphaned_file = attachments_dir / "images" / "orphaned.jpg"
        
        valid_file.write_bytes(b"valid image data")
        orphaned_file.write_bytes(b"orphaned image data")
        
        # Update sample assets to reference valid file
        sample_assets[0].local_path = str(valid_file)
        
        manager = AssetDownloadManager()
        cleaned_count = await manager.cleanup_orphaned_downloads(
            attachments_dir, sample_assets[:1]  # Only first asset is valid
        )
        
        assert cleaned_count == 1
        assert valid_file.exists()
        assert not orphaned_file.exists()

    def test_mime_type_compatibility(self):
        """Test MIME type compatibility checking."""
        manager = AssetDownloadManager()
        
        # Test exact match
        assert manager._is_compatible_mime_type("image/jpeg", "image/jpeg") is True
        
        # Test image type compatibility
        assert manager._is_compatible_mime_type("image/jpeg", "image/png") is True
        
        # Test incompatible types
        assert manager._is_compatible_mime_type("image/jpeg", "text/plain") is False
        
        # Test text type compatibility
        assert manager._is_compatible_mime_type("text/plain", "text/html") is True

    def test_extract_assets_from_html(self):
        """Test HTML asset extraction utility."""
        html_content = """
        <div>
            <img src="https://example.com/image1.jpg" alt="Image 1">
            <img src="/local/image2.png" alt="Image 2">
            <object data="https://example.com/document.pdf">
            <embed src="https://example.com/video.mp4">
        </div>
        """
        
        assets = extract_assets_from_html(html_content, "https://example.com")
        
        assert len(assets) >= 2  # Should find at least the images
        
        # Check first asset (image)
        image_asset = next((a for a in assets if a.type == "image"), None)
        assert image_asset is not None
        assert image_asset.original_url.startswith("https://")
        assert image_asset.filename.endswith(('.jpg', '.png'))

    def test_extract_assets_from_empty_html(self):
        """Test HTML asset extraction with empty content."""
        assets = extract_assets_from_html("")
        assert len(assets) == 0

    @pytest.mark.asyncio
    async def test_is_asset_current_missing_file(self, temp_dir, sample_assets):
        """Test asset currency check with missing file."""
        manager = AssetDownloadManager()
        asset = sample_assets[0]
        
        non_existent_path = temp_dir / "missing_file.jpg"
        is_current = await manager._is_asset_current(non_existent_path, asset)
        
        assert is_current is False

    @pytest.mark.asyncio
    async def test_is_asset_current_size_mismatch(self, temp_dir, sample_assets):
        """Test asset currency check with size mismatch."""
        manager = AssetDownloadManager()
        asset = sample_assets[0]
        asset.size_bytes = 1024
        
        test_file = temp_dir / "test_file.jpg"
        test_file.write_bytes(b"different size content")  # Wrong size
        
        is_current = await manager._is_asset_current(test_file, asset)
        
        assert is_current is False

    @pytest.mark.asyncio
    async def test_is_asset_current_correct_size(self, temp_dir, sample_assets):
        """Test asset currency check with correct size."""
        manager = AssetDownloadManager()
        asset = sample_assets[0]
        
        # Create file with correct size
        content = b"x" * asset.size_bytes
        test_file = temp_dir / "test_file.jpg"
        test_file.write_bytes(content)
        
        is_current = await manager._is_asset_current(test_file, asset)
        
        assert is_current is True
