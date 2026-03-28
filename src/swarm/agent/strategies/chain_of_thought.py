from typing import AsyncIterator, Protocol
from dataclasses import dataclass
import structlog


class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        stream: bool = True,
    ) -> str | AsyncIterator[str]: ...


@dataclass
class ReasoningResult:
    reasoning_trace: list[str]
    final_answer: str
    confidence: float = 1.0


class ReasoningStrategy(Protocol):
    name: str

    async def think(
        self,
        llm: LLMClient,
        prompt: str,
        system: str | None = None,
        **kwargs,
    ) -> ReasoningResult: ...


logger = structlog.get_logger()


class ChainOfThought:
    name = "CoT"

    async def think(
        self,
        llm: LLMClient,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> ReasoningResult:
        cot_prompt = f"""{prompt}

Think through this step by step. Break down your reasoning into clear, numbered steps.
Show your work at each stage. Be thorough but concise.

Steps:"""

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": cot_prompt})

        response = await llm.chat(messages, temperature=temperature, stream=False)

        steps = self._parse_steps(response)
        trace = steps if steps else [response]

        logger.debug("cot_reasoning_completed", steps=len(steps))

        return ReasoningResult(
            reasoning_trace=trace,
            final_answer=response,
            confidence=0.8,
        )

    def _parse_steps(self, response: str) -> list[str]:
        steps = []
        lines = response.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")) or stripped.startswith(
                ("- ", "* ")
            ):
                steps.append(stripped)
        if not steps and response.strip():
            steps = [s.strip() for s in response.split("\n\n") if s.strip()]
        return steps
