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
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from ..auth.microsoft_auth import AuthenticationError, MicrosoftAuthenticator
from ..config.logging import log_api_call, log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import OneNotePage, SearchResult
from ..models.responses import (AgentState, OneNoteSearchResponse,
                                StreamingChunk)
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

        # Initialize LLM
        self.llm = ChatOpenAI(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            streaming=True
        )

        # Create LangGraph workflow
        self.graph = self._create_agent_graph()

        # Agent state
        self.current_state: Optional[AgentState] = None

    def _create_agent_graph(self) -> Any:
        """Create the LangGraph workflow for the agent."""
        workflow = StateGraph(MessagesState)

        # Add nodes
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("search_onenote", self._search_onenote_node)
        workflow.add_node("get_recent_pages", self._get_recent_pages_node)
        workflow.add_node("get_notebooks", self._get_notebooks_node)

        # Add conditional edges for tool routing
        workflow.add_conditional_edges(
            "agent",
            self._should_use_tools,
            {
                "search_onenote": "search_onenote",
                "get_recent_pages": "get_recent_pages",
                "get_notebooks": "get_notebooks",
                "end": "__end__"
            }
        )

        # Add edges back to agent after tool execution
        workflow.add_edge("search_onenote", "agent")
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
            "notes about", "pages about", "content about"
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
            # Default to search
            # Extract potential search query from content
            # This is a simplified extraction - in production you might want more sophisticated NLP
            query = content

            # Clean up the query
            for phrase in ["search for", "find", "show me", "look for"]:
                query = query.replace(phrase, "")

            query = query.strip()

            return {"tool": "search_onenote", "query": query, "max_results": 10}

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

            # Yield status update
            yield StreamingChunk.status_chunk("Processing your query...")

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
                elif any(tool in event for tool in ["search_onenote", "get_recent_pages", "get_notebooks"]):
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
        Direct search method for OneNote pages.

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            OneNoteSearchResponse with results
        """
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
                        "total_results": search_result.total_count
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
                    metadata={"no_results": True}
                )

        except Exception as e:
            logger.error(f"Search error: {e}")
            return OneNoteSearchResponse(
                answer=f"I encountered an error while searching: {e}",
                sources=[],
                confidence=0.0,
                search_query_used=query,
                metadata={"error": str(e)}
            )

    async def initialize(self) -> None:
        """Initialize the agent and ensure authentication."""
        try:
            # Test authentication
            token = await self.authenticator.get_valid_token()
            is_valid = await self.authenticator.validate_token(token)

            if not is_valid:
                raise AuthenticationError("Token validation failed")

            logger.info("OneNote agent initialized successfully")

        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            raise

    def get_conversation_starters(self) -> List[str]:
        """Get example conversation starters."""
        from .prompts import CONVERSATION_STARTERS
        return CONVERSATION_STARTERS

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
