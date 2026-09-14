"""Integration tests for orchestrator"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator.orchestrator import Orchestrator
from src.orchestrator.models import Challenge, ChallengeType, ChallengeCategory


@pytest.fixture
def mock_components():
    """Create mock components for testing."""
    with patch("src.orchestrator.orchestrator.get_agent_runtime") as mock_runtime, \
         patch("src.orchestrator.orchestrator.get_memory_manager") as mock_memory, \
         patch("src.orchestrator.orchestrator.get_evidence_engine") as mock_evidence, \
         patch("src.orchestrator.orchestrator.get_artifact_manager") as mock_artifacts, \
         patch("src.orchestrator.orchestrator.get_challenge_manager") as mock_challenge, \
         patch("src.orchestrator.orchestrator.get_llm_provider") as mock_llm:
        
        yield {
            "runtime": mock_runtime.return_value,
            "memory": mock_memory.return_value,
            "evidence": mock_evidence.return_value,
            "artifacts": mock_artifacts.return_value,
            "challenge": mock_challenge.return_value,
            "llm": mock_llm.return_value,
        }


@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_components):
    """Test orchestrator initialization."""
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    assert orchestrator.runtime is not None
    assert orchestrator.memory is not None
    assert orchestrator.evidence is not None
    assert orchestrator.artifacts is not None


@pytest.mark.asyncio
async def test_add_challenge(mock_components):
    """Test adding a challenge."""
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    # Mock LLM classification response
    mock_components["llm"].complete.return_value = MagicMock(
        content='{"categories": ["web"], "confidence": 0.9, "reasoning": "Web challenge", "suggested_agents": ["web"], "attack_surface": {}}'
    )
    
    challenge = await orchestrator.add_challenge(
        name="Test Web Challenge",
        description="A simple web challenge",
        challenge_type=ChallengeType.JEOPARDY,
    )
    
    assert challenge.name == "Test Web Challenge"
    assert ChallengeCategory.WEB in challenge.category
    assert challenge.id in orchestrator._active_challenges


@pytest.mark.asyncio
async def test_classify_challenge(mock_components):
    """Test challenge classification."""
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    mock_components["llm"].complete.return_value = MagicMock(
        content='{"categories": ["crypto", "web"], "confidence": 0.85, "reasoning": "Crypto in web app", "suggested_agents": ["crypto", "web"], "attack_surface": {}}'
    )
    
    challenge = Challenge(
        name="Crypto Web",
        description="Web app with custom crypto",
    )
    
    classification = await orchestrator.classify_challenge(challenge)
    
    assert ChallengeCategory.CRYPTO in classification.categories
    assert ChallengeCategory.WEB in classification.categories
    assert classification.confidence == 0.85


@pytest.mark.asyncio
async def test_solve_challenge(mock_components):
    """Test challenge solving flow."""
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    # Setup challenge
    challenge = Challenge(
        id="test-chal-1",
        name="Test Challenge",
        description="Test",
    )
    orchestrator._active_challenges[challenge.id] = challenge
    
    # Mock agent execution
    mock_agent = MagicMock()
    mock_agent.config.id = "orchestrator-agent-1"
    mock_agent.state = "COMPLETED"
    mock_agent.final_result = {
        "status": "success",
        "flag": "flag{test_flag}",
        "method": "Found in HTML comment",
        "evidence": ["artifact-1"],
    }
    mock_agent.child_agents = []
    
    mock_components["runtime"].create_agent.return_value = mock_agent
    mock_components["runtime"].spawn_agent.return_value = MagicMock()
    mock_components["runtime"].execute_agent.return_value = mock_agent
    
    # Mock evidence verification
    mock_components["evidence"].verify_flag.return_value = MagicMock(
        status="verified",
        confidence=0.95,
    )
    
    result = await orchestrator.solve_challenge(challenge.id)
    
    assert result.success is True
    assert result.flag == "flag{test_flag}"
    assert result.method == "Found in HTML comment"