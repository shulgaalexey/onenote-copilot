"""
Unit tests for directory utilities.

Tests the directory structure management, path sanitization,
and organizational functions for the cache system.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.storage.directory_utils import (cleanup_empty_directories,
                                         create_cache_directory_structure,
                                         find_duplicate_assets,
                                         get_asset_storage_path,
                                         get_cache_size_breakdown,
                                         get_directory_summary,
                                         organize_by_date_hierarchy,
                                         sanitize_directory_name,
                                         sanitize_filename,
                                         validate_cache_structure)


class TestSanitization:
    """Test filename and directory name sanitization."""

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        assert sanitize_filename("hello world.txt") == "hello world.txt"
        assert sanitize_filename("normal_file.md") == "normal_file.md"

    def test_sanitize_filename_unsafe_chars(self):
        """Test removal of unsafe characters."""
        unsafe = 'file<>:"/\\|?*.txt'
        result = sanitize_filename(unsafe)
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result
        assert result.endswith(".txt")

    def test_sanitize_filename_empty_input(self):
        """Test handling of empty or whitespace-only input."""
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("   ") == "untitled"
        assert sanitize_filename("...") == "untitled"

    def test_sanitize_filename_length_limit(self):
        """Test filename length limiting."""
        long_name = "a" * 150 + ".txt"
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50
        assert result.endswith(".txt")  # Extension preserved

    def test_sanitize_filename_multiple_underscores(self):
        """Test consolidation of multiple underscores."""
        result = sanitize_filename("file___with____many_____underscores.txt")
        assert "___" not in result
        assert result == "file_with_many_underscores.txt"

    def test_sanitize_directory_name(self):
        """Test directory name sanitization."""
        result = sanitize_directory_name("My Folder.Name")
        assert "." not in result  # Dots removed from directories
        assert result == "My Folder_Name"

    def test_sanitize_directory_name_empty(self):
        """Test directory name with empty input."""
        assert sanitize_directory_name("") == "untitled_dir"
        assert sanitize_directory_name("...") == "untitled_dir"


class TestDirectoryStructure:
    """Test directory structure creation and management."""

    @pytest.fixture
    def temp_base_dir(self, tmp_path):
        """Create a temporary base directory for testing."""
        return tmp_path / "cache_test"

    def test_create_cache_directory_structure(self, temp_base_dir):
        """Test complete directory structure creation."""
        paths = create_cache_directory_structure(
            temp_base_dir, "user123", "notebook456", "section789", "page321"
        )

        # Check all paths exist
        assert paths['user_root'].exists()
        assert paths['notebook_root'].exists()
        assert paths['section_root'].exists()
        assert paths['page_root'].exists()
        assert paths['attachments_root'].exists()
        assert paths['images_dir'].exists()
        assert paths['files_dir'].exists()

        # Check path structure
        assert "user123" in str(paths['user_root'])
        assert "notebook456" in str(paths['notebook_root'])
        assert "section789" in str(paths['section_root'])
        assert "page321" in str(paths['page_root'])

    def test_create_cache_directory_structure_unsafe_names(self, temp_base_dir):
        """Test directory creation with unsafe names."""
        paths = create_cache_directory_structure(
            temp_base_dir,
            "user@domain.com",
            'nb<>:bad|chars',
            "sec/with\\slash",
            "page?wild*"
        )

        # All directories should be created despite unsafe names
        assert paths['user_root'].exists()
        assert paths['notebook_root'].exists()
        assert paths['section_root'].exists()
        assert paths['page_root'].exists()

        # Check that unsafe characters were sanitized
        assert "<" not in str(paths['notebook_root'])
        assert "/" not in str(paths['section_root'])
        assert "?" not in str(paths['page_root'])

    def test_get_asset_storage_path(self, tmp_path):
        """Test asset storage path generation."""
        attachments_dir = tmp_path / "attachments"
        attachments_dir.mkdir()

        # Test image path
        image_path = get_asset_storage_path(
            attachments_dir, "image", "test.png", "img123"
        )
        assert "images" in str(image_path)
        assert "img123" in str(image_path)
        assert "test.png" in str(image_path)

        # Test file path
        file_path = get_asset_storage_path(
            attachments_dir, "file", "document.pdf"
        )
        assert "files" in str(file_path)
        assert "document.pdf" in str(file_path)

        # Test unknown type defaults to files
        unknown_path = get_asset_storage_path(
            attachments_dir, "unknown", "mystery.xyz"
        )
        assert "files" in str(unknown_path)

    def test_organize_by_date_hierarchy(self, tmp_path):
        """Test date-based organization."""
        test_date = datetime(2024, 3, 15)

        result_path = organize_by_date_hierarchy(
            tmp_path, test_date, "Test Notebook", "Test Page"
        )

        assert result_path.exists()
        assert "2024" in str(result_path)
        assert "03" in str(result_path)
        assert "Test Notebook" in str(result_path)
        assert "Test Page" in str(result_path)


class TestDirectoryValidation:
    """Test directory validation and analysis."""

    @pytest.fixture
    def valid_cache_dir(self, tmp_path):
        """Create a valid cache directory structure."""
        cache_dir = tmp_path / "valid_cache"
        cache_dir.mkdir()

        # Create required directories
        (cache_dir / "notebooks").mkdir()
        (cache_dir / "global").mkdir()

        # Create required files
        (cache_dir / "cache_metadata.json").write_text('{"user_id": "test"}')
        (cache_dir / "sync_status.json").write_text('{"sync_in_progress": false}')

        return cache_dir

    @pytest.fixture
    def invalid_cache_dir(self, tmp_path):
        """Create an invalid cache directory structure."""
        cache_dir = tmp_path / "invalid_cache"
        cache_dir.mkdir()
        # Missing required subdirectories and files
        return cache_dir

    def test_validate_cache_structure_valid(self, valid_cache_dir):
        """Test validation of a valid cache structure."""
        validation = validate_cache_structure(valid_cache_dir)

        assert validation['user_dir_exists'] is True
        assert validation['notebooks_dir'] is True
        assert validation['global_dir'] is True
        assert validation['cache_metadata'] is True
        assert validation['sync_status'] is True
        assert validation['writable'] is True
        assert validation['overall_valid'] is True

    def test_validate_cache_structure_invalid(self, invalid_cache_dir):
        """Test validation of an invalid cache structure."""
        validation = validate_cache_structure(invalid_cache_dir)

        assert validation['user_dir_exists'] is True  # Directory exists
        assert validation['notebooks_dir'] is False  # Missing subdirs
        assert validation['global_dir'] is False
        assert validation['cache_metadata'] is False  # Missing files
        assert validation['sync_status'] is False
        assert validation['overall_valid'] is False

    def test_validate_cache_structure_nonexistent(self, tmp_path):
        """Test validation of nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"
        validation = validate_cache_structure(nonexistent)

        assert validation['user_dir_exists'] is False
        assert validation['overall_valid'] is False

    def test_get_cache_size_breakdown(self, tmp_path):
        """Test cache size breakdown calculation."""
        cache_dir = tmp_path / "size_test"
        cache_dir.mkdir()

        # Create test files of different types
        (cache_dir / "metadata.json").write_text('{"test": "data"}')
        (cache_dir / "content.md").write_text("# Test Content")
        (cache_dir / "page.html").write_text("<html><body>Test</body></html>")

        # Create images directory with test image
        images_dir = cache_dir / "images"
        images_dir.mkdir()
        (images_dir / "test.png").write_bytes(b"fake image data")

        breakdown = get_cache_size_breakdown(cache_dir)

        assert breakdown['metadata'] > 0
        assert breakdown['content_md'] > 0
        assert breakdown['content_html'] > 0
        assert breakdown['images'] > 0
        assert breakdown['total'] > 0
        assert breakdown['total'] == (breakdown['metadata'] +
                                     breakdown['content_md'] +
                                     breakdown['content_html'] +
                                     breakdown['images'] +
                                     breakdown['files'] +
                                     breakdown['other'])

    def test_get_directory_summary(self, tmp_path):
        """Test directory summary generation."""
        # Create a mock cache structure
        cache_dir = tmp_path / "summary_test"
        cache_dir.mkdir()

        notebooks_dir = cache_dir / "notebooks" / "nb1" / "sections" / "sec1" / "pages" / "page1"
        notebooks_dir.mkdir(parents=True)

        # Add some files
        (notebooks_dir / "content.md").write_text("Test content")
        (notebooks_dir / "metadata.json").write_text('{"test": true}')

        # Add attachments
        attachments_dir = notebooks_dir / "attachments"
        (attachments_dir / "images").mkdir(parents=True)
        (attachments_dir / "files").mkdir(parents=True)
        (attachments_dir / "images" / "test.png").write_bytes(b"image")
        (attachments_dir / "files" / "doc.pdf").write_bytes(b"document")

        summary = get_directory_summary(cache_dir)

        assert summary['exists'] is True
        assert summary['notebooks'] == 1
        assert summary['sections'] == 1
        assert summary['pages'] == 1
        assert summary['images'] == 1
        assert summary['files'] == 1
        assert summary['total_size_bytes'] > 0
        assert summary['total_files'] > 0


class TestDirectoryMaintenance:
    """Test directory maintenance operations."""

    def test_cleanup_empty_directories(self, tmp_path):
        """Test removal of empty directories."""
        # Create directory structure with some empty dirs
        base_dir = tmp_path / "cleanup_test"
        base_dir.mkdir()

        # Create nested empty directories
        (base_dir / "empty1").mkdir()
        (base_dir / "empty2" / "nested_empty").mkdir(parents=True)

        # Create directory with content
        content_dir = base_dir / "with_content"
        content_dir.mkdir()
        (content_dir / "file.txt").write_text("content")

        removed_count = cleanup_empty_directories(base_dir, preserve_root=True)

        # Should remove empty directories but preserve root and content dir
        assert base_dir.exists()  # Root preserved
        assert content_dir.exists()  # Has content
        assert not (base_dir / "empty1").exists()  # Empty, removed
        assert not (base_dir / "empty2").exists()  # Empty after nested removal
        assert removed_count >= 2

    def test_find_duplicate_assets(self, tmp_path):
        """Test duplicate asset detection."""
        attachments_dir = tmp_path / "attachments"
        attachments_dir.mkdir()

        # Create some duplicate files
        content1 = b"This is test content for duplication"
        content2 = b"Different content"

        (attachments_dir / "file1.txt").write_bytes(content1)
        (attachments_dir / "file1_copy.txt").write_bytes(content1)  # Duplicate
        (attachments_dir / "file2.txt").write_bytes(content2)  # Unique
        (attachments_dir / "file3.txt").write_bytes(content1)  # Another duplicate

        duplicates = find_duplicate_assets(attachments_dir)

        # Should find one group of duplicates (3 files with same content)
        assert len(duplicates) == 1
        assert duplicates[0]['count'] == 3
        assert len(duplicates[0]['files']) == 3

        # All three duplicate files should be listed
        file_names = [Path(f).name for f in duplicates[0]['files']]
        assert "file1.txt" in file_names
        assert "file1_copy.txt" in file_names
        assert "file3.txt" in file_names

    def test_find_duplicate_assets_no_duplicates(self, tmp_path):
        """Test duplicate detection with no duplicates."""
        attachments_dir = tmp_path / "attachments"
        attachments_dir.mkdir()

        # Create unique files
        (attachments_dir / "file1.txt").write_bytes(b"Content 1")
        (attachments_dir / "file2.txt").write_bytes(b"Content 2")
        (attachments_dir / "file3.txt").write_bytes(b"Content 3")

        duplicates = find_duplicate_assets(attachments_dir)
        assert len(duplicates) == 0

    @patch('src.storage.directory_utils.logger')
    def test_error_handling(self, mock_logger, tmp_path):
        """Test error handling in various operations."""
        # Test with nonexistent directory
        nonexistent_dir = tmp_path / "does_not_exist"

        # Operations should handle errors gracefully
        breakdown = get_cache_size_breakdown(nonexistent_dir)
        assert breakdown['total'] == 0  # Should return empty breakdown

        validation = validate_cache_structure(nonexistent_dir)
        assert validation['user_dir_exists'] is False

        summary = get_directory_summary(nonexistent_dir)
        assert summary['exists'] is False


class TestIntegration:
    """Integration tests for directory utilities."""

    def test_full_cache_directory_workflow(self, tmp_path):
        """Test complete directory management workflow."""
        base_cache = tmp_path / "full_workflow"

        # Step 1: Create structure
        paths = create_cache_directory_structure(
            base_cache, "user123", "notebook456", "section789", "page321"
        )

        # Step 2: Add some assets
        image_path = get_asset_storage_path(
            paths['attachments_root'], "image", "test.png", "img001"
        )
        file_path = get_asset_storage_path(
            paths['attachments_root'], "file", "document.pdf", "doc001"
        )

        # Create the asset files
        image_path.write_bytes(b"fake image content")
        file_path.write_bytes(b"fake document content")

        # Step 3: Validate structure
        validation = validate_cache_structure(paths['user_root'])
        # Note: This will fail because we need metadata files for full validation
        assert validation['user_dir_exists'] is True
        assert validation['writable'] is True

        # Step 4: Get size breakdown
        breakdown = get_cache_size_breakdown(paths['user_root'])
        assert breakdown['images'] > 0
        assert breakdown['files'] > 0  # Should find the file we created
        assert breakdown['total'] > 0

        # Step 5: Generate summary
        summary = get_directory_summary(paths['user_root'])
        assert summary['exists'] is True
        assert summary['notebooks'] == 1
        assert summary['sections'] == 1
        assert summary['pages'] == 1
        assert summary['images'] == 1
        assert summary['files'] == 1

    def test_directory_utilities_with_complex_names(self, tmp_path):
        """Test directory utilities with complex, real-world names."""
        complex_names = {
            'user': 'user@company.com',
            'notebook': 'Meeting Notes Q4',
            'section': 'Team Meetings',
            'page': 'Sprint Planning'
        }

        # Should handle complex names without errors
        paths = create_cache_directory_structure(
            tmp_path / "complex",
            complex_names['user'],
            complex_names['notebook'],
            complex_names['section'],
            complex_names['page']
        )

        # All paths should be created successfully
        for path_name, path in paths.items():
            if path_name != 'base':
                assert path.exists(), f"Path {path_name} was not created: {path}"

        # Asset storage should also work with complex names
        asset_path = get_asset_storage_path(
            paths['attachments_root'],
            "image",
            "Screenshot.png",
            "img-001"
        )

        asset_path.write_bytes(b"screenshot data")
        assert asset_path.exists()

        # Summary should reflect the structure correctly
        summary = get_directory_summary(paths['user_root'])
        assert summary['notebooks'] == 1
        assert summary['sections'] == 1
        assert summary['pages'] == 1
