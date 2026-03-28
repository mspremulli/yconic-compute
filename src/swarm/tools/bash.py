import asyncio
import re
import structlog
import uuid
from typing import Any

from swarm.tools.base import Tool, ToolResult

logger = structlog.get_logger()


DENIED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"dd\s+if=",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"curl.*\|bash",
    r"wget.*\|bash",
    r">\s*/dev/sd",
    r"mkfs",
    r"dd.*of=/dev/",
]


class BashTool(Tool):
    def __init__(
        self,
        allowed_commands: list[str] | None = None,
        denied_patterns: list[str] | None = None,
        timeout_seconds: int = 60,
        workspace_root: str = ".",
    ):
        self.name = "bash"
        self.description = "Execute shell commands in a sandboxed environment"
        self.input_schema = {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
            },
            "required": ["command"],
        }
        self.allowed_commands = allowed_commands or ["python", "pytest", "git", "ruff", "pip"]
        self.denied_patterns = denied_patterns or DENIED_PATTERNS
        self.timeout_seconds = timeout_seconds
        self.workspace_root = workspace_root

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())
        command = arguments.get("command", "")

        if not self._is_allowed(command):
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error="Command not allowed",
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    error=f"Command timed out after {self.timeout_seconds}s",
                )

            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""

            if proc.returncode != 0:
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    output=output,
                    error=error or f"Exit code: {proc.returncode}",
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

    def _is_allowed(self, command: str) -> bool:
        for pattern in self.denied_patterns:
            if re.search(pattern, command):
                return False

        command_name = command.strip().split()[0] if command.strip() else ""
        if command_name not in self.allowed_commands:
            return False

        return True


class PythonReplTool(Tool):
    def __init__(
        self,
        timeout_seconds: int = 30,
        max_output_lines: int = 100,
        allowed_modules: list[str] | None = None,
    ):
        self.name = "python_repl"
        self.description = "Execute Python code in a sandboxed environment"
        self.input_schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        }
        self.timeout_seconds = timeout_seconds
        self.max_output_lines = max_output_lines
        self.allowed_modules = allowed_modules or ["math", "re", "json", "csv", "datetime", "collections"]

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())
        code = arguments.get("code", "")

        import io
        import sys

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        old_stdout = sys.stdout
        old_stderr = sys.stderr

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, exec, code, {"__name__": "__main__"}),
                timeout=self.timeout_seconds,
            )

            output = stdout_capture.getvalue()
            if len(output.split("\n")) > self.max_output_lines:
                output = "\n".join(output.split("\n")[: self.max_output_lines]) + "\n... (output truncated)"

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output,
            )

        except asyncio.TimeoutError:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=f"Execution timed out after {self.timeout_seconds}s",
            )
        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
            )
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


class CalculatorTool(Tool):
    def __init__(self):
        self.name = "calculator"
        self.description = "Evaluate mathematical expressions safely"
        self.input_schema = {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematical expression to evaluate"},
            },
            "required": ["expression"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())
        expression = arguments.get("expression", "")

        import ast
        import operator
        import math

        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }

        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
            "range": range,
            "int": int,
            "float": float,
            "str": str,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "True": True,
            "False": False,
            "None": None,
            "math_pi": math.pi,
            "math_e": math.e,
            "math_sqrt": math.sqrt,
            "math_log": math.log,
            "math_log10": math.log10,
            "math_exp": math.exp,
            "math_sin": math.sin,
            "math_cos": math.cos,
            "math_tan": math.tan,
            "math_floor": math.floor,
            "math_ceil": math.ceil,
        }

        try:
            node = ast.parse(expression, mode="eval")

            def eval_node(n):
                if isinstance(n, ast.Expression):
                    return eval_node(n.body)
                elif isinstance(n, ast.Constant):
                    return n.value
                elif isinstance(n, ast.BinOp):
                    left = eval_node(n.left)
                    right = eval_node(n.right)
                    return operators[type(n.op)](left, right)
                elif isinstance(n, ast.UnaryOp):
                    return operators[type(n.op)](eval_node(n.operand))
                elif isinstance(n, ast.Name):
                    if n.id in allowed_names:
                        return allowed_names[n.id]
                    raise ValueError(f"Unknown name: {n.id}")
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    if n.func.id in allowed_names:
                        args = [eval_node(arg) for arg in n.args]
                        return allowed_names[n.func.id](*args)
                    raise ValueError(f"Unknown function: {n.func.id}")
                elif isinstance(n, ast.List):
                    return [eval_node(e) for e in n.elts]
                elif isinstance(n, ast.Tuple):
                    return tuple(eval_node(e) for e in n.elts)
                else:
                    raise ValueError(f"Unsupported operation: {type(n)}")

            result = eval_node(node)
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=str(result),
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )
