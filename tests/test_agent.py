import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from swarm.agent.agent import Agent, AgentConfig
from swarm.bus.message_bus import MessageBus
from swarm.memory.manager import MemoryManager
from swarm.llm.ollama_client import OllamaClient
from swarm.types.task import Task


@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=OllamaClient)
    llm.chat = AsyncMock(return_value="Mock response from LLM")
    return llm


@pytest.fixture
def mock_memory():
    memory = MagicMock(spec=MemoryManager)
    memory.store_episode = AsyncMock()
    memory.retrieve_semantic = AsyncMock(return_value=[])
    memory.retrieve_episodes = AsyncMock(return_value=[])
    return memory


@pytest.fixture
def mock_bus():
    return MessageBus()


@pytest.fixture
def agent_config():
    return AgentConfig(
        name="test_agent",
        role="tester",
        model="llama3.3:70b",
        system_prompt="You are a test agent.",
        strategy="CoT",
        tools=[],
        max_retries=2,
    )


@pytest.fixture
def agent(agent_config, mock_llm, mock_memory, mock_bus):
    return Agent(
        config=agent_config,
        llm=mock_llm,
        memory=mock_memory,
        message_bus=mock_bus,
    )


@pytest.mark.asyncio
async def test_agent_run_success(agent, mock_llm, mock_memory):
    task = Task(id="task1", description="Write a hello world function")

    result = await agent.run(task)

    assert result.success is True
    assert result.final_answer == "Mock response from LLM"
    mock_memory.store_episode.assert_called()


@pytest.mark.asyncio
async def test_agent_run_failure_no_retry():
    from unittest.mock import MagicMock, AsyncMock
    from swarm.agent.agent import Agent, AgentConfig
    from swarm.types.task import Task
    from swarm.bus.message_bus import MessageBus
    from swarm.memory.manager import MemoryManager
    
    config = AgentConfig(
        name="test_agent2",
        role="tester",
        model="llama3.3:70b",
        system_prompt="You are a test agent.",
        strategy="CoT",
        tools=[],
        max_retries=0,
    )
    
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(side_effect=[Exception("Single error")])
    mock_memory = MagicMock(spec=MemoryManager)
    mock_memory.store_episode = AsyncMock()
    
    agent2 = Agent(config=config, llm=mock_llm, memory=mock_memory, message_bus=MessageBus())
    task = Task(id="task3", description="Single failure test")
    
    result = await agent2.run(task)
    
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_agent_think(agent, mock_llm):
    result = await agent.think("What is 2+2?")

    assert result.final_answer == "Mock response from LLM"
    mock_llm.chat.assert_called()


@pytest.mark.asyncio
async def test_agent_retries_then_succeeds():
    from unittest.mock import MagicMock, AsyncMock
    from swarm.agent.agent import Agent, AgentConfig
    from swarm.types.task import Task
    from swarm.bus.message_bus import MessageBus
    from swarm.memory.manager import MemoryManager

    config = AgentConfig(
        name="retry_agent",
        role="tester",
        model="llama3.3:70b",
        system_prompt="You are a test agent.",
        strategy="CoT",
        tools=[],
        max_retries=2,
    )

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(side_effect=[
        Exception("Temporary error"),
        Exception("Temporary error"),
        "Success on third attempt",
    ])
    mock_memory = MagicMock(spec=MemoryManager)
    mock_memory.store_episode = AsyncMock()

    agent = Agent(config=config, llm=mock_llm, memory=mock_memory, message_bus=MessageBus())
    task = Task(id="retry_task", description="Retry test")

    result = await agent.run(task)

    assert result.success is True
    assert result.final_answer == "Success on third attempt"
    assert mock_llm.chat.call_count == 3


@pytest.mark.asyncio
async def test_agent_retries_respect_max_and_then_fails():
    from unittest.mock import MagicMock, AsyncMock
    from swarm.agent.agent import Agent, AgentConfig
    from swarm.types.task import Task
    from swarm.bus.message_bus import MessageBus
    from swarm.memory.manager import MemoryManager

    config = AgentConfig(
        name="fail_agent",
        role="tester",
        model="llama3.3:70b",
        system_prompt="You are a test agent.",
        strategy="CoT",
        tools=[],
        max_retries=2,
    )

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(side_effect=Exception("Permanent error"))
    mock_memory = MagicMock(spec=MemoryManager)
    mock_memory.store_episode = AsyncMock()

    agent = Agent(config=config, llm=mock_llm, memory=mock_memory, message_bus=MessageBus())
    task = Task(id="fail_task", description="Failure test")

    result = await agent.run(task)

    assert result.success is False
    assert "Permanent error" in result.error
    assert mock_llm.chat.call_count == 3  # initial + 2 retries
