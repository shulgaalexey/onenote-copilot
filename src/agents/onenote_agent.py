"""
OneNote LangGraph agent for natural language search and interaction.

Implements a stateful LangGraph agent that can search OneNote content,
provide intelligent responses, and stream results in real-time.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage)
# Lazy import: from langchain_openai import ChatOpenAI
# Lazy import: from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from ..auth.microsoft_auth import AuthenticationError, MicrosoftAuthenticator
from ..config.logging import log_api_call, log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import OneNotePage, SearchResult
from ..models.responses import (AgentState, OneNoteSearchResponse,
                                StreamingChunk)
from ..storage.cache_manager import OneNoteCacheManager
from ..storage.local_search import LocalOneNoteSearch, LocalSearchError
from ..tools.onenote_content import (OneNoteContentProcessor,
                                     create_ai_context_from_pages)
from ..tools.onenote_search import OneNoteSearchError, OneNoteSearchTool
from .prompts import (RESPONSE_TEMPLATES, get_answer_generation_prompt,
                      get_no_results_prompt, get_system_prompt)

logger = logging.getLogger(__name__)


class MessagesState(TypedDict):
    """State for the OneNote agent conversation."""
    messages: List[BaseMessage]


class OneNoteAgent:
    """
    LangGraph-based agent for OneNote natural language search.

    Provides intelligent search capabilities with streaming responses,
    source attribution, and comprehensive error handling.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the OneNote agent.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Initialize components
        self.authenticator = MicrosoftAuthenticator(self.settings)
        self.search_tool = OneNoteSearchTool(self.authenticator, self.settings)
        self.content_processor = OneNoteContentProcessor()

        # Initialize cache and local search (lazy loaded)
        self._cache_manager = None
        self._local_search = None
        self._local_search_available = False

        # Initialize semantic search components
        self._semantic_search_engine = None
        self._semantic_search_enabled = self.settings.enable_hybrid_search

        # Initialize LLM (will be lazy loaded)
        self._llm = None

        # Create LangGraph workflow (will be lazy loaded)
        self._graph = None

        # Agent state
        self.current_state: Optional[AgentState] = None

    @property
    def llm(self):
        """Lazy initialization of ChatOpenAI LLM."""
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                temperature=self.settings.openai_temperature,
                streaming=True
            )
            logger.info("LLM initialized")
        return self._llm

    @property
    def graph(self):
        """Lazy initialization of LangGraph workflow."""
        if self._graph is None:
            self._graph = self._create_agent_graph()
            logger.info("Agent graph initialized")
        return self._graph

    @property
    def semantic_search_engine(self):
        """Lazy initialization of semantic search engine."""
        if self._semantic_search_engine is None and self._semantic_search_enabled:
            try:
                from ..search.semantic_search import SemanticSearchEngine
                self._semantic_search_engine = SemanticSearchEngine(
                    search_tool=self.search_tool,
                    settings=self.settings
                )
                logger.info("Semantic search engine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize semantic search: {e}")
                self._semantic_search_enabled = False
        return self._semantic_search_engine

    @property
    def cache_manager(self):
        """Lazy initialization of cache manager."""
        if self._cache_manager is None:
            self._cache_manager = OneNoteCacheManager(self.settings)
            logger.debug("Cache manager initialized")
        return self._cache_manager

    @property
    def local_search(self):
        """Lazy initialization of local search engine."""
        if self._local_search is None and not self._local_search_available:
            try:
                self._local_search = LocalOneNoteSearch(self.settings, self.cache_manager)
                # Don't initialize yet - will be done in initialize() method
                logger.debug("Local search engine created")
            except Exception as e:
                logger.warning(f"Failed to create local search engine: {e}")
        return self._local_search

    async def _check_local_search_available(self) -> bool:
        """Check if local search is available and has content."""
        try:
            if not self.local_search:
                return False

            # Check if cache directory exists and has content
            cache_root = self.cache_manager.cache_root
            if not cache_root.exists():
                logger.debug("Cache directory doesn't exist - local search unavailable")
                return False

            # Check if there are any cached pages
            cached_pages = await self.cache_manager.get_all_cached_pages()
            if not cached_pages:
                logger.debug("No cached pages found - local search unavailable")
                return False

            logger.info(f"Local search available with {len(cached_pages)} cached pages")
            return True

        except Exception as e:
            logger.warning(f"Error checking local search availability: {e}")
            return False

    def _create_agent_graph(self) -> Any:
        """Create the LangGraph workflow for the agent."""
        from langgraph.graph import StateGraph

        workflow = StateGraph(MessagesState)

        # Add nodes
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("search_onenote", self._search_onenote_node)
        workflow.add_node("semantic_search", self._semantic_search_node)
        workflow.add_node("get_recent_pages", self._get_recent_pages_node)
        workflow.add_node("get_notebooks", self._get_notebooks_node)

        # Add conditional edges for tool routing
        workflow.add_conditional_edges(
            "agent",
            self._should_use_tools,
            {
                "search_onenote": "search_onenote",
                "semantic_search": "semantic_search",
                "get_recent_pages": "get_recent_pages",
                "get_notebooks": "get_notebooks",
                "end": "__end__"
            }
        )

        # Add edges back to agent after tool execution
        workflow.add_edge("search_onenote", "agent")
        workflow.add_edge("semantic_search", "agent")
        workflow.add_edge("get_recent_pages", "agent")
        workflow.add_edge("get_notebooks", "agent")

        # Set entry point
        workflow.set_entry_point("agent")

        return workflow.compile()

    async def _agent_node(self, state: MessagesState) -> MessagesState:
        """
        Main agent node that processes messages and generates responses.

        Args:
            state: Current conversation state

        Returns:
            Updated state with agent response
        """
        try:
            messages = state["messages"]

            # Add system prompt if not present
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                system_msg = SystemMessage(content=get_system_prompt())
                messages = [system_msg] + messages

            # Check if we have tool results to process into a final response
            tool_results = [
                msg for msg in messages
                if isinstance(msg, AIMessage) and isinstance(msg.content, str) and
                any(prefix in msg.content for prefix in ["SEARCH_RESULTS:", "RECENT_PAGES:", "NOTEBOOKS:", "NO_RESULTS:", "SEARCH_ERROR:"])
            ]

            if tool_results:
                # We have tool results, generate final response based on them
                latest_tool_result = tool_results[-1]
                original_query = None

                # Find the original human query
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        original_query = msg.content
                        break

                if latest_tool_result.content.startswith("SEARCH_RESULTS:"):
                    # Generate response based on search results
                    context = latest_tool_result.content.replace("SEARCH_RESULTS:\n", "")
                    prompt = get_answer_generation_prompt(original_query or "user query", context)
                    response_messages = [
                        SystemMessage(content=get_system_prompt()),
                        HumanMessage(content=prompt)
                    ]
                elif latest_tool_result.content.startswith("NO_RESULTS:"):
                    # Generate response for no results
                    prompt = get_no_results_prompt(original_query or "user query")
                    response_messages = [
                        SystemMessage(content=get_system_prompt()),
                        HumanMessage(content=prompt)
                    ]
                elif latest_tool_result.content.startswith("RECENT_PAGES:"):
                    # Format recent pages response
                    pages_content = latest_tool_result.content.replace("RECENT_PAGES:\n", "")
                    prompt = f"Based on these recent OneNote pages, provide a helpful summary for the user:\n\n{pages_content}"
                    response_messages = [
                        SystemMessage(content=get_system_prompt()),
                        HumanMessage(content=prompt)
                    ]
                elif latest_tool_result.content.startswith("NOTEBOOKS:"):
                    # Format notebooks response
                    notebooks_content = latest_tool_result.content.replace("NOTEBOOKS:\n", "")
                    prompt = f"Present this OneNote notebooks information in a helpful way:\n\n{notebooks_content}"
                    response_messages = [
                        SystemMessage(content=get_system_prompt()),
                        HumanMessage(content=prompt)
                    ]
                else:
                    # Error case
                    error_content = latest_tool_result.content
                    response = AIMessage(content=f"I encountered an issue: {error_content}")
                    return {"messages": messages + [response]}

                # Get final response from LLM
                response = await self.llm.ainvoke(response_messages)
                return {"messages": messages + [response]}

            # No tool results yet, check if we need to call tools
            last_message = messages[-1]
            if isinstance(last_message, HumanMessage):
                # Initial user query - determine if we need tools
                user_query = last_message.content

                if self._needs_tool_call(user_query):
                    # Extract tool information and add to state
                    tool_info = self._extract_tool_info(user_query)
                    response = AIMessage(content=json.dumps(tool_info))
                    return {"messages": messages + [response]}
                else:
                    # Direct response without tools
                    response = await self.llm.ainvoke(messages)
                    return {"messages": messages + [response]}

            # Default case - get response from LLM
            response = await self.llm.ainvoke(messages)
            return {"messages": messages + [response]}

        except Exception as e:
            logger.error(f"Agent node error: {e}")
            error_msg = AIMessage(content=f"I encountered an error: {e}")
            return {"messages": messages + [error_msg]}

    async def _search_onenote_node(self, state: MessagesState) -> MessagesState:
        """
        Search OneNote pages tool node.

        Args:
            state: Current conversation state

        Returns:
            Updated state with search results
        """
        try:
            messages = state["messages"]
            last_message = messages[-1]

            # Extract search parameters
            if isinstance(last_message.content, str):
                tool_info = json.loads(last_message.content)
            else:
                tool_info = {"query": str(last_message.content), "max_results": 10}

            query = tool_info.get("query", "")
            max_results = tool_info.get("max_results", 10)

            logger.info(f"Searching OneNote for: '{query}'")

            # Perform search
            search_result = await self.search_tool.search_pages(query, max_results)

            # Format results for LLM
            if search_result.pages:
                formatted_context = self.content_processor.format_search_results_for_ai(search_result)
                prompt = get_answer_generation_prompt(query, formatted_context)

                tool_response = AIMessage(content=f"SEARCH_RESULTS:\n{formatted_context}")
            else:
                prompt = get_no_results_prompt(query)
                tool_response = AIMessage(content=f"NO_RESULTS: No pages found for query '{query}'")

            return {"messages": messages + [tool_response]}

        except OneNoteSearchError as e:
            logger.error(f"OneNote search error: {e}")
            error_msg = AIMessage(content=f"SEARCH_ERROR: {e}")
            return {"messages": messages + [error_msg]}
        except Exception as e:
            logger.error(f"Search node error: {e}")
            error_msg = AIMessage(content=f"SEARCH_ERROR: Unexpected error during search: {e}")
            return {"messages": messages + [error_msg]}

    async def _semantic_search_node(self, state: MessagesState) -> MessagesState:
        """
        Semantic search OneNote tool node using vector embeddings.

        Args:
            state: Current conversation state

        Returns:
            Updated state with semantic search results
        """
        try:
            messages = state["messages"]
            last_message = messages[-1]

            # Extract tool information from the last message
            if isinstance(last_message.content, str):
                tool_info = json.loads(last_message.content)
            else:
                tool_info = {"query": str(last_message.content), "limit": 10}

            query = tool_info.get("query", "")
            limit = tool_info.get("limit", self.settings.semantic_search_limit)

            logger.info(f"Performing semantic search for: '{query}'")

            # Check if semantic search is available
            if not self._semantic_search_enabled or not self.semantic_search_engine:
                logger.warning("Semantic search not available, falling back to keyword search")
                # Delegate to regular search
                return await self._search_onenote_node(state)

            # Perform semantic search with fallback
            search_results = await self.semantic_search_engine.search_with_fallback(
                query=query,
                limit=limit,
                prefer_semantic=True
            )

            # Format results for LLM
            if search_results:
                # Convert semantic results to pages for formatting
                pages = []
                for result in search_results:
                    if result.page:
                        pages.append(result.page)
                    else:
                        # Create a pseudo-page from chunk data
                        from ..models.onenote import OneNotePage
                        pseudo_page = OneNotePage(
                            id=result.chunk.page_id,
                            title=result.chunk.page_title,
                            content=result.chunk.content,
                            content_url=None,
                            created_date_time=None,
                            last_modified_date_time=None
                        )
                        pages.append(pseudo_page)

                # Create a search result object for formatting
                from ..models.onenote import SearchResult
                formatted_search_result = SearchResult(
                    query=query,
                    pages=pages[:limit],
                    total_count=len(pages)
                )

                formatted_context = self.content_processor.format_search_results_for_ai(formatted_search_result)

                # Add semantic search information
                search_type_info = [result.search_type for result in search_results[:3]]
                context_with_info = f"[Semantic Search Results - Types: {', '.join(set(search_type_info))}]\n\n{formatted_context}"

                tool_response = AIMessage(content=f"SEARCH_RESULTS:\n{context_with_info}")
            else:
                # No semantic results found, try keyword search as fallback
                logger.info("No semantic results found, attempting keyword search fallback")

                try:
                    # Fallback to regular keyword search
                    search_result = await self.search_tool.search_pages(query, limit)

                    if search_result.pages:
                        formatted_context = self.content_processor.format_search_results_for_ai(search_result)
                        context_with_info = f"[Keyword Search Results - Semantic search found no matches]\n\n{formatted_context}"
                        tool_response = AIMessage(content=f"SEARCH_RESULTS:\n{context_with_info}")
                    else:
                        tool_response = AIMessage(content=f"NO_RESULTS: No pages found for query '{query}' using semantic or keyword search")
                except Exception as e:
                    logger.error(f"Keyword search fallback failed: {e}")
                    tool_response = AIMessage(content=f"NO_RESULTS: No pages found for query '{query}'")

            return {"messages": messages + [tool_response]}

        except Exception as e:
            logger.error(f"Semantic search node error: {e}")
            # Fallback to regular search on error
            try:
                logger.info("Semantic search failed, falling back to keyword search")
                return await self._search_onenote_node(state)
            except Exception as fallback_error:
                logger.error(f"Keyword search fallback also failed: {fallback_error}")
                error_msg = AIMessage(content=f"SEARCH_ERROR: Both semantic and keyword search failed: {e}")
                return {"messages": messages + [error_msg]}

    async def _get_recent_pages_node(self, state: MessagesState) -> MessagesState:
        """
        Get recent OneNote pages tool node.

        Args:
            state: Current conversation state

        Returns:
            Updated state with recent pages
        """
        try:
            messages = state["messages"]
            last_message = messages[-1]

            # Extract parameters
            if isinstance(last_message.content, str):
                tool_info = json.loads(last_message.content)
            else:
                tool_info = {"limit": 10}

            limit = tool_info.get("limit", 10)

            logger.info(f"Getting {limit} recent OneNote pages")

            # Get recent pages
            recent_pages = await self.search_tool.get_recent_pages(limit)

            # Format for display
            if recent_pages:
                pages_info = []
                for i, page in enumerate(recent_pages, 1):
                    date_str = page.last_modified_date_time.strftime("%Y-%m-%d %H:%M")
                    pages_info.append(
                        f"{i}. **{page.title}** ({page.get_notebook_name()} > {page.get_section_name()}) - {date_str}"
                    )

                response_content = f"RECENT_PAGES:\nHere are your {len(recent_pages)} most recently modified OneNote pages:\n\n" + "\n".join(pages_info)
            else:
                response_content = "RECENT_PAGES:\nNo recent pages found."

            tool_response = AIMessage(content=response_content)
            return {"messages": messages + [tool_response]}

        except Exception as e:
            logger.error(f"Recent pages node error: {e}")
            error_msg = AIMessage(content=f"RECENT_PAGES_ERROR: {e}")
            return {"messages": messages + [error_msg]}

    async def _get_notebooks_node(self, state: MessagesState) -> MessagesState:
        """
        Get OneNote notebooks tool node.

        Args:
            state: Current conversation state

        Returns:
            Updated state with notebook list
        """
        try:
            messages = state["messages"]

            logger.info("Getting OneNote notebooks list")

            # Get notebooks
            notebooks = await self.search_tool.get_notebooks()

            # Format for display
            if notebooks:
                notebook_info = []
                for i, notebook in enumerate(notebooks, 1):
                    name = notebook.get("displayName", "Unnamed Notebook")
                    created = notebook.get("createdDateTime", "")
                    if created:
                        created = created[:10]  # Just the date part
                        notebook_info.append(f"{i}. **{name}** (Created: {created})")
                    else:
                        notebook_info.append(f"{i}. **{name}**")

                response_content = f"NOTEBOOKS:\nHere are your OneNote notebooks:\n\n" + "\n".join(notebook_info)
            else:
                response_content = "NOTEBOOKS:\nNo notebooks found."

            tool_response = AIMessage(content=response_content)
            return {"messages": messages + [tool_response]}

        except Exception as e:
            logger.error(f"Notebooks node error: {e}")
            error_msg = AIMessage(content=f"NOTEBOOKS_ERROR: {e}")
            return {"messages": messages + [error_msg]}

    def _should_use_tools(self, state: MessagesState) -> str:
        """
        Determine if tools should be used based on the last message.

        Args:
            state: Current conversation state

        Returns:
            Next node to execute
        """
        messages = state["messages"]
        last_message = messages[-1]

        # Check if we already have tool results in the conversation
        # If we do, and the last message is from AI, we should end
        tool_results_present = any(
            isinstance(msg, AIMessage) and isinstance(msg.content, str) and
            any(prefix in msg.content for prefix in ["SEARCH_RESULTS:", "RECENT_PAGES:", "NOTEBOOKS:", "NO_RESULTS:", "SEARCH_ERROR:"])
            for msg in messages
        )

        if isinstance(last_message, AIMessage) and isinstance(last_message.content, str):
            # If we have tool results and this is a regular AI response, end the conversation
            if tool_results_present and not last_message.content.startswith("{"):
                return "end"

            try:
                # Check if the message contains tool information
                if last_message.content.startswith("{") and "tool" in last_message.content:
                    tool_info = json.loads(last_message.content)
                    tool_name = tool_info.get("tool", "")

                    # Only execute tools if we haven't already executed them
                    if not tool_results_present:
                        if tool_name == "search_onenote":
                            return "search_onenote"
                        elif tool_name == "semantic_search":
                            return "semantic_search"
                        elif tool_name == "get_recent_pages":
                            return "get_recent_pages"
                        elif tool_name == "get_notebooks":
                            return "get_notebooks"
            except (json.JSONDecodeError, KeyError):
                pass

        return "end"

    def _needs_tool_call(self, content: str) -> bool:
        """
        Check if the LLM response indicates a tool call is needed.

        Args:
            content: LLM response content

        Returns:
            True if tool call is needed
        """
        # Simple heuristics to detect when tools should be used
        lower_content = content.lower()

        search_indicators = [
            "search", "find", "look for", "show me", "what did i write",
            "notes about", "pages about", "content about", "thoughts about",
            "what were my thoughts", "my thoughts on", "what did i think",
            "what was my", "thoughts on", "ideas about", "how did i",
            "what did i", "tell me about", "describe",
            "what about", "information about", "details about", "data about",
            "anything about", "stuff about", "material about", "content on",
            "organise", "organize", "prepare", "preparation", "plan", "planning",
            "approach", "method", "strategy", "process", "procedure", "steps"
        ]

        recent_indicators = [
            "recent", "lately", "recently", "last week", "yesterday",
            "latest", "most recent"
        ]

        notebook_indicators = [
            "notebook", "notebooks", "list notebook", "show notebook",
            "what notebooks"
        ]

        if any(indicator in lower_content for indicator in search_indicators):
            return True
        elif any(indicator in lower_content for indicator in recent_indicators):
            return True
        elif any(indicator in lower_content for indicator in notebook_indicators):
            return True

        return False

    def _extract_tool_info(self, content: str) -> Dict[str, Any]:
        """
        Extract tool information from LLM response.

        Args:
            content: LLM response content

        Returns:
            Tool information dictionary
        """
        lower_content = content.lower()

        # Determine tool type
        if any(word in lower_content for word in ["recent", "lately", "recently", "latest"]):
            return {"tool": "get_recent_pages", "limit": 10}
        elif any(word in lower_content for word in ["notebook", "notebooks"]):
            return {"tool": "get_notebooks"}
        else:
            # Determine if semantic search should be used
            # Use semantic search for conceptual queries
            semantic_indicators = [
                "think about", "thought about", "ideas about", "opinion on", "feels about",
                "vibe", "concept", "philosophy", "approach", "strategy", "methodology",
                "what did i", "tell me about", "my thoughts on", "my ideas on",
                "how did i", "how i", "organise", "organize", "prepare", "preparation",
                "plan", "planning", "process", "procedure", "method", "steps",
                "interview", "interviews", "meeting", "meetings", "work"
            ]

            use_semantic = (
                self._semantic_search_enabled and
                any(indicator in lower_content for indicator in semantic_indicators)
            )

            # Extract potential search query from content
            query = content

            # Clean up the query
            for phrase in ["search for", "find", "show me", "look for"]:
                query = query.replace(phrase, "")

            query = query.strip()

            # Choose tool based on query characteristics
            tool_name = "semantic_search" if use_semantic else "search_onenote"
            limit_key = "limit" if use_semantic else "max_results"

            return {
                "tool": tool_name,
                "query": query,
                limit_key: 10
            }

    async def process_query(self, query: str) -> AsyncGenerator[StreamingChunk, None]:
        """
        Process a user query and stream the response.

        Args:
            query: User query string

        Yields:
            StreamingChunk objects with response data
        """
        try:
            # Initialize state
            initial_state = {"messages": [HumanMessage(content=query)]}

            # Yield status update for AI component loading (only on first access)
            if self._graph is None:
                yield StreamingChunk.status_chunk("🤖 Loading AI components...")

            # Yield status update
            yield StreamingChunk.status_chunk("🔍 Processing your query...")

            # Track execution state
            tool_executed = False
            final_response_found = False
            user_query_needs_tools = self._needs_tool_call(query)

            # Process through the graph
            async for event in self.graph.astream(initial_state):
                logger.debug(f"Processing event: {list(event.keys())}")

                # Handle agent node events
                if "agent" in event:
                    node_output = event["agent"]
                    if "messages" in node_output:
                        messages = node_output["messages"]
                        if messages:
                            last_message = messages[-1]
                            if isinstance(last_message, AIMessage) and isinstance(last_message.content, str):

                                # Check if this is a tool call instruction
                                if last_message.content.startswith("{") and "tool" in last_message.content:
                                    # Tool call instruction - update status
                                    yield StreamingChunk.status_chunk("Searching OneNote...")

                                # Check if this is a final response after tool execution
                                elif tool_executed and not any(prefix in last_message.content for prefix in
                                       ["SEARCH_RESULTS:", "RECENT_PAGES:", "NOTEBOOKS:", "NO_RESULTS:", "SEARCH_ERROR:"]):
                                    # This is the final user-facing response after tool execution
                                    logger.debug("Final response found after tool execution")
                                    yield StreamingChunk.text_chunk(last_message.content, is_final=True)
                                    final_response_found = True
                                    break  # Exit the event loop

                                # Check if this is a direct response (no tools needed)
                                elif not tool_executed and not user_query_needs_tools and not last_message.content.startswith("{"):
                                    # Direct response without tools
                                    logger.debug("Direct response without tools")
                                    yield StreamingChunk.text_chunk(last_message.content, is_final=True)
                                    final_response_found = True
                                    break  # Exit the event loop

                # Handle tool execution events
                elif any(tool in event for tool in ["search_onenote", "get_recent_pages", "get_notebooks", "semantic_search"]):
                    # Tool execution
                    yield StreamingChunk.status_chunk("Processing results...")
                    tool_executed = True
                    logger.debug("Tool execution completed")

            # Safety check: if no final response was yielded, try to extract one
            if not final_response_found:
                logger.warning("No final response yielded during normal processing, attempting fallback")
                yield StreamingChunk.error_chunk("I'm having trouble generating a response. Please try again.")

        except AuthenticationError:
            yield StreamingChunk.error_chunk(RESPONSE_TEMPLATES["authentication_required"])
        except OneNoteSearchError as e:
            yield StreamingChunk.error_chunk(RESPONSE_TEMPLATES["search_error"].format(error=str(e)))
        except Exception as e:
            logger.error(f"Query processing error: {e}")
            yield StreamingChunk.error_chunk(f"An unexpected error occurred: {e}")

    async def search_pages(self, query: str, max_results: int = 10) -> OneNoteSearchResponse:
        """
        Direct search method for OneNote pages with local search support.

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            OneNoteSearchResponse with results
        """
        start_time = time.time()
        search_method = "unknown"

        try:
            # Try local search first if available
            if self._local_search_available and self.local_search:
                try:
                    local_results = await self.local_search.search(query, limit=max_results)
                    if local_results:
                        search_method = "local_cache"
                        logger.info(f"Local search found {len(local_results)} results in {time.time() - start_time:.2f}s")
                        return await self._create_response_from_local_results(local_results, query, start_time, search_method)
                    else:
                        logger.info("Local search returned no results, falling back to API")

                except LocalSearchError as e:
                    logger.warning(f"Local search error, falling back to API: {e}")
                except Exception as e:
                    logger.warning(f"Unexpected local search error, falling back to API: {e}")

            # Fallback to API search
            search_method = "api"
            logger.info(f"Using API search for query: '{query}'")
            return await self._api_search_pages(query, max_results, start_time, search_method)

        except Exception as e:
            logger.error(f"Search error: {e}")
            return OneNoteSearchResponse(
                answer=f"I encountered an error while searching: {e}",
                sources=[],
                confidence=0.0,
                search_query_used=query,
                metadata={"error": str(e), "search_method": search_method}
            )

    async def _create_response_from_local_results(
        self,
        local_results: list,
        query: str,
        start_time: float,
        search_method: str
    ) -> OneNoteSearchResponse:
        """Create OneNoteSearchResponse from local search results."""
        try:
            # Convert local search results to pages
            pages = [result.page for result in local_results]

            # Create formatted context for AI
            search_result = SearchResult(
                query=query,  # Fix: Add the required query field
                pages=pages,
                total_count=len(pages),
                execution_time=time.time() - start_time,
                api_calls_made=0  # No API calls for local search
            )

            formatted_context = self.content_processor.format_search_results_for_ai(search_result)

            # Generate AI answer
            messages = [
                SystemMessage(content=get_system_prompt()),
                HumanMessage(content=get_answer_generation_prompt(query, formatted_context))
            ]

            response = await self.llm.ainvoke(messages)
            answer = response.content

            # Calculate confidence based on results
            confidence = min(0.9, 0.3 + (len(pages) * 0.1))

            return OneNoteSearchResponse(
                answer=answer,
                sources=pages,
                confidence=confidence,
                search_query_used=query,
                metadata={
                    "execution_time": time.time() - start_time,
                    "api_calls": 0,
                    "total_results": len(pages),
                    "search_method": search_method,
                    "local_search_results": len(local_results)
                }
            )

        except Exception as e:
            logger.error(f"Error creating response from local results: {e}")
            # Fallback to API search if local result processing fails
            return await self._api_search_pages(query, 10, start_time, "api_fallback")

    async def _api_search_pages(
        self,
        query: str,
        max_results: int,
        start_time: float,
        search_method: str
    ) -> OneNoteSearchResponse:
        """Perform API-based search (original implementation)."""
        try:
            # Perform search
            search_result = await self.search_tool.search_pages(query, max_results)

            if search_result.pages:
                # Generate AI answer
                formatted_context = self.content_processor.format_search_results_for_ai(search_result)

                messages = [
                    SystemMessage(content=get_system_prompt()),
                    HumanMessage(content=get_answer_generation_prompt(query, formatted_context))
                ]

                response = await self.llm.ainvoke(messages)
                answer = response.content

                # Calculate confidence based on results
                confidence = min(0.9, 0.3 + (len(search_result.pages) * 0.1))

                return OneNoteSearchResponse(
                    answer=answer,
                    sources=search_result.pages,
                    confidence=confidence,
                    search_query_used=query,
                    metadata={
                        "execution_time": search_result.execution_time,
                        "api_calls": search_result.api_calls_made,
                        "total_results": search_result.total_count,
                        "search_method": search_method
                    }
                )
            else:
                # No results found
                messages = [
                    SystemMessage(content=get_system_prompt()),
                    HumanMessage(content=get_no_results_prompt(query))
                ]

                response = await self.llm.ainvoke(messages)

                return OneNoteSearchResponse(
                    answer=response.content,
                    sources=[],
                    confidence=0.1,
                    search_query_used=query,
                    metadata={
                        "no_results": True,
                        "search_method": search_method,
                        "execution_time": time.time() - start_time
                    }
                )

        except OneNoteSearchError as e:
            logger.error(f"OneNote search error: {e}")
            return OneNoteSearchResponse(
                answer=f"I encountered an error while searching OneNote: {e}",
                sources=[],
                confidence=0.0,
                search_query_used=query,
                metadata={"search_error": str(e), "search_method": search_method}
            )

    async def initialize(self) -> None:
        """Initialize the agent and ensure authentication."""
        try:
            # Test authentication
            token = await self.authenticator.get_valid_token()
            is_valid = await self.authenticator.validate_token(token)

            if not is_valid:
                raise AuthenticationError("Token validation failed")

            # Initialize local search if available
            await self._initialize_local_search()

            logger.info("OneNote agent initialized successfully")

        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            raise

    async def _initialize_local_search(self) -> None:
        """Initialize local search engine if cache is available."""
        try:
            if await self._check_local_search_available():
                if self.local_search:
                    await self.local_search.initialize()
                    self._local_search_available = True
                    logger.info("Local search engine initialized and ready")
                else:
                    logger.warning("Local search not available despite cache check")
            else:
                logger.info("Local search not available - will use API search")

        except Exception as e:
            logger.warning(f"Failed to initialize local search, using API search: {e}")
            self._local_search_available = False

    def get_conversation_starters(self) -> List[str]:
        """Get example conversation starters."""
        from .prompts import CONVERSATION_STARTERS
        return CONVERSATION_STARTERS

    async def get_cache_status(self) -> Dict[str, Any]:
        """Get information about local cache status."""
        try:
            status = {
                "local_search_available": self._local_search_available,
                "cache_directory_exists": False,
                "cached_pages_count": 0,
                "last_sync": None,
                "search_mode": "api"
            }

            # Check cache directory
            if self.cache_manager:
                cache_root = self.cache_manager.cache_root
                status["cache_directory_exists"] = cache_root.exists()

                if cache_root.exists():
                    # Get cached pages count
                    try:
                        cached_pages = await self.cache_manager.get_all_cached_pages()
                        status["cached_pages_count"] = len(cached_pages)

                        if cached_pages:
                            # Get most recent sync time
                            latest_sync = max(page.metadata.cached_at for page in cached_pages)
                            status["last_sync"] = latest_sync.isoformat()

                    except Exception as e:
                        logger.warning(f"Error getting cached pages count: {e}")

            # Determine search mode
            if self._local_search_available:
                status["search_mode"] = "hybrid" if status["cached_pages_count"] > 0 else "api"
            else:
                status["search_mode"] = "api"

            return status

        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {
                "local_search_available": False,
                "error": str(e),
                "search_mode": "api"
            }

    async def cleanup(self) -> None:
        """Cleanup resources used by the agent."""
        try:
            # Close local search database connection
            if self._local_search:
                await self._local_search.close()
                logger.debug("Local search engine closed")

            # Close semantic search if it has cleanup
            if hasattr(self._semantic_search_engine, 'close'):
                await self._semantic_search_engine.close()

        except Exception as e:
            logger.warning(f"Error during agent cleanup: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def list_notebooks(self) -> List[Dict[str, Any]]:
        """List all notebooks directly via search tool."""
        try:
            logger.info("Fetching OneNote notebooks list")

            # Ensure we have a valid authenticator and search tool
            if not self.search_tool:
                raise Exception("Search tool not initialized")

            notebooks = await self.search_tool.get_notebooks()
            logger.info(f"Retrieved {len(notebooks)} notebooks")
            return notebooks

        except Exception as e:
            logger.error(f"Failed to list notebooks: {e}")
            # Return empty list instead of raising to prevent CLI crashes
            return []

    async def get_recent_pages(self, limit: int = 10) -> List[OneNotePage]:
        """Get recent pages directly via search tool."""
        try:
            logger.info(f"Fetching {limit} recent OneNote pages")

            # Ensure we have a valid authenticator and search tool
            if not self.search_tool:
                raise Exception("Search tool not initialized")

            pages = await self.search_tool.get_recent_pages(limit)
            logger.info(f"Retrieved {len(pages)} recent pages")
            return pages

        except Exception as e:
            logger.error(f"Failed to get recent pages: {e}")
            # Return empty list instead of raising to prevent CLI crashes
            return []

    @logged
    async def get_page_content_by_title(self, title: str) -> Optional[OneNotePage]:
        """
        Get the full content of a OneNote page by its title.

        Args:
            title: Title of the page to retrieve

        Returns:
            OneNotePage with full content if found, None otherwise

        Raises:
            Exception: If operation fails
        """
        try:
            # Ensure we have a valid authenticator and search tool
            if not self.search_tool:
                raise Exception("Search tool not initialized")

            page = await self.search_tool.get_page_content_by_title(title)
            if page:
                logger.info(f"Retrieved content for page: {page.title}")
            else:
                logger.info(f"No page found with title: {title}")

            return page

        except Exception as e:
            logger.error(f"Failed to get page content by title '{title}': {e}")
            raise Exception(f"Failed to get page content: {e}")

    async def stream_query(self, query: str) -> AsyncGenerator[StreamingChunk, None]:
        """Alias for process_query to match test expectations."""
        async for chunk in self.process_query(query):
            yield chunk

if __name__ == "__main__":
    """Test OneNote agent functionality."""
    async def test_agent():
        try:
            agent = OneNoteAgent()
            await agent.initialize()

            print("Testing OneNote agent...")

            # Test direct search
            response = await agent.search_pages("test", max_results=3)
            print(f"✅ Search successful: {response.answer[:100]}...")
            print(f"   Sources: {len(response.sources)} pages")

            # Test streaming query
            print("\nTesting streaming query...")
            chunks = []
            async for chunk in agent.process_query("What are my recent notes?"):
                chunks.append(chunk)
                print(f"   {chunk.type}: {chunk.content[:50]}...")

            print(f"✅ Streaming successful: {len(chunks)} chunks")

        except Exception as e:
            print(f"❌ Agent test failed: {e}")

    asyncio.run(test_agent())
