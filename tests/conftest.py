"""
Test configuration and fixtures for OneNote Copilot.

Provides shared fixtures, mock configurations, and testing utilities
for all test modules.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

# Test environment setup
os.environ["OPENAI_API_KEY"] = "test-api-key"
os.environ["AZURE_CLIENT_ID"] = "2d793eb5-32a9-4c85-8b9d-3b4c5c6be62e"


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_settings(temp_dir: Path):
    """Create mock settings for testing."""
    from src.config.settings import Settings

    return Settings(
        openai_api_key="test-openai-key",  # Will be converted to SecretStr
        azure_client_id="2d793eb5-32a9-4c85-8b9d-3b4c5c6be62e",
        cache_dir=temp_dir / "cache",
        config_dir=temp_dir / "config",
        token_cache_filename="msal_token_cache.json",  # Test expects no dot prefix
        debug_enabled=True,
        cli_color_enabled=False,
        cli_markdown_enabled=False,
        cli_welcome_enabled=False
    )


@pytest.fixture
def mock_onenote_search_response() -> Dict[str, Any]:
    """Mock OneNote search response."""
    return {
        "value": [
            {
                "id": "test-page-1",
                "title": "Test Page 1",
                "contentUrl": "https://graph.microsoft.com/v1.0/me/onenote/pages/test-page-1/content",
                "links": {
                    "oneNoteWebUrl": {
                        "href": "https://onedrive.live.com/edit.aspx?page_id=test-page-1"
                    }
                },
                "lastModifiedDateTime": "2024-01-15T10:30:00Z",
                "parentSection": {
                    "displayName": "Test Section"
                },
                "parentNotebook": {
                    "displayName": "Test Notebook"
                }
            },
            {
                "id": "test-page-2",
                "title": "Test Page 2",
                "contentUrl": "https://graph.microsoft.com/v1.0/me/onenote/pages/test-page-2/content",
                "links": {
                    "oneNoteWebUrl": {
                        "href": "https://onedrive.live.com/edit.aspx?page_id=test-page-2"
                    }
                },
                "lastModifiedDateTime": "2024-01-14T15:45:00Z",
                "parentSection": {
                    "displayName": "Another Section"
                },
                "parentNotebook": {
                    "displayName": "Test Notebook"
                }
            }
        ]
    }


@pytest.fixture
def mock_onenote_content() -> str:
    """Mock OneNote page content (HTML)."""
    return """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <div>
            <h1>Meeting Notes - Project Discussion</h1>
            <p>Today we discussed the new project timeline and deliverables.</p>
            <ul>
                <li>Phase 1: Research and planning - Due Feb 15</li>
                <li>Phase 2: Development - Due March 30</li>
                <li>Phase 3: Testing and deployment - Due April 15</li>
            </ul>
            <p>Next meeting scheduled for next Tuesday at 2 PM.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_notebooks_response() -> Dict[str, Any]:
    """Mock OneNote notebooks response."""
    return {
        "value": [
            {
                "id": "notebook-1",
                "displayName": "Work Notebook",
                "links": {
                    "oneNoteWebUrl": {
                        "href": "https://onedrive.live.com/edit.aspx?notebook_id=notebook-1"
                    }
                },
                "lastModifiedDateTime": "2024-01-15T10:30:00Z"
            },
            {
                "id": "notebook-2",
                "displayName": "Personal Notes",
                "links": {
                    "oneNoteWebUrl": {
                        "href": "https://onedrive.live.com/edit.aspx?notebook_id=notebook-2"
                    }
                },
                "lastModifiedDateTime": "2024-01-10T14:20:00Z"
            }
        ]
    }


@pytest.fixture
def mock_access_token() -> str:
    """Mock access token for testing."""
    return "mock-access-token-12345"


@pytest.fixture
def mock_authenticator(mock_access_token: str, mock_settings):
    """Mock Microsoft authenticator."""
    from src.auth.microsoft_auth import MicrosoftAuthenticator

    authenticator = MicrosoftAuthenticator(mock_settings)

    # Mock the async methods
    authenticator.get_access_token = AsyncMock(return_value=mock_access_token)
    authenticator.ensure_authenticated = AsyncMock(return_value=True)
    authenticator.is_authenticated = Mock(return_value=True)

    return authenticator


@pytest.fixture
def mock_search_tool(mock_settings, mock_authenticator):
    """Mock OneNote search tool."""
    from src.tools.onenote_search import OneNoteSearchTool

    tool = OneNoteSearchTool(mock_settings)
    tool.authenticator = mock_authenticator

    return tool


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI streaming response."""
    class MockStreamChunk:
        def __init__(self, content: str):
            self.choices = [
                Mock(delta=Mock(content=content))
            ]

    async def mock_stream():
        chunks = [
            "Based on your OneNote content, ",
            "I found information about ",
            "project planning and timelines."
        ]
        for chunk in chunks:
            yield MockStreamChunk(chunk)

    return mock_stream()


@pytest.fixture
def mock_console():
    """Mock Rich console for CLI testing."""
    console = Mock()
    console.print = Mock()
    console.status = Mock()
    return console


@pytest.fixture
def mock_cli_formatter(mock_console):
    """Mock CLI formatter."""
    from src.cli.formatting import CLIFormatter

    formatter = CLIFormatter(
        console=mock_console,
        enable_color=False,
        enable_markdown=False
    )

    # Mock all formatting methods to return simple strings
    formatter.format_welcome_message = Mock(return_value="Welcome!")
    formatter.format_search_response = Mock(return_value="Search response")
    formatter.format_error = Mock(return_value="Error message")
    formatter.format_help = Mock(return_value="Help message")

    return formatter


# Test data generators
def create_test_page(page_id: str, title: str, content: str = "") -> Dict[str, Any]:
    """Create a test OneNote page object."""
    return {
        "id": page_id,
        "title": title,
        "contentUrl": f"https://graph.microsoft.com/v1.0/me/onenote/pages/{page_id}/content",
        "links": {
            "oneNoteWebUrl": {
                "href": f"https://onedrive.live.com/edit.aspx?page_id={page_id}"
            }
        },
        "lastModifiedDateTime": "2024-01-15T10:30:00Z",
        "parentSection": {
            "displayName": "Test Section"
        },
        "parentNotebook": {
            "displayName": "Test Notebook"
        }
    }


def create_test_notebook(notebook_id: str, name: str) -> Dict[str, Any]:
    """Create a test OneNote notebook object."""
    return {
        "id": notebook_id,
        "displayName": name,
        "links": {
            "oneNoteWebUrl": {
                "href": f"https://onedrive.live.com/edit.aspx?notebook_id={notebook_id}"
            }
        },
        "lastModifiedDateTime": "2024-01-15T10:30:00Z"
    }


# Context managers for testing
@pytest.fixture
def mock_graph_api():
    """Mock Microsoft Graph API responses."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock()
        mock_response.text = AsyncMock()

        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value.get = AsyncMock(return_value=mock_response)

        yield mock_client, mock_response


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_stream = AsyncMock()
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_stream)
        yield mock_client


# Markers for test organization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.cli = pytest.mark.cli
pytest.mark.slow = pytest.mark.slow


# Test optimization fixtures
@pytest.fixture
def mock_network_delays():
    """Mock sleep functions to eliminate network timeouts in tests."""
    with patch('time.sleep') as mock_sleep, \
         patch('asyncio.sleep') as mock_async_sleep:
        mock_sleep.return_value = None
        mock_async_sleep.return_value = None
        yield mock_sleep, mock_async_sleep


@pytest.fixture
def fast_embedding_response():
    """Pre-computed embedding response for fast tests."""
    return [0.1, 0.2, 0.3, 0.4, 0.5] * 256  # 1280 dimensions


@pytest.fixture
def mock_chromadb_client():
    """Mock ChromaDB client for vector storage tests."""
    mock_client = Mock()
    mock_collection = Mock()
    mock_collection.add.return_value = None
    mock_collection.query.return_value = {
        'ids': [['doc1', 'doc2']],
        'documents': [['Mock document 1', 'Mock document 2']],
        'metadatas': [[{'source': 'test1'}, {'source': 'test2'}]],
        'distances': [[0.1, 0.2]]
    }
    mock_collection.count.return_value = 2
    mock_client.get_collection.return_value = mock_collection
    mock_client.create_collection.return_value = mock_collection
    return mock_client


@pytest.fixture
def mock_http_response():
    """Mock HTTP response for network-based tests."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'value': [
            {
                'id': 'page1',
                'title': 'Mock Page 1',
                'content': 'Mock content 1'
            },
            {
                'id': 'page2',
                'title': 'Mock Page 2',
                'content': 'Mock content 2'
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    return mock_response


@pytest.fixture
def mock_requests_session():
    """Mock requests session for HTTP tests."""
    mock_session = Mock()
    mock_session.get.return_value = mock_http_response()
    mock_session.post.return_value = mock_http_response()
    return mock_session


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for async HTTP tests."""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        'value': [
            {
                'id': 'page1',
                'title': 'Mock Page 1',
                'content': 'Mock content 1'
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aenter__.return_value = mock_response
    return mock_session


@pytest.fixture(scope="function", autouse=True)
def test_cleanup():
    """Automatic cleanup between tests."""
    # Setup - before each test
    yield
    # Cleanup - after each test
    # Clear any global state that might have been set
    if hasattr(asyncio, '_current_task'):
        asyncio._current_task = None


# Fast test markers for categorization
pytest.mark.fast = pytest.mark.fast
pytest.mark.network = pytest.mark.network


# Phase 2: Advanced optimization fixtures with session and module scoping
@pytest.fixture(scope="session")
def session_auth_setup():
    """One-time authentication setup for entire test session."""
    # Mock expensive authentication operations that can be shared across tests
    mock_auth_data = {
        "access_token": "test-session-token",
        "refresh_token": "test-refresh-token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://graph.microsoft.com/.default"
    }
    return mock_auth_data


@pytest.fixture(scope="session")
def session_openai_embeddings():
    """Pre-computed embeddings for session-wide use."""
    # Create a variety of embeddings for different test scenarios
    embeddings = {
        "test_content": [0.1, 0.2, 0.3, 0.4, 0.5] * 256,  # 1280 dimensions
        "meeting_notes": [0.2, 0.3, 0.4, 0.5, 0.6] * 256,
        "project_ideas": [0.3, 0.4, 0.5, 0.6, 0.7] * 256,
        "technical_docs": [0.4, 0.5, 0.6, 0.7, 0.8] * 256,
        "personal_notes": [0.5, 0.6, 0.7, 0.8, 0.9] * 256,
    }
    return embeddings


@pytest.fixture(scope="session")
def session_vector_store():
    """Mock vector store for session-wide use."""
    mock_store = Mock()
    mock_store.add_documents.return_value = None
    mock_store.similarity_search.return_value = [
        {"id": "doc1", "content": "Mock document 1", "metadata": {"source": "test1"}},
        {"id": "doc2", "content": "Mock document 2", "metadata": {"source": "test2"}}
    ]
    mock_store.count.return_value = 100
    return mock_store


@pytest.fixture(scope="module")
def module_settings():
    """Module-scoped settings for related tests."""
    from src.config.settings import Settings

    # Create settings once per module
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        yield Settings(
            openai_api_key="test-module-key",
            azure_client_id="2d793eb5-32a9-4c85-8b9d-3b4c5c6be62e",
            cache_dir=temp_path / "cache",
            config_dir=temp_path / "config",
            token_cache_filename="msal_token_cache.json",
            debug_enabled=True,
            cli_color_enabled=False,
            cli_markdown_enabled=False,
            cli_welcome_enabled=False
        )


@pytest.fixture(scope="module")
def module_mock_chromadb():
    """Module-scoped ChromaDB mock for vector storage tests."""
    mock_client = Mock()
    mock_collection = Mock()

    # Pre-computed collection data
    mock_collection.add.return_value = None
    mock_collection.query.return_value = {
        'ids': [['doc1', 'doc2', 'doc3']],
        'documents': [['Mock document 1', 'Mock document 2', 'Mock document 3']],
        'metadatas': [[
            {'source': 'test1', 'type': 'note'},
            {'source': 'test2', 'type': 'meeting'},
            {'source': 'test3', 'type': 'idea'}
        ]],
        'distances': [[0.1, 0.2, 0.3]]
    }
    mock_collection.count.return_value = 3

    mock_client.get_collection.return_value = mock_collection
    mock_client.create_collection.return_value = mock_collection
    mock_client.list_collections.return_value = [mock_collection]

    return mock_client


@pytest.fixture(scope="module")
def module_mock_onenote_data():
    """Module-scoped OneNote data for search tests."""
    return {
        "notebooks": [
            {
                "id": "notebook1",
                "displayName": "Work Notebook",
                "sections": [
                    {
                        "id": "section1",
                        "displayName": "Meeting Notes",
                        "pages": [
                            {
                                "id": "page1",
                                "title": "Team Meeting - Jan 15",
                                "content": "Discussed project roadmap and sprint goals.",
                                "lastModifiedDateTime": "2025-01-15T10:30:00Z"
                            },
                            {
                                "id": "page2",
                                "title": "Client Call - Jan 16",
                                "content": "Requirements gathering for new feature.",
                                "lastModifiedDateTime": "2025-01-16T14:20:00Z"
                            }
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture(scope="function", autouse=True)
def optimized_test_cleanup():
    """Optimized automatic cleanup between tests."""
    # Minimal setup - before each test
    yield

    # Efficient cleanup - after each test
    # Only clean what's absolutely necessary
    if hasattr(asyncio, '_current_task'):
        asyncio._current_task = None

    # Clear any cached modules if needed
    import gc
    gc.collect()  # Force garbage collection for cleaner test isolation


# Advanced test categorization fixtures
@pytest.fixture
def performance_monitor():
    """Monitor test performance and log slow operations."""
    import time

    start_time = time.time()
    yield
    end_time = time.time()

    execution_time = end_time - start_time
    if execution_time > 1.0:  # Log tests that take more than 1 second
        import logging
        logging.warning(f"Slow test detected: {execution_time:.2f}s")


@pytest.fixture
def memory_monitor():
    """Monitor memory usage during tests."""
    import os

    import psutil

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    yield

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_diff = final_memory - initial_memory

    if memory_diff > 50:  # Log tests that use more than 50MB
        import logging
        logging.warning(f"High memory usage test: {memory_diff:.2f}MB")


# Import optimization fixtures
@pytest.fixture
def lazy_imports():
    """Provide lazy imports for heavy modules."""
    import importlib

    def lazy_import(module_name):
        return importlib.import_module(module_name)

    return lazy_import


@pytest.fixture
def mock_heavy_imports():
    """Mock heavy imports to speed up test startup."""
    with patch('chromadb.Client') as mock_chroma, \
         patch('openai.AsyncOpenAI') as mock_openai, \
         patch('langchain.embeddings.OpenAIEmbeddings') as mock_embeddings:

        # Configure mocks with minimal setup
        mock_chroma.return_value = Mock()
        mock_openai.return_value = Mock()
        mock_embeddings.return_value = Mock()

        yield {
            'chromadb': mock_chroma,
            'openai': mock_openai,
            'embeddings': mock_embeddings
        }
