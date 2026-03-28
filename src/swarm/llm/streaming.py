from typing import AsyncIterator, Callable
import json


async def stream_to_async_generator(
    stream: AsyncIterator[str],
) -> AsyncIterator[str]:
    async for chunk in stream:
        yield chunk


async def parse_streaming_response(
    stream: AsyncIterator[str],
    callback: Callable[[str], None] | None = None,
) -> str:
    full_response = []
    async for chunk in stream:
        if callback:
            callback(chunk)
        full_response.append(chunk)
    return "".join(full_response)


def format_tools_for_ollama(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for tool in tools
    ]


def parse_tool_calls(response: str) -> list[dict]:
    try:
        data = json.loads(response)
        if isinstance(data, dict) and "tool_calls" in data:
            return data["tool_calls"]
        if isinstance(data, dict) and "message" in data and "tool_calls" in data["message"]:
            return data["message"]["tool_calls"]
    except json.JSONDecodeError:
        pass
    return []


async def parse_stream_with_tools(
    stream: AsyncIterator[str],
) -> tuple[str, list[dict]]:
    full_response = []
    tool_calls = []

    buffer = ""

    async for chunk in stream:
        full_response.append(chunk)
        buffer += chunk

        while "```tool" in buffer or "tool_call" in buffer or buffer.count("```") >= 2:
            if "```tool" in buffer and "```" in buffer[buffer.index("```tool") + 7:]:
                start = buffer.index("```tool")
                end = buffer.index("```", start + 7)
                tool_block = buffer[start + 7 : end].strip()
                buffer = buffer[end + 3 :]
                try:
                    tc = json.loads(tool_block)
                    if isinstance(tc, dict) and "name" in tc:
                        tool_calls.append(tc)
                except json.JSONDecodeError:
                    pass
            else:
                break

    return "".join(full_response), tool_calls
