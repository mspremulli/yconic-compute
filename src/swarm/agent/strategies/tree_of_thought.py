import structlog

from swarm.agent.strategies.chain_of_thought import ReasoningResult, LLMClient

logger = structlog.get_logger()


class TreeOfThought:
    name = "ToT"

    def __init__(self, num_branches: int = 3, max_depth: int = 3):
        self.num_branches = num_branches
        self.max_depth = max_depth

    async def think(
        self,
        llm: LLMClient,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.8,
        **kwargs,
    ) -> ReasoningResult:
        tot_prompt = f"""{prompt}

Explore multiple different approaches or lines of reasoning. For each major branch:
1. Consider a distinct strategy or perspective
2. Evaluate the pros and cons
3. Trace through the implications
4. Assess confidence in each approach

After exploring branches, identify the most promising path and provide your final answer.

Branches:"""

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": tot_prompt})

        response = await llm.chat(messages, temperature=temperature, stream=False)

        branches = self._parse_branches(response)
        winner = self._select_winner(branches)

        logger.debug("tot_reasoning_completed", branches=len(branches))

        return ReasoningResult(
            reasoning_trace=[f"Branch: {b['name']}\n{b['reasoning']}" for b in branches],
            final_answer=winner["final"] if winner else response,
            confidence=0.7,
        )

    def _parse_branches(self, response: str) -> list[dict]:
        branches = []
        current = {"name": "Initial", "reasoning": "", "final": ""}
        in_final = False

        for line in response.split("\n"):
            stripped = line.strip().lower()
            if any(k in stripped for k in ["final", "best", "conclusion"]):
                in_final = True
            if stripped.startswith(("branch", "path", "approach", "option")):
                if current["reasoning"]:
                    branches.append(current)
                current = {"name": stripped, "reasoning": "", "final": ""}
                in_final = False
            elif in_final:
                current["final"] += line + "\n"
            else:
                current["reasoning"] += line + "\n"

        if current["reasoning"]:
            branches.append(current)

        return branches if branches else [{"name": "Default", "reasoning": response, "final": response}]

    def _select_winner(self, branches: list[dict]) -> dict | None:
        if not branches:
            return None
        return max(branches, key=lambda b: len(b["reasoning"]))
