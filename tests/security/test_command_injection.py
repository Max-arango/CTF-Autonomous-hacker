"""Security tests for command injection prevention"""
import pytest
from src.execution.engine import ExecutionEngine, CommandWrapper


@pytest.fixture
def execution_engine():
    engine = ExecutionEngine()
    return engine


@pytest.mark.asyncio
async def test_command_injection_prevention(execution_engine):
    """Test that command injection is prevented in tool wrappers."""
    # CommandWrapper uses format strings, not shell interpolation
    wrapper = CommandWrapper(
        tool_name="test_tool",
        execution_engine=execution_engine,
        command_template="echo {message}",
    )
    
    # Attempt injection
    result = await wrapper.execute(
        arguments={"message": "hello; rm -rf /"},
        agent_id="test-agent",
    )
    
    # Should execute literal command, not inject
    assert "hello; rm -rf /" in result.stdout or result.success is False


@pytest.mark.asyncio
async def test_tool_allowlist_enforcement(execution_engine):
    """Test that only allowed tools can be executed."""
    # Agent with restricted tools
    allowed_tools = ["read_file", "write_file"]
    
    result = await execution_engine.execute_tool(
        tool_name="execute_command",
        arguments={"command": "ls"},
        agent_id="test-agent",
        allowed_tools=allowed_tools,
    )
    
    assert result.success is False
    assert "not allowed" in result.error


@pytest.mark.asyncio
async def test_resource_limits_enforcement(execution_engine):
    """Test that resource limits are enforced."""
    # Timeout enforcement
    result = await execution_engine.execute_command(
        command="sleep 10",
        agent_id="test-agent",
        timeout=1,  # 1 second timeout
    )
    
    assert result.success is False
    assert "timed out" in result.error.lower() or result.exit_code == -1