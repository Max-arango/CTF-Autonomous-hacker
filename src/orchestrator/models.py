"""Orchestrator Models"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path


class ChallengeCategory(str, Enum):
    WEB = "web"
    CRYPTO = "crypto"
    PWN = "pwn"
    REVERSE = "reverse"
    FORENSICS = "forensics"
    OSINT = "osint"
    STEGO = "stego"
    MOBILE = "mobile"
    MALWARE = "malware"
    CLOUD = "cloud"
    NETWORK = "network"
    SUPPLY_CHAIN = "supply_chain"
    AD = "ad"
    WEB3 = "web3"
    AI_SECURITY = "ai_security"
    SIDECHANNEL = "sidechannel"
    FIRMWARE = "firmware"
    SOCIAL = "social"
    PROGRAMMING = "programming"
    META = "meta"
    UNKNOWN = "unknown"


class ChallengeType(str, Enum):
    JEOPARDY = "jeopardy"
    MACHINE = "machine"
    ATTACK_DEFENSE = "attack_defense"


@dataclass
class Challenge:
    """CTF Challenge."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: List[ChallengeCategory] = field(default_factory=list)
    challenge_type: ChallengeType = ChallengeType.JEOPARDY
    files: List[str] = field(default_factory=list)  # Artifact IDs
    target_info: Dict[str, Any] = field(default_factory=dict)
    credentials: Dict[str, str] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    flag_format: str = "flag{.*}"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ChallengeClassification:
    """Challenge classification result."""
    challenge_id: str
    categories: List[ChallengeCategory]
    confidence: float
    reasoning: str
    suggested_agents: List[str]
    attack_surface: "AttackSurface"


@dataclass
class AttackSurface:
    """Identified attack surface."""
    services: List[Dict[str, Any]] = field(default_factory=list)
    web_endpoints: List[str] = field(default_factory=list)
    open_ports: List[int] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    potential_vulnerabilities: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)


@dataclass
class SolveResult:
    """Result of challenge solving."""
    challenge_id: str
    success: bool
    flag: Optional[str] = None
    method: str = ""
    evidence: List[str] = field(default_factory=list)
    agents_used: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None