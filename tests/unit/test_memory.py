"""Unit tests for memory system"""
import pytest
import asyncio
from src.memory.models import MemoryEntry, MemoryType, MemoryLayer, Finding
from src.memory.manager import MemoryManager


@pytest.fixture
def memory_manager():
    return MemoryManager()


@pytest.mark.asyncio
async def test_store_and_retrieve(memory_manager):
    """Test storing and retrieving memory entries."""
    entry = MemoryEntry(
        type=MemoryType.OBSERVATION,
        layer=MemoryLayer.SHORT_TERM,
        agent_id="test-agent",
        title="Test Observation",
        content="Test content",
        confidence=0.9,
        tags=["test", "observation"],
    )
    
    entry_id = await memory_manager.store(entry)
    retrieved = await memory_manager.retrieve(entry_id)
    
    assert retrieved is not None
    assert retrieved.id == entry_id
    assert retrieved.title == "Test Observation"
    assert retrieved.confidence == 0.9
    assert retrieved.access_count == 1


@pytest.mark.asyncio
async def test_query_by_agent(memory_manager):
    """Test querying by agent."""
    agent_id = "test-agent-1"
    
    for i in range(3):
        entry = MemoryEntry(
            type=MemoryType.OBSERVATION,
            layer=MemoryLayer.SHORT_TERM,
            agent_id=agent_id,
            title=f"Observation {i}",
            content=f"Content {i}",
        )
        await memory_manager.store(entry)
    
    # Add entry for different agent
    await memory_manager.store(MemoryEntry(
        type=MemoryType.OBSERVATION,
        layer=MemoryLayer.SHORT_TERM,
        agent_id="other-agent",
        title="Other",
        content="Other content",
    ))
    
    results = await memory_manager.query(agent_id=agent_id)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_query_by_type(memory_manager):
    """Test querying by memory type."""
    await memory_manager.store(MemoryEntry(
        type=MemoryType.OBSERVATION,
        layer=MemoryLayer.SHORT_TERM,
        agent_id="agent1",
        title="Obs 1",
        content="Content",
    ))
    
    await memory_manager.store(MemoryEntry(
        type=MemoryType.HYPOTHESIS,
        layer=MemoryLayer.SHORT_TERM,
        agent_id="agent1",
        title="Hyp 1",
        content="Content",
    ))
    
    results = await memory_manager.query(memory_type=MemoryType.OBSERVATION)
    assert len(results) == 1
    assert results[0].type == MemoryType.OBSERVATION


@pytest.mark.asyncio
async def test_store_finding(memory_manager):
    """Test storing findings."""
    finding = Finding(
        agent_id="test-agent",
        challenge_id="challenge-1",
        type="observation",
        title="Test Finding",
        content="Found something",
        confidence=0.85,
    )
    
    entry_id = await memory_manager.store_finding(finding)
    retrieved = await memory_manager.retrieve(entry_id)
    
    assert retrieved is not None
    assert retrieved.type == MemoryType.OBSERVATION
    assert retrieved.layer == MemoryLayer.TASK


@pytest.mark.asyncio
async def test_promotion(memory_manager):
    """Test memory promotion between layers."""
    entry = MemoryEntry(
        type=MemoryType.OBSERVATION,
        layer=MemoryLayer.SHORT_TERM,
        agent_id="agent1",
        title="Test",
        content="Content",
    )
    
    entry_id = await memory_manager.store(entry)
    
    # Promote to task memory
    await memory_manager.promote_to_task_memory(entry_id)
    retrieved = await memory_manager.retrieve(entry_id)
    assert retrieved.layer == MemoryLayer.TASK
    
    # Promote to long term
    await memory_manager.promote_to_long_term(entry_id)
    retrieved = await memory_manager.retrieve(entry_id)
    assert retrieved.layer == MemoryLayer.LONG_TERM