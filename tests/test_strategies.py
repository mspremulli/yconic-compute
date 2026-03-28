import pytest
import asyncio
from swarm.agent.strategies.chain_of_thought import ChainOfThought
from swarm.agent.strategies.tree_of_thought import TreeOfThought
from swarm.agent.strategies.plan_and_execute import PlanAndExecute


class MockLLM:
    def __init__(self, response: str):
        self.response = response

    async def chat(self, messages, model=None, temperature=0.7, stream=False):
        return self.response


@pytest.mark.asyncio
async def test_chain_of_thought():
    llm = MockLLM("1. Step one\n2. Step two\n3. Therefore the answer is 42")
    strategy = ChainOfThought()

    result = await strategy.think(llm, "What is 21 * 2?")

    assert result.final_answer
    assert len(result.reasoning_trace) >= 1


@pytest.mark.asyncio
async def test_tree_of_thought():
    llm = MockLLM(
        "Branch approach A: Use method one\nFinal answer: Choose approach A"
    )
    strategy = TreeOfThought(num_branches=2)

    result = await strategy.think(llm, "Solve this problem two different ways")

    assert result.final_answer is not None
    assert len(result.reasoning_trace) >= 1


@pytest.mark.asyncio
async def test_plan_and_execute():
    llm = MockLLM("1. First step\n2. Second step\n3. Third step")
    strategy = PlanAndExecute()

    result = await strategy.think(llm, "Build a REST API")

    assert result.final_answer
    assert "Plan" in result.reasoning_trace[0] or len(result.reasoning_trace) >= 1


@pytest.mark.asyncio
async def test_cot_parse_steps():
    strategy = ChainOfThought()

    steps = strategy._parse_steps("1. First step\n2. Second step\n3. Third step")

    assert len(steps) == 3


@pytest.mark.asyncio
async def test_tot_parse_branches():
    strategy = TreeOfThought()

    branches = strategy._parse_branches(
        "Branch approach A: Use method one\nFinal: Use method one because..."
    )

    assert len(branches) >= 1
