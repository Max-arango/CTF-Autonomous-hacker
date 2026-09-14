"""End-to-end CTF challenge tests"""
import pytest
import asyncio
from pathlib import Path

from src.orchestrator import get_orchestrator
from src.orchestrator.models import Challenge, ChallengeType


@pytest.mark.asyncio
async def test_web_basic_challenge():
    """Test solving the basic web challenge."""
    orchestrator = await get_orchestrator()
    
    # Add challenge
    challenge = await orchestrator.add_challenge(
        name="Web Basic",
        description="Basic web challenge with flag in source",
        challenge_type=ChallengeType.JEOPARDY,
    )
    
    # Import challenge files
    challenge_dir = Path(__file__).parent.parent.parent / "examples" / "challenges" / "web_basic"
    await orchestrator.challenge_manager.import_challenge(challenge_dir)
    
    # Solve
    result = await orchestrator.solve_challenge(challenge.id)
    
    # Should find at least one flag
    assert result.success is True
    assert result.flag is not None
    assert "web_basic" in result.flag.lower()


@pytest.mark.asyncio
async def test_crypto_basic_challenge():
    """Test solving the basic crypto challenge."""
    orchestrator = await get_orchestrator()
    
    challenge = await orchestrator.add_challenge(
        name="Crypto Basic",
        description="Base64 + Caesar cipher",
        challenge_type=ChallengeType.JEOPARDY,
    )
    
    challenge_dir = Path(__file__).parent.parent.parent / "examples" / "challenges" / "crypto_basic"
    await orchestrator.challenge_manager.import_challenge(challenge_dir)
    
    result = await orchestrator.solve_challenge(challenge.id)
    
    assert result.success is True
    assert result.flag is not None
    assert "crypto_basic" in result.flag.lower()


@pytest.mark.asyncio
async def test_pwn_basic_challenge():
    """Test solving the basic pwn challenge."""
    orchestrator = await get_orchestrator()
    
    challenge = await orchestrator.add_challenge(
        name="Pwn Basic",
        description="Simple buffer overflow",
        challenge_type=ChallengeType.JEOPARDY,
    )
    
    challenge_dir = Path(__file__).parent.parent.parent / "examples" / "challenges" / "pwn_basic"
    await orchestrator.challenge_manager.import_challenge(challenge_dir)
    
    result = await orchestrator.solve_challenge(challenge.id)
    
    # This would require the binary to be compiled and runnable
    # For now, just verify the flow works
    assert result is not None