"""Evidence Models"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    PARTIALLY_VERIFIED = "partially_verified"
    VERIFIED = "verified"
    DISPROVEN = "disproven"


@dataclass
class EvidenceClaim:
    """A claim that needs verification."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    challenge_id: Optional[str] = None
    type: str = "observation"  # observation|hypothesis|evidence|exploit|proof
    title: str = ""
    content: str = ""
    confidence: float = 0.0
    expected_artifacts: List[str] = field(default_factory=list)
    expected_commands: List[str] = field(default_factory=list)
    verification_criteria: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VerificationResult:
    """Result of evidence verification."""
    claim_id: str
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = 0.0
    evidence_found: List[str] = field(default_factory=list)
    evidence_missing: List[str] = field(default_factory=list)
    verification_details: Dict[str, Any] = field(default_factory=dict)
    verified_by: str = ""
    verified_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""