"""Unit tests for evidence engine"""
import pytest
from src.evidence.models import EvidenceClaim, VerificationResult, VerificationStatus
from src.evidence.engine import EvidenceEngine
from src.artifacts.manager import ArtifactManager
import tempfile
import asyncio


@pytest.fixture
async def artifact_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ArtifactManager()
        manager.storage_path = Path(tmpdir)
        yield manager


@pytest.fixture
def evidence_engine(artifact_manager):
    engine = EvidenceEngine()
    engine.artifact_manager = artifact_manager
    return engine


@pytest.mark.asyncio
async def test_verify_observation_with_artifact(evidence_engine, artifact_manager):
    """Test verifying observation with supporting artifact."""
    # Store an artifact
    artifact_id = await artifact_manager.store(
        content=b"test evidence",
        filename="evidence.txt",
        creator="test-agent",
    )
    
    claim = EvidenceClaim(
        agent_id="test-agent",
        type="observation",
        title="Test Observation",
        content="Found evidence",
        expected_artifacts=[artifact_id],
    )
    
    result = await evidence_engine.verify_claim(claim, "test-agent")
    
    assert result.status == VerificationStatus.VERIFIED
    assert artifact_id in result.evidence_found


@pytest.mark.asyncio
async def test_verify_observation_missing_artifact(evidence_engine):
    """Test verifying observation with missing artifact."""
    claim = EvidenceClaim(
        agent_id="test-agent",
        type="observation",
        title="Test Observation",
        content="Found evidence",
        expected_artifacts=["non-existent-id"],
    )
    
    result = await evidence_engine.verify_claim(claim, "test-agent")
    
    assert result.status == VerificationStatus.UNVERIFIED
    assert "non-existent-id" in result.evidence_missing


@pytest.mark.asyncio
async def test_verify_proof_flag_format(evidence_engine, artifact_manager):
    """Test flag verification with correct format."""
    # Store flag artifact
    artifact_id = await artifact_manager.store(
        content=b"flag{test_flag_here}",
        filename="flag.txt",
        creator="test-agent",
    )
    
    claim = EvidenceClaim(
        agent_id="test-agent",
        type="proof",
        title="Flag Capture",
        content="Captured flag",
        verification_criteria={
            "flag_artifact_id": artifact_id,
            "flag_format": "flag{.*}",
        },
    )
    
    result = await evidence_engine.verify_claim(claim, "test-agent")
    
    assert result.status == VerificationStatus.VERIFIED
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_verify_proof_invalid_flag(evidence_engine, artifact_manager):
    """Test flag verification with incorrect format."""
    artifact_id = await artifact_manager.store(
        content=b"not_a_flag",
        filename="flag.txt",
        creator="test-agent",
    )
    
    claim = EvidenceClaim(
        agent_id="test-agent",
        type="proof",
        title="Flag Capture",
        content="Captured flag",
        verification_criteria={
            "flag_artifact_id": artifact_id,
            "flag_format": "flag{.*}",
        },
    )
    
    result = await evidence_engine.verify_claim(claim, "test-agent")
    
    assert result.status == VerificationStatus.DISPROVEN


@pytest.mark.asyncio
async def test_verify_flag_direct(evidence_engine, artifact_manager):
    """Test direct flag verification."""
    artifact_id = await artifact_manager.store(
        content=b"flag{direct_verification_test}",
        filename="flag.txt",
        creator="test-agent",
    )
    
    result = await evidence_engine.verify_flag(
        flag="flag{direct_verification_test}",
        challenge_id="chal-1",
        agent_id="test-agent",
        method="direct",
        evidence_artifacts=[artifact_id],
    )
    
    assert result.status == VerificationStatus.VERIFIED
    assert result.confidence >= 0.9