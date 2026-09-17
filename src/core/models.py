"""SQLAlchemy Models - Local SQLite"""
import uuid
import json
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, ForeignKey,
    Index, UniqueConstraint, Enum as SQLEnum, JSON, Boolean
)
from sqlalchemy.orm import relationship, declarative_mixin
from .db import Base


class ChallengeCategory(PyEnum):
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


class ChallengeType(PyEnum):
    JEOPARDY = "jeopardy"
    MACHINE = "machine"
    ATTACK_DEFENSE = "attack_defense"


class AgentState(PyEnum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(PyEnum):
    ORCHESTRATOR = "orchestrator"
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
    SUB_AGENT = "sub_agent"


class HypothesisStatus(PyEnum):
    PROPOSED = "proposed"
    TESTING = "testing"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    CONFIRMED = "confirmed"
    ABANDONED = "abandoned"
    DEAD_END = "dead_end"


class VerificationStatus(PyEnum):
    UNVERIFIED = "unverified"
    PARTIALLY_VERIFIED = "partially_verified"
    VERIFIED = "verified"
    DISPROVEN = "disproven"


class ScopeType(PyEnum):
    TARGET = "target"
    DISCOVERY = "discovery"
    LATERAL = "lateral"
    CONTROL = "control"


class NetworkPermission(PyEnum):
    CONNECT = "connect"
    SEND = "send"
    LISTEN = "listen"
    BIND = "bind"
    ICMP = "icmp"
    RAW_SOCKET = "raw_socket"
    PACKET_CAPTURE = "packet_capture"


class Capability(PyEnum):
    READ_AUDIT_LOGS = "read_audit_logs"


def gen_uuid():
    return str(uuid.uuid4())


class Challenge(Base):
    __tablename__ = "challenges"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    category = Column(JSON, default=list)  # List[ChallengeCategory]
    challenge_type = Column(SQLEnum(ChallengeType), default=ChallengeType.JEOPARDY)
    flag_format = Column(String(100), default="flag{.*}")
    target_info = Column(JSON, default=dict)
    credentials = Column(JSON, default=dict)
    constraints = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    
    # Scope fields
    target_scope = Column(JSON, default=list)
    discovery_scope = Column(JSON, default=list)
    lateral_scope = Column(JSON, default=list)
    control_scope = Column(JSON, default=list)
    allow_subnet_expansion = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agents = relationship("Agent", back_populates="challenge", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="challenge", cascade="all, delete-orphan")
    hypotheses = relationship("Hypothesis", back_populates="challenge", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="challenge", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="challenge", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="challenge", cascade="all, delete-orphan")
    solve_result = relationship("SolveResult", back_populates="challenge", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (Index("ix_challenge_name_type", "name", "challenge_type"),)


class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    parent_id = Column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    
    role = Column(SQLEnum(AgentRole), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    objective = Column(Text)
    depth = Column(Integer, default=0)
    
    state = Column(SQLEnum(AgentState), default=AgentState.CREATED, index=True)
    system_prompt = Column(Text)
    capabilities = Column(JSON, default=list)
    allowed_tools = Column(JSON, default=list)
    allowed_files = Column(JSON, default=list)
    allowed_networks = Column(JSON, default=list)
    
    # Resource budget
    max_tokens = Column(Integer, default=100000)
    max_time_seconds = Column(Integer, default=300)
    max_sub_agents = Column(Integer, default=4)
    max_commands = Column(Integer, default=100)
    tokens_used = Column(Integer, default=0)
    time_used_seconds = Column(Float, default=0.0)
    sub_agents_created = Column(Integer, default=0)
    commands_executed = Column(Integer, default=0)
    
    # Identity (explicit, not derived)
    identity_id = Column(String(36), nullable=True)
    identity_signature = Column(String(64), nullable=True)
    identity_expires_at = Column(DateTime, nullable=True)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Results
    final_result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="agents")
    parent = relationship("Agent", remote_side=[id], backref="children")
    findings = relationship("Finding", back_populates="agent", cascade="all, delete-orphan")
    hypotheses = relationship("Hypothesis", back_populates="agent", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="agent", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="agent", cascade="all, delete-orphan")
    tool_executions = relationship("ToolExecution", back_populates="agent", cascade="all, delete-orphan")
    observations = relationship("Observation", back_populates="agent", cascade="all, delete-orphan")
    
    __table_args__ = (Index("ix_agent_challenge_state", "challenge_id", "state"),)


class Finding(Base):
    __tablename__ = "findings"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    
    type = Column(String(50))  # observation|hypothesis|evidence|exploit|proof
    title = Column(String(255))
    content = Column(Text)
    confidence = Column(Float, default=0.0)
    
    supporting_artifacts = Column(JSON, default=list)  # artifact IDs
    supporting_commands = Column(JSON, default=list)   # tool_execution IDs
    verification_criteria = Column(JSON, default=dict)
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="findings")
    agent = relationship("Agent", back_populates="findings")
    verification = relationship("Verification", back_populates="finding", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (Index("ix_finding_challenge_type", "challenge_id", "type"),)


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    parent_id = Column(String(36), ForeignKey("hypotheses.id"), nullable=True)
    
    description = Column(Text, nullable=False)
    confidence = Column(Float, default=0.0)
    status = Column(SQLEnum(HypothesisStatus), default=HypothesisStatus.PROPOSED, index=True)
    
    supporting_evidence = Column(JSON, default=list)      # finding IDs
    contradicting_evidence = Column(JSON, default=list)   # finding IDs
    dependencies = Column(JSON, default=list)              # hypothesis IDs
    estimated_cost = Column(Integer, default=0)
    expected_information_gain = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tested_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="hypotheses")
    agent = relationship("Agent", back_populates="hypotheses")
    experiments = relationship("Experiment", back_populates="hypothesis", cascade="all, delete-orphan")
    
    __table_args__ = (Index("ix_hypothesis_challenge_status", "challenge_id", "status"),)


class Experiment(Base):
    __tablename__ = "experiments"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    hypothesis_id = Column(String(36), ForeignKey("hypotheses.id"), nullable=False, index=True)
    
    name = Column(String(255))
    description = Column(Text)
    tool_name = Column(String(100))
    arguments = Column(JSON, default=dict)
    expected_outcome = Column(Text)
    
    status = Column(String(50), default="pending")  # pending|running|completed|failed
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="experiments")
    agent = relationship("Agent", back_populates="experiments")
    hypothesis = relationship("Hypothesis", back_populates="experiments")
    tool_executions = relationship("ToolExecution", back_populates="experiment", cascade="all, delete-orphan")


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    experiment_id = Column(String(36), ForeignKey("experiments.id"), nullable=True, index=True)
    
    tool_name = Column(String(100), nullable=False)
    arguments = Column(JSON, default=dict)
    
    success = Column(Boolean)
    stdout = Column(Text)
    stderr = Column(Text)
    exit_code = Column(Integer)
    execution_time = Column(Float, default=0.0)
    
    artifacts_created = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    
    executed_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="tool_executions")
    experiment = relationship("Experiment", back_populates="tool_executions")
    observation = relationship("Observation", back_populates="tool_execution", uselist=False, cascade="all, delete-orphan")


class Observation(Base):
    __tablename__ = "observations"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    tool_execution_id = Column(String(36), ForeignKey("tool_executions.id"), nullable=True, unique=True)
    
    source_tool = Column(String(100))
    observation_type = Column(String(50))  # service|endpoint|file_type|string|embedded_artifact
    normalized_data = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="observations")
    agent = relationship("Agent", back_populates="observations")
    tool_execution = relationship("ToolExecution", back_populates="observation")


class Evidence(Base):
    __tablename__ = "evidence"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    finding_id = Column(String(36), ForeignKey("findings.id"), nullable=True, index=True)
    
    type = Column(String(50))  # observation|hypothesis|evidence|exploit|proof
    title = Column(String(255))
    content = Column(Text)
    confidence = Column(Float, default=0.0)
    
    artifact_ids = Column(JSON, default=list)
    tool_execution_ids = Column(JSON, default=list)
    verification_criteria = Column(JSON, default=dict)
    
    status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.UNVERIFIED, index=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(String(36), nullable=True)
    notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="evidence")
    agent = relationship("Agent", back_populates="evidence")
    finding = relationship("Finding", back_populates="verification")


class Artifact(Base):
    __tablename__ = "artifacts"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    
    filename = Column(String(500))
    sha256 = Column(String(64), index=True)
    mime_type = Column(String(100))
    size = Column(Integer)
    
    creator = Column(String(36))
    source = Column(String(100))
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="artifacts")
    
    __table_args__ = (Index("ix_artifact_challenge_sha", "challenge_id", "sha256"),)


class SolveResult(Base):
    __tablename__ = "solve_results"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, unique=True, index=True)
    
    success = Column(Boolean, default=False)
    flag = Column(String(500), nullable=True)
    method = Column(Text)
    evidence = Column(JSON, default=list)
    agents_used = Column(JSON, default=list)
    duration_seconds = Column(Float, default=0.0)
    error = Column(Text, nullable=True)
    
    completed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="solve_result")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    agent_id = Column(String(36), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    target = Column(String(255))
    reason = Column(Text)
    result = Column(String(50))  # success|partial|error|denied
    risk_level = Column(String(20))  # low|medium|high|critical
    artifacts = Column(JSON, default=list)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (Index("ix_audit_agent_time", "agent_id", "timestamp"),)


class AgentIdentity(Base):
    __tablename__ = "agent_identities"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    agent_id = Column(String(36), unique=True, nullable=False, index=True)
    role = Column(String(50), nullable=False)
    challenge_id = Column(String(36), nullable=False, index=True)
    parent_id = Column(String(36), nullable=True)
    
    capabilities = Column(JSON, default=list)
    policy_version = Column(String(20), default="1.0")
    identity_signature = Column(String(64), nullable=False)
    
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    metadata = Column(JSON, default=dict)
    
    __table_args__ = (Index("ix_identity_challenge_role", "challenge_id", "role"),)


class ResourceBudget(Base):
    __tablename__ = "resource_budgets"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    challenge_id = Column(String(36), ForeignKey("challenges.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    
    # Budgets
    max_tokens = Column(Integer, default=100000)
    max_time_seconds = Column(Integer, default=300)
    max_sub_agents = Column(Integer, default=4)
    max_commands = Column(Integer, default=100)
    max_llm_calls = Column(Integer, default=100)
    
    # Usage
    tokens_used = Column(Integer, default=0)
    time_used_seconds = Column(Float, default=0.0)
    sub_agents_created = Column(Integer, default=0)
    commands_executed = Column(Integer, default=0)
    llm_calls = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agent = relationship("Agent")


class ToolCost(Base):
    __tablename__ = "tool_costs"
    
    tool_name = Column(String(100), primary_key=True)
    category = Column(String(50))
    base_cost = Column(Integer, default=1)
    description = Column(Text)