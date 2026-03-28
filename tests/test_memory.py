import pytest
import asyncio
from swarm.memory.working import WorkingMemory


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.mark.asyncio
async def test_working_memory_put_get(working_memory):
    await working_memory.put("key1", {"data": "value"})
    result = await working_memory.get("key1")
    assert result == {"data": "value"}


@pytest.mark.asyncio
async def test_working_memory_get_default(working_memory):
    result = await working_memory.get("nonexistent", "default")
    assert result == "default"


@pytest.mark.asyncio
async def test_working_memory_get_many(working_memory):
    await working_memory.put("a", 1)
    await working_memory.put("b", 2)
    await working_memory.put("c", 3)

    result = await working_memory.get_many(["a", "c"])
    assert result == {"a": 1, "c": 3}


@pytest.mark.asyncio
async def test_working_memory_delete(working_memory):
    await working_memory.put("key", "value")
    assert await working_memory.has("key")
    await working_memory.delete("key")
    assert not await working_memory.has("key")


@pytest.mark.asyncio
async def test_working_memory_clear(working_memory):
    await working_memory.put("a", 1)
    await working_memory.put("b", 2)
    await working_memory.clear()
    assert len(await working_memory.keys()) == 0


@pytest.mark.asyncio
async def test_working_memory_order(working_memory):
    await working_memory.put("first", 1)
    await working_memory.put("second", 2)
    await working_memory.get("first")
    keys = await working_memory.keys()
    assert keys == ["second", "first"]
