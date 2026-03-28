import pytest
import pytest_asyncio
import asyncio
from swarm.bus.message_bus import MessageBus
from swarm.types.message import AgentMessage


@pytest.fixture
def message_bus():
    return MessageBus()


@pytest.mark.asyncio
async def test_message_bus_publish_subscribe(message_bus):
    received = []

    async def handler(msg: AgentMessage):
        received.append(msg)

    await message_bus.subscribe("agent1", ["test.topic"], handler)

    msg = AgentMessage(
        id="1",
        sender="agent2",
        topic="test.topic",
        payload={"hello": "world"},
    )
    await message_bus.publish(msg)

    await message_bus.broadcast("agent2", "test.topic", {"broadcast": True})

    await asyncio.sleep(0.1)

    assert len(received) >= 1


@pytest.mark.asyncio
async def test_message_bus_direct_send(message_bus):
    received = []

    async def handler(msg: AgentMessage):
        received.append(msg)

    await message_bus.subscribe("agent2", ["direct"], handler)

    await message_bus.send_direct("agent1", "agent2", {"secret": 42})

    await asyncio.sleep(0.1)

    assert len(received) >= 1


@pytest.mark.asyncio
async def test_message_bus_subscription_count(message_bus):
    async def handler(msg: AgentMessage):
        pass

    sub1 = await message_bus.subscribe("agent1", ["topic1"], handler)
    sub2 = await message_bus.subscribe("agent1", ["topic2"], handler)

    subs = message_bus.get_subscriptions("agent1")
    assert len(subs) == 2

    await message_bus.unsubscribe(sub1)
    subs = message_bus.get_subscriptions("agent1")
    assert len(subs) == 1


@pytest.mark.asyncio
async def test_message_bus_unsubscribe(message_bus):
    count = [0]

    async def handler(msg: AgentMessage):
        count[0] += 1

    sub_id = await message_bus.subscribe("agent1", ["test"], handler)

    await message_bus.publish(AgentMessage(id="1", sender="s", topic="test", payload={}))
    await asyncio.sleep(0.1)
    await message_bus.unsubscribe(sub_id)

    assert count[0] == 1


@pytest.mark.asyncio
async def test_message_bus_topics_filter(message_bus):
    received = []

    async def handler(msg: AgentMessage):
        received.append(msg)

    await message_bus.subscribe("agent1", ["topic.a"], handler)

    await message_bus.publish(AgentMessage(id="1", sender="s", topic="topic.a", payload={}))
    await message_bus.publish(AgentMessage(id="2", sender="s", topic="topic.b", payload={}))

    await asyncio.sleep(0.1)

    assert len(received) == 1
    assert received[0].topic == "topic.a"
