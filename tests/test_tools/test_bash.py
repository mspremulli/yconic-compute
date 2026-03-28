import pytest
import asyncio
from swarm.tools.bash import BashTool, PythonReplTool, CalculatorTool


@pytest.mark.asyncio
async def test_calculator_basic():
    tool = CalculatorTool()

    result = await tool.execute({"expression": "2 + 2"})

    assert result.success is True
    assert result.output == "4"


@pytest.mark.asyncio
async def test_calculator_complex():
    tool = CalculatorTool()

    result = await tool.execute({"expression": "(10 + 5) * 2 - 3"})

    assert result.success is True


@pytest.mark.asyncio
async def test_calculator_invalid():
    tool = CalculatorTool()

    result = await tool.execute({"expression": "2 +"})

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_calculator_math_functions():
    tool = CalculatorTool()

    result = await tool.execute({"expression": "math_sqrt(16)"})

    assert result.success is True


@pytest.mark.asyncio
async def test_bash_allowed_command():
    tool = BashTool(allowed_commands=["echo"], timeout_seconds=5)

    result = await tool.execute({"command": "echo 'hello'"})

    assert result.success is True


@pytest.mark.asyncio
async def test_bash_denied_pattern():
    tool = BashTool(allowed_commands=["python"], timeout_seconds=5)

    result = await tool.execute({"command": "python -c 'import os; os.system(\"rm -rf /\")'"})

    assert result.success is False
    assert "not allowed" in result.error.lower()


@pytest.mark.asyncio
async def test_bash_command_not_allowed():
    tool = BashTool(allowed_commands=["echo"], timeout_seconds=5)

    result = await tool.execute({"command": "ls -la"})

    assert result.success is False
