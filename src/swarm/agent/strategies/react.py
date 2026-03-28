from __future__ import annotations
import re
import structlog

from swarm.agent.strategies.chain_of_thought import ReasoningResult, LLMClient

logger = structlog.get_logger()


class ReAct:
    name = "ReAct"

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations

    async def think(
        self,
        llm: LLMClient,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        tools: list[dict] | None = None,
        tool_executor: callable | None = None,
        **kwargs,
    ) -> ReasoningResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        context = f"Task: {prompt}\n\nYou have access to the following tools. Use them strategically."
        if tools:
            tool_desc = "\n".join(
                f"- {t['name']}: {t['description']}" for t in tools
            )
            context += f"\n\n{tool_desc}"

        messages.append({"role": "user", "content": context})

        thought_history = []
        iteration = 0
        final_answer = None

        while iteration < self.max_iterations:
            iteration += 1

            response = await llm.chat(messages, temperature=temperature, stream=False)
            messages.append({"role": "assistant", "content": response})
            thought_history.append(response)

            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                final_answer = self._extract_final_answer(response)
                break

            if not tool_executor:
                tool_result = "No tool executor provided. Cannot execute tools."
                messages.append({"role": "user", "content": f"Tool results: {tool_result}"})
                continue

            for tc in tool_calls:
                try:
                    result = await tool_executor(tc)
                    tool_msg = f"Tool '{tc['name']}' result: {result}"
                    messages.append({"role": "user", "content": tool_msg})
                    thought_history.append(tool_msg)
                except Exception as e:
                    error_msg = f"Tool '{tc['name']}' failed: {str(e)}"
                    messages.append({"role": "user", "content": error_msg})
                    thought_history.append(error_msg)

        logger.debug("react_reasoning_completed", iterations=iteration)

        return ReasoningResult(
            reasoning_trace=thought_history,
            final_answer=final_answer or response or "",
            confidence=0.75 if final_answer else 0.5,
        )

    def _extract_tool_calls(self, response: str) -> list[dict]:
        calls = []
        patterns = [
            r'```tool\s*\n(.*?)\n```',
            r'```json\s*\n(.*?)\n```',
            r'"name":\s*"([^"]+)".*?"arguments":\s*({.*?})',
            r'`Tool:\s*(\w+)\s*\nArgs:\s*(.*?)(?:`|$)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, response, re.DOTALL)
            for match in matches:
                if "name" in pattern:
                    try:
                        import json

                        data = json.loads(match.group(0))
                        if "name" in data:
                            calls.append({"name": data["name"], "arguments": data.get("arguments", {})})
                    except Exception:
                        pass
                else:
                    calls.append({"name": match.group(1).strip(), "arguments": {}})

        return calls

    def _extract_final_answer(self, response: str) -> str | None:
        patterns = [
            r"(?:Final Answer|Final Response):\s*(.*?)(?:\n\n|\n```|$)",
            r"(?:Therefore|In conclusion|Hence):\s*(.*?)(?:\n\n|\n```|$)",
            r"Answer:\s*(.*?)(?:\n\n|\n```|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None
