import uuid
from typing import Any
import structlog

try:
    import exa_py

    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False

from swarm.tools.base import Tool, ToolResult

logger = structlog.get_logger()


class WebSearchTool(Tool):
    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_per_minute: int = 30,
        max_results: int = 10,
        timeout_seconds: int = 30,
    ):
        self.name = "web_search"
        self.description = "Search the web for information using Exa API"
        self.input_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 10,
                },
            },
            "required": ["query"],
        }
        self.rate_limit = rate_limit_per_minute
        self.max_results = max_results
        self.timeout_seconds = timeout_seconds
        self._client = None
        self._api_key = api_key or self._get_api_key()

    def _get_api_key(self) -> str | None:
        import os
        return os.environ.get("EXA_API_KEY")

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())

        if not EXA_AVAILABLE:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error="exa-py not installed. Run: pip install exa-py",
            )

        if not self._api_key:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error="EXA_API_KEY not set in environment",
            )

        query = arguments.get("query", "")
        num_results = min(arguments.get("num_results", self.max_results), self.max_results)

        try:
            client = exa_py.Exa(self._api_key)
            search_response = client.search(
                query,
                num_results=num_results,
                type="auto",
            )

            results = []
            for result in search_response.results:
                results.append(
                    {
                        "title": result.title,
                        "url": result.url,
                        "snippet": result.text[:500] if result.text else "",
                    }
                )

            output = "\n\n".join(
                f"[{i+1}] {r['title']}\n   URL: {r['url']}\n   {r['snippet']}"
                for i, r in enumerate(results)
            )

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output,
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )


class UrlFetchTool(Tool):
    def __init__(self, timeout_seconds: int = 15, max_content_length: int = 50000):
        self.name = "url_fetch"
        self.description = "Fetch and summarize content from a URL"
        self.input_schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "query": {
                    "type": "string",
                    "description": "Optional query to extract specific information from the page",
                },
            },
            "required": ["url"],
        }
        self.timeout_seconds = timeout_seconds
        self.max_content_length = max_content_length

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())
        url = arguments.get("url", "")
        query = arguments.get("query")

        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()

                content = response.text[: self.max_content_length]

                if query:
                    output = f"URL: {url}\n\nContent (truncated to {self.max_content_length} chars):\n{content}\n\nQuery: {query}\n\nNote: To extract specific info, use the content above to answer the query."
                else:
                    output = f"URL: {url}\n\nContent (truncated to {self.max_content_length} chars):\n{content}"

                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=True,
                    output=output,
                )

        except httpx.TimeoutException:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=f"Request timed out after {self.timeout_seconds}s",
            )
        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )
