"""Unit tests for agent runtime"""
import pytest
import asyncio
from src.runtime.agent import Agent, AgentConfig, AgentState, ResourceBudget


def test_agent_config():
    """Test agent configuration."""
    config = AgentConfig(
        role="test",
        name="Test Agent",
        objective="Test objective",
    )
    
    assert config.role == "test"
    assert config.name == "Test Agent"
    assert config.depth == 0


def test_resource_budget():
    """Test resource budget tracking."""
    budget = ResourceBudget(
        max_tokens=1000,
        max_time_seconds=60,
        max_sub_agents=2,
        max_commands=10,
    )
    
    assert budget.can_spawn_sub_agent() is True
    assert budget.can_execute_command() is True
    assert budget.can_use_tokens(100) is True
    
    budget.record_sub_agent()
    budget.record_sub_agent()
    assert budget.can_spawn_sub_agent() is False
    
    budget.record_tokens(900)
    assert budget.can_use_tokens(200) is False


def test_agent_state_transitions():
    """Test agent state transitions."""
    config = AgentConfig(role="test", name="Test", objective="Test")
    agent = Agent(config=config)
    
    assert agent.state == AgentState.CREATED
    
    # Valid transitions
    assert agent.transition_to(AgentState.PLANNING) is True
    assert agent.state == AgentState.PLANNING
    
    assert agent.transition_to(AgentState.EXECUTING) is True
    assert agent.state == AgentState.EXECUTING
    
    assert agent.transition_to(AgentState.COMPLETED) is True
    assert agent.state == AgentState.COMPLETED
    
    # Invalid transition from COMPLETED
    assert agent.transition_to(AgentState.EXECUTING) is False


def test_agent_findings():
    """Test agent findings tracking."""
    config = AgentConfig(role="test", name="Test", objective="Test")
    agent = Agent(config=config)
    
    finding = {
        "type": "observation",
        "title": "Test finding",
        "content": "Test content",
        "confidence": 0.8,
    }
    
    agent.add_finding(finding)
    assert len(agent.findings) == 1
    assert agent.findings[0]["title"] == "Test finding"
    assert "timestamp" in agent.findings[0]
    assert agent.findings[0]["agent_id"] == agent.config.id


def test_agent_summary():
    """Test agent summary generation."""
    config = AgentConfig(role="web", name="Web Agent", objective="Test web")
    agent = Agent(config=config)
    agent.transition_to(AgentState.EXECUTING)
    
    summary = agent.get_summary()
    
    assert summary["role"] == "web"
    assert summary["name"] == "Web Agent"
    assert summary["state"] == "EXECUTING"
    assert "resource_usage" in summary