import uuid
from pathlib import Path
from typing import Any
import structlog

from swarm.tools.base import Tool, ToolResult

logger = structlog.get_logger()


class ReadFileTool(Tool):
    def __init__(self, workspace_root: str = "."):
        self.name = "read_file"
        self.description = "Read the contents of a file"
        self.input_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"},
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-indexed)",
                    "default": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read",
                    "default": 2000,
                },
            },
            "required": ["path"],
        }
        self.workspace_root = Path(workspace_root).resolve()

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())
        file_path = arguments.get("path", "")
        offset = arguments.get("offset", 1)
        limit = arguments.get("limit", 2000)

        safe_path = self._resolve_safe_path(file_path)
        if not safe_path:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error="Path outside workspace",
            )

        try:
            content = safe_path.read_text()
            lines = content.split("\n")
            start = max(0, offset - 1)
            end = start + limit
            selected_lines = lines[start:end]

            output = "\n".join(f"{i+offset}: {line}" for i, line in enumerate(selected_lines))

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output,
            )

        except FileNotFoundError:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=f"File not found: {file_path}",
            )
        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )

    def _resolve_safe_path(self, path: str) -> Path | None:
        try:
            resolved = (self.workspace_root / path).resolve()
            resolved = resolved.resolve()
            if resolved.is_relative_to(self.workspace_root):
                return resolved
            return None
        except Exception:
            return None


class WriteFileTool(Tool):
    def __init__(self, workspace_root: str = "."):
        self.name = "write_file"
        self.description = "Write content to a file (creates or overwrites)"
        self.input_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
                "append": {
                    "type": "boolean",
                    "description": "Append to existing file instead of overwriting",
                    "default": False,
                },
            },
            "required": ["path", "content"],
        }
        self.workspace_root = Path(workspace_root).resolve()

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())
        file_path = arguments.get("path", "")
        content = arguments.get("content", "")
        append = arguments.get("append", False)

        safe_path = self._resolve_safe_path(file_path)
        if not safe_path:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error="Path outside workspace",
            )

        try:
            safe_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(safe_path, mode) as f:
                f.write(content)

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=f"Written {len(content)} characters to {file_path}",
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )

    def _resolve_safe_path(self, path: str) -> Path | None:
        try:
            resolved = (self.workspace_root / path).resolve()
            if resolved.is_relative_to(self.workspace_root):
                return resolved
            return None
        except Exception:
            return None
