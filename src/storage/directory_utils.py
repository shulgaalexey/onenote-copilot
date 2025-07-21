"""
Directory structure utilities for OneNote cache system.

Provides helper functions for managing cache directory structures,
path sanitization, and organizational hierarchy.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    Sanitize a filename for cross-platform filesystem safety.
    
    Args:
        filename: Original filename or title
        max_length: Maximum allowed filename length
        
    Returns:
        Safe filename for filesystem use
    """
    # Remove/replace unsafe characters
    unsafe_chars = r'[<>:"/\\|?*\x00-\x1f]'
    safe_name = re.sub(unsafe_chars, '_', filename)
    
    # Remove multiple consecutive underscores
    safe_name = re.sub(r'_+', '_', safe_name)
    
    # Remove leading/trailing whitespace and dots
    safe_name = safe_name.strip(' .')
    
    # Ensure not empty
    if not safe_name:
        safe_name = "untitled"
    
    # Truncate if too long, preserving extension if present
    if len(safe_name) > max_length:
        parts = safe_name.rsplit('.', 1)
        if len(parts) == 2 and len(parts[1]) <= 10:  # Has reasonable extension
            name_part = parts[0][:max_length - len(parts[1]) - 1]
            safe_name = f"{name_part}.{parts[1]}"
        else:
            safe_name = safe_name[:max_length]
    
    return safe_name


def sanitize_directory_name(dirname: str, max_length: int = 50) -> str:  # Reduced from 80
    """
    Sanitize a directory name for filesystem safety.
    
    Args:
        dirname: Original directory name
        max_length: Maximum allowed directory name length
        
    Returns:
        Safe directory name for filesystem use
    """
    # Use filename sanitization but be more restrictive
    safe_name = sanitize_filename(dirname, max_length)
    
    # Remove dots from directory names (problematic on some systems)
    safe_name = safe_name.replace('.', '_')
    
    # Ensure doesn't end with space or period
    safe_name = safe_name.rstrip(' .')
    
    # Override the default from sanitize_filename for directories
    if safe_name == "untitled":
        safe_name = "untitled_dir"
    
    return safe_name


def create_cache_directory_structure(base_path: Path, user_id: str, notebook_id: str, 
                                    section_id: str, page_id: str) -> Dict[str, Path]:
    """
    Create the complete directory structure for a cached page.
    
    Args:
        base_path: Base cache directory path
        user_id: User identifier
        notebook_id: Notebook identifier  
        section_id: Section identifier
        page_id: Page identifier
        
    Returns:
        Dictionary mapping structure names to paths
        
    Raises:
        OSError: If directories cannot be created
    """
    try:
        # Build sanitized path components
        safe_user_id = sanitize_directory_name(user_id)
        safe_notebook_id = sanitize_directory_name(notebook_id)
        safe_section_id = sanitize_directory_name(section_id)
        safe_page_id = sanitize_directory_name(page_id)
        
        # Create path hierarchy
        paths = {}
        paths['base'] = base_path
        paths['user_root'] = base_path / "users" / safe_user_id
        paths['notebook_root'] = paths['user_root'] / "notebooks" / safe_notebook_id
        paths['section_root'] = paths['notebook_root'] / "sections" / safe_section_id
        paths['page_root'] = paths['section_root'] / "pages" / safe_page_id
        paths['attachments_root'] = paths['page_root'] / "attachments"
        paths['images_dir'] = paths['attachments_root'] / "images"
        paths['files_dir'] = paths['attachments_root'] / "files"
        
        # Create all directories
        for name, path in paths.items():
            if name != 'base':  # Don't create base if it doesn't exist
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {name} -> {path}")
        
        return paths
        
    except Exception as e:
        logger.error(f"Failed to create cache directory structure: {e}")
        raise


def get_asset_storage_path(attachments_dir: Path, asset_type: str, 
                          filename: str, asset_id: Optional[str] = None) -> Path:
    """
    Generate appropriate storage path for an asset.
    
    Args:
        attachments_dir: Base attachments directory
        asset_type: Type of asset ('image', 'file', etc.)
        filename: Original filename
        asset_id: Optional asset ID for uniqueness
        
    Returns:
        Path where asset should be stored
    """
    # Sanitize filename
    safe_filename = sanitize_filename(filename)
    
    # Add asset ID prefix if provided for uniqueness
    if asset_id:
        safe_id = sanitize_filename(asset_id, 20)  # Keep ID short
        name_parts = safe_filename.rsplit('.', 1)
        if len(name_parts) == 2:
            safe_filename = f"{safe_id}_{name_parts[0]}.{name_parts[1]}"
        else:
            safe_filename = f"{safe_id}_{safe_filename}"
    
    # Route to appropriate subdirectory and ensure it exists
    if asset_type == "image":
        target_dir = attachments_dir / "images"
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / safe_filename
    elif asset_type == "file":
        target_dir = attachments_dir / "files"
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / safe_filename
    else:
        # Default to files directory for unknown types
        target_dir = attachments_dir / "files"
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / safe_filename


def organize_by_date_hierarchy(base_path: Path, created_date, 
                              notebook_name: str, page_title: str) -> Path:
    """
    Create date-based organizational structure for pages.
    
    Args:
        base_path: Base directory for organization
        created_date: Page creation date
        notebook_name: Notebook name
        page_title: Page title
        
    Returns:
        Path for date-organized storage
    """
    try:
        year = str(created_date.year)
        month = f"{created_date.month:02d}"
        
        safe_notebook = sanitize_directory_name(notebook_name)
        safe_title = sanitize_filename(page_title)
        
        # Create: base/YYYY/MM/notebook_name/page_title
        date_path = base_path / year / month / safe_notebook / safe_title
        date_path.mkdir(parents=True, exist_ok=True)
        
        return date_path
        
    except Exception as e:
        logger.warning(f"Failed to create date hierarchy, using default: {e}")
        # Fallback to simple structure
        safe_notebook = sanitize_directory_name(notebook_name)
        fallback_path = base_path / safe_notebook / sanitize_filename(page_title)
        fallback_path.mkdir(parents=True, exist_ok=True)
        return fallback_path


def validate_cache_structure(user_cache_dir: Path) -> Dict[str, bool]:
    """
    Validate that a user's cache directory has proper structure.
    
    Args:
        user_cache_dir: Path to user's cache directory
        
    Returns:
        Dictionary mapping structure elements to validation status
    """
    validation = {}
    
    # Check essential directories
    validation['user_dir_exists'] = user_cache_dir.exists()
    validation['notebooks_dir'] = (user_cache_dir / "notebooks").exists()
    validation['global_dir'] = (user_cache_dir / "global").exists()
    
    # Check metadata files
    validation['cache_metadata'] = (user_cache_dir / "cache_metadata.json").exists()
    validation['sync_status'] = (user_cache_dir / "sync_status.json").exists()
    
    # Check permissions (try to create a temp file)
    try:
        temp_file = user_cache_dir / ".permission_test"
        temp_file.touch()
        temp_file.unlink()
        validation['writable'] = True
    except (OSError, PermissionError):
        validation['writable'] = False
    
    validation['overall_valid'] = all(validation.values())
    
    return validation


def get_cache_size_breakdown(user_cache_dir: Path) -> Dict[str, int]:
    """
    Calculate storage breakdown for a user's cache.
    
    Args:
        user_cache_dir: Path to user's cache directory
        
    Returns:
        Dictionary with size breakdown in bytes
    """
    breakdown = {
        'metadata': 0,
        'content_md': 0,
        'content_html': 0,
        'images': 0,
        'files': 0,
        'other': 0,
        'total': 0
    }
    
    if not user_cache_dir.exists():
        return breakdown
    
    try:
        for item in user_cache_dir.rglob("*"):
            if not item.is_file():
                continue
                
            size = item.stat().st_size
            filename = item.name.lower()
            
            # Categorize by file type
            if filename.endswith('.json'):
                breakdown['metadata'] += size
            elif filename.endswith('.md'):
                breakdown['content_md'] += size
            elif filename.endswith('.html'):
                breakdown['content_html'] += size
            elif filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')):
                breakdown['images'] += size
            elif 'images' in str(item.parent):  # Path-agnostic check
                breakdown['images'] += size
            elif 'files' in str(item.parent):   # Path-agnostic check
                breakdown['files'] += size
            else:
                breakdown['other'] += size
                
            breakdown['total'] += size
            
    except Exception as e:
        logger.warning(f"Failed to calculate cache size breakdown: {e}")
    
    return breakdown


def cleanup_empty_directories(base_path: Path, preserve_root: bool = True) -> int:
    """
    Remove empty directories from cache structure.
    
    Args:
        base_path: Base path to clean up
        preserve_root: Whether to preserve the root directory itself
        
    Returns:
        Number of directories removed
    """
    removed_count = 0
    
    try:
        # Get all directories, sorted by depth (deepest first)
        all_dirs = [d for d in base_path.rglob("*") if d.is_dir()]
        all_dirs.sort(key=lambda x: len(x.parts), reverse=True)
        
        for directory in all_dirs:
            if preserve_root and directory == base_path:
                continue
                
            try:
                # Check if directory is empty
                if not any(directory.iterdir()):
                    directory.rmdir()
                    removed_count += 1
                    logger.debug(f"Removed empty directory: {directory}")
                    
            except OSError as e:
                # Directory not empty or permission denied
                logger.debug(f"Could not remove directory {directory}: {e}")
                continue
                
    except Exception as e:
        logger.warning(f"Error during directory cleanup: {e}")
    
    return removed_count


def find_duplicate_assets(attachments_dir: Path) -> List[Dict[str, any]]:
    """
    Find duplicate asset files in the attachments directory.
    
    Args:
        attachments_dir: Path to attachments directory
        
    Returns:
        List of dictionaries describing duplicate sets
    """
    duplicates = []
    
    if not attachments_dir.exists():
        return duplicates
    
    try:
        # Group files by size first (quick check)
        size_groups = {}
        
        for asset_file in attachments_dir.rglob("*"):
            if not asset_file.is_file():
                continue
                
            size = asset_file.stat().st_size
            if size not in size_groups:
                size_groups[size] = []
            size_groups[size].append(asset_file)
        
        # Check for content duplicates within same-size groups
        import hashlib
        
        for size, files in size_groups.items():
            if len(files) < 2:
                continue
                
            # Calculate hashes for files of same size
            hash_groups = {}
            
            for file_path in files:
                try:
                    hasher = hashlib.md5()
                    with open(file_path, 'rb') as f:
                        hasher.update(f.read())
                    file_hash = hasher.hexdigest()
                    
                    if file_hash not in hash_groups:
                        hash_groups[file_hash] = []
                    hash_groups[file_hash].append(file_path)
                    
                except Exception as e:
                    logger.warning(f"Failed to hash file {file_path}: {e}")
                    continue
            
            # Report duplicate groups
            for file_hash, duplicate_files in hash_groups.items():
                if len(duplicate_files) > 1:
                    duplicates.append({
                        'hash': file_hash,
                        'size_bytes': size,
                        'files': [str(f) for f in duplicate_files],
                        'count': len(duplicate_files)
                    })
                    
    except Exception as e:
        logger.error(f"Failed to find duplicate assets: {e}")
    
    return duplicates


def get_directory_summary(cache_dir: Path) -> Dict[str, any]:
    """
    Generate a comprehensive summary of cache directory contents.
    
    Args:
        cache_dir: Path to cache directory
        
    Returns:
        Dictionary with directory summary information
    """
    summary = {
        'path': str(cache_dir),
        'exists': cache_dir.exists(),
        'total_size_bytes': 0,
        'total_files': 0,
        'total_directories': 0,
        'notebooks': 0,
        'sections': 0,
        'pages': 0,
        'images': 0,
        'files': 0,
        'last_modified': None,
        'structure_valid': False
    }
    
    if not cache_dir.exists():
        return summary
    
    try:
        # Count structure elements
        notebooks_dir = cache_dir / "notebooks"
        if notebooks_dir.exists():
            summary['notebooks'] = len([d for d in notebooks_dir.iterdir() if d.is_dir()])
            
            for notebook_dir in notebooks_dir.iterdir():
                if not notebook_dir.is_dir():
                    continue
                    
                sections_dir = notebook_dir / "sections"
                if sections_dir.exists():
                    for section_dir in sections_dir.iterdir():
                        if not section_dir.is_dir():
                            continue
                        summary['sections'] += 1
                        
                        pages_dir = section_dir / "pages"
                        if pages_dir.exists():
                            for page_dir in pages_dir.iterdir():
                                if not page_dir.is_dir():
                                    continue
                                summary['pages'] += 1
                                
                                # Count assets
                                attachments_dir = page_dir / "attachments"
                                if attachments_dir.exists():
                                    images_dir = attachments_dir / "images"
                                    if images_dir.exists():
                                        summary['images'] += len([f for f in images_dir.iterdir() if f.is_file()])
                                    
                                    files_dir = attachments_dir / "files"
                                    if files_dir.exists():
                                        summary['files'] += len([f for f in files_dir.iterdir() if f.is_file()])
        
        # Overall file and directory counts
        for item in cache_dir.rglob("*"):
            if item.is_file():
                summary['total_files'] += 1
                summary['total_size_bytes'] += item.stat().st_size
                
                # Track most recent modification
                mtime = item.stat().st_mtime
                if summary['last_modified'] is None or mtime > summary['last_modified']:
                    summary['last_modified'] = mtime
                    
            elif item.is_dir():
                summary['total_directories'] += 1
        
        # Validate structure
        validation = validate_cache_structure(cache_dir)
        summary['structure_valid'] = validation.get('overall_valid', False)
        
    except Exception as e:
        logger.error(f"Failed to generate directory summary: {e}")
        summary['error'] = str(e)
    
    return summary


def get_content_path_for_page(cache_root: Path, notebook_name: str, section_name: str, page_title: str) -> Path:
    """
    Get the expected content path for a specific page.
    
    Args:
        cache_root: Root directory of the cache
        notebook_name: Name of the parent notebook
        section_name: Name of the parent section  
        page_title: Title of the page
        
    Returns:
        Path to the page's markdown file
    """
    safe_notebook = sanitize_filename(notebook_name)
    safe_section = sanitize_filename(section_name)
    safe_page = sanitize_filename(page_title)
    
    return cache_root / "content" / safe_notebook / safe_section / f"{safe_page}.md"


def get_content_path_for_section(cache_root: Path, notebook_name: str, section_name: str) -> Path:
    """
    Get the expected content path for a specific section.
    
    Args:
        cache_root: Root directory of the cache
        notebook_name: Name of the parent notebook
        section_name: Name of the section
        
    Returns:
        Path to the section's directory
    """
    safe_notebook = sanitize_filename(notebook_name)
    safe_section = sanitize_filename(section_name)
    
    return cache_root / "content" / safe_notebook / safe_section
