"""Evidence Engine - Verifies agent claims"""
import asyncio
import hashlib
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from .models import EvidenceClaim, VerificationResult, VerificationStatus
from ..artifacts import ArtifactManager, get_artifact_manager
from ..execution import ExecutionEngine, get_execution_engine
from ..observability import get_logger, log_evidence_verification


class EvidenceEngine:
    """Verifies agent claims against actual evidence."""

    def __init__(self):
        self.artifact_manager: Optional[ArtifactManager] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self._verification_cache: Dict[str, VerificationResult] = {}

    async def initialize(self):
        """Initialize the engine."""
        self.artifact_manager = await get_artifact_manager()
        self.execution_engine = await get_execution_engine()

    async def verify_claim(
        self,
        claim: EvidenceClaim,
        agent_id: str,
    ) -> VerificationResult:
        """Verify a claim against available evidence."""
        # Check cache
        cache_key = f"{claim.agent_id}:{claim.id}"
        if cache_key in self._verification_cache:
            return self._verification_cache[cache_key]

        result = VerificationResult(claim_id=claim.id, verified_by=agent_id)

        try:
            if claim.type == "observation":
                result = await self._verify_observation(claim, agent_id)
            elif claim.type == "hypothesis":
                result = await self._verify_hypothesis(claim, agent_id)
            elif claim.type == "evidence":
                result = await self._verify_evidence(claim, agent_id)
            elif claim.type == "exploit":
                result = await self._verify_exploit(claim, agent_id)
            elif claim.type == "proof":
                result = await self._verify_proof(claim, agent_id)
            else:
                result.status = VerificationStatus.UNVERIFIED
                result.notes = f"Unknown claim type: {claim.type}"

        except Exception as e:
            result.status = VerificationStatus.UNVERIFIED
            result.notes = f"Verification error: {e}"

        # Cache result
        self._verification_cache[cache_key] = result

        # Log verification
        await log_evidence_verification(
            claim_id=claim.id,
            agent_id=agent_id,
            status=result.status.value,
            confidence=result.confidence,
        )

        return result

    async def _verify_observation(
        self,
        claim: EvidenceClaim,
        agent_id: str,
    ) -> VerificationResult:
        """Verify an observation claim."""
        result = VerificationResult(claim_id=claim.id, verified_by=agent_id)

        # Check for expected artifacts
        found_artifacts = []
        missing_artifacts = []

        for artifact_id in claim.expected_artifacts:
            artifact = await self.artifact_manager.get(artifact_id)
            if artifact:
                found_artifacts.append(artifact_id)
            else:
                missing_artifacts.append(artifact_id)

        # Check for expected commands (in execution history)
        # This would query the execution engine's history

        result.evidence_found = found_artifacts
        result.evidence_missing = missing_artifacts

        if not missing_artifacts:
            result.status = VerificationStatus.VERIFIED
            result.confidence = 0.9
        elif found_artifacts and missing_artifacts:
            result.status = VerificationStatus.PARTIALLY_VERIFIED
            result.confidence = len(found_artifacts) / len(claim.expected_artifacts) * 0.7
        else:
            result.status = VerificationStatus.UNVERIFIED
            result.confidence = 0.1

        return result

    async def _verify_hypothesis(
        self,
        claim: EvidenceClaim,
        agent_id: str,
    ) -> VerificationResult:
        """Verify a hypothesis claim."""
        result = VerificationResult(claim_id=claim.id, verified_by=agent_id)

        # Hypotheses require experiments to verify
        # Check if there are experiments for this hypothesis
        criteria = claim.verification_criteria
        required_experiments = criteria.get("required_experiments", [])

        if not required_experiments:
            result.status = VerificationStatus.UNVERIFIED
            result.notes = "No verification criteria specified for hypothesis"
            return result

        # Would check experiment results here
        # For now, return unverified
        result.status = VerificationStatus.UNVERIFIED
        result.notes = "Hypothesis verification requires experiment execution"
        return result

    async def _verify_evidence(
        self,
        claim: EvidenceClaim,
        agent_id: str,
    ) -> VerificationResult:
        """Verify an evidence claim."""
        result = VerificationResult(claim_id=claim.id, verified_by=agent_id)

        # Evidence should have artifacts and/or command outputs
        found_artifacts = []
        missing_artifacts = []

        for artifact_id in claim.expected_artifacts:
            artifact = await self.artifact_manager.get(artifact_id)
            if artifact:
                found_artifacts.append(artifact_id)
            else:
                missing_artifacts.append(artifact_id)

        result.evidence_found = found_artifacts
        result.evidence_missing = missing_artifacts

        if not missing_artifacts and found_artifacts:
            result.status = VerificationStatus.VERIFIED
            result.confidence = 0.95
        elif found_artifacts and missing_artifacts:
            result.status = VerificationStatus.PARTIALLY_VERIFIED
            result.confidence = 0.6
        else:
            result.status = VerificationStatus.UNVERIFIED
            result.confidence = 0.0

        return result

    async def _verify_exploit(
        self,
        claim: EvidenceClaim,
        agent_id: str,
    ) -> VerificationResult:
        """Verify an exploit claim."""
        result = VerificationResult(claim_id=claim.id, verified_by=agent_id)

        # Exploits need to demonstrate actual exploitation
        criteria = claim.verification_criteria

        # Check for proof of exploitation
        required_artifacts = criteria.get("required_artifacts", [])
        required_outputs = criteria.get("required_outputs", [])

        found_artifacts = []
        missing_artifacts = []

        for artifact_id in required_artifacts:
            artifact = await self.artifact_manager.get(artifact_id)
            if artifact:
                found_artifacts.append(artifact_id)
            else:
                missing_artifacts.append(artifact_id)

        # Would also check command outputs for exploitation indicators
        # e.g., shell obtained, flag read, privilege escalation

        result.evidence_found = found_artifacts
        result.evidence_missing = missing_artifacts

        if not missing_artifacts and found_artifacts:
            result.status = VerificationStatus.VERIFIED
            result.confidence = 0.9
        elif found_artifacts and missing_artifacts:
            result.status = VerificationStatus.PARTIALLY_VERIFIED
            result.confidence = 0.5
        else:
            result.status = VerificationStatus.UNVERIFIED
            result.confidence = 0.0

        return result

    async def _verify_proof(
        self,
        claim: EvidenceClaim,
        agent_id: str,
    ) -> VerificationResult:
        """Verify a proof claim (e.g., flag capture)."""
        result = VerificationResult(claim_id=claim.id, verified_by=agent_id)

        # Proof claims require highest standard
        criteria = claim.verification_criteria

        # Must have flag artifact
        flag_artifact_id = criteria.get("flag_artifact_id")
        flag_format = criteria.get("flag_format", "flag{.*}")

        if not flag_artifact_id:
            result.status = VerificationStatus.UNVERIFIED
            result.notes = "No flag artifact specified"
            return result

        artifact = await self.artifact_manager.get(flag_artifact_id)
        if not artifact:
            result.status = VerificationStatus.DISPROVEN
            result.notes = "Flag artifact not found"
            return result

        # Verify flag format
        import re
        if re.match(flag_format, artifact.content.strip()):
            result.status = VerificationStatus.VERIFIED
            result.confidence = 1.0
            result.evidence_found = [flag_artifact_id]
            result.notes = "Flag format verified"
        else:
            result.status = VerificationStatus.DISPROVEN
            result.confidence = 0.0
            result.notes = f"Flag format mismatch. Expected: {flag_format}"

        return result

    async def verify_flag(
        self,
        flag: str,
        challenge_id: str,
        agent_id: str,
        method: str,
        evidence_artifacts: List[str],
    ) -> VerificationResult:
        """Verify a captured flag."""
        result = VerificationResult(
            claim_id=f"flag_{challenge_id}",
            verified_by=agent_id,
        )

        # Check flag format
        from ..config.settings import get_settings
        settings = get_settings()

        format_matched = False
        for fmt in settings.flag_validation.formats:
            import re
            if re.match(fmt, flag):
                format_matched = True
                break

        if not format_matched:
            result.status = VerificationStatus.DISPROVEN
            result.confidence = 0.0
            result.notes = "Flag format does not match expected patterns"
            return result

        # Verify evidence artifacts exist
        found_artifacts = []
        for artifact_id in evidence_artifacts:
            artifact = await self.artifact_manager.get(artifact_id)
            if artifact:
                found_artifacts.append(artifact_id)

        if not evidence_artifacts or found_artifacts:
            result.status = VerificationStatus.VERIFIED
            result.confidence = 0.95
            result.evidence_found = found_artifacts
            result.notes = "Flag verified with supporting evidence"
        else:
            result.status = VerificationStatus.PARTIALLY_VERIFIED
            result.confidence = 0.5
            result.notes = "Flag format valid but missing supporting evidence"

        return result


# Global evidence engine
_evidence_engine: Optional[EvidenceEngine] = None


async def get_evidence_engine() -> EvidenceEngine:
    """Get global evidence engine."""
    global _evidence_engine
    if _evidence_engine is None:
        _evidence_engine = EvidenceEngine()
        await _evidence_engine.initialize()
    return _evidence_engine