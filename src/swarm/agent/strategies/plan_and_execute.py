import structlog

from swarm.agent.strategies.chain_of_thought import ReasoningResult, LLMClient

logger = structlog.get_logger()


class PlanAndExecute:
    name = "PlanAndExecute"

    def __init__(self, max_plan_steps: int = 10):
        self.max_plan_steps = max_plan_steps

    async def think(
        self,
        llm: LLMClient,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> ReasoningResult:
        plan_prompt = f"""{prompt}

First, create a detailed plan to accomplish this task. Break it into numbered steps.
Each step should be atomic and actionable.

Plan:"""

        plan_messages = []
        if system:
            plan_messages.append({"role": "system", "content": system})
        plan_messages.append({"role": "user", "content": plan_prompt})

        plan_response = await llm.chat(plan_messages, temperature=temperature, stream=False)
        plan_messages.append({"role": "assistant", "content": plan_response})

        steps = self._parse_steps(plan_response)

        logger.debug("pae_plan_created", steps=len(steps))

        results = []
        for i, step in enumerate(steps, 1):
            execute_prompt = f"""Execute step {i} of your plan: {step}

Provide the result of executing this step."""

            execute_messages = [
                {"role": "system", "content": "You are executing a plan. Provide clear, actionable results."},
                {"role": "user", "content": execute_prompt},
            ]

            step_result = await llm.chat(execute_messages, temperature=0.5, stream=False)
            results.append(f"Step {i}: {step}\nResult: {step_result}")

        synthesis_prompt = f"""Based on the following step results, provide the final answer:

{chr(10).join(results)}

Final Answer:"""

        final_messages = [
            {"role": "system", "content": "You are synthesizing results from multiple steps into a coherent answer."},
            {"role": "user", "content": synthesis_prompt},
        ]

        final_answer = await llm.chat(final_messages, temperature=0.3, stream=False)

        logger.debug("pae_execution_completed", steps=len(steps))

        return ReasoningResult(
            reasoning_trace=[f"Plan: {plan_response}"] + results,
            final_answer=final_answer,
            confidence=0.85,
        )

    def _parse_steps(self, plan_response: str) -> list[str]:
        steps = []
        for line in plan_response.split("\n"):
            stripped = line.strip()
            if stripped and (
                stripped[0].isdigit() and "." in stripped[:3]
                or stripped.startswith(("- ", "* ", "• "))
            ):
                cleaned = stripped.lstrip("0123456789. - *•")
                if cleaned:
                    steps.append(cleaned.strip())
        return steps[: self.max_plan_steps]
