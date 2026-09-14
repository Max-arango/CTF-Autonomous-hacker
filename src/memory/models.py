"""Memory models"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryType(str, Enum):
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    EXPLOIT = "exploit"
    PROOF = "proof"
    FAILED_ATTEMPT = "failed_attempt"
    TOOL_OUTPUT = "tool_output"
    CREDENTIAL = "credential"
    VULNERABILITY = "vulnerability"
    TECHNIQUE = "technique"
    LESSON = "lesson"


class MemoryLayer(str, Enum):
    SHORT_TERM = "short_term"      # Current task state
    TASK = "task"                  # Current challenge knowledge
    LONG_TERM = "long_term"        # Reusable patterns across challenges


@dataclass
class MemoryEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MemoryType = MemoryType.OBSERVATION
    layer: MemoryLayer = MemoryLayer.SHORT_TERM
    agent_id: str = ""
    challenge_id: Optional[str] = None
    title: str = ""
    content: str = ""
    confidence: float = 0.0
    tags: List[str] = field(default_factory=list)
    related_entries: List[str] = field(default_factory=list)  # Related entry IDs
    artifacts: List[str] = field(default_factory=list)  # Artifact IDs
    commands: List[str] = field(default_factory=list)  # Command IDs
    source: str = ""  # Where this came from
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: Optional[datetime] = None
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "layer": self.layer.value,
            "agent_id": self.agent_id,
            "challenge_id": self.challenge_id,
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence,
            "tags": self.tags,
            "related_entries": self.related_entries,
            "artifacts": self.artifacts,
            "commands": self.commands,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        entry = cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MemoryType(data.get("type", "observation")),
            layer=MemoryLayer(data.get("layer", "short_term")),
            agent_id=data.get("agent_id", ""),
            challenge_id=data.get("challenge_id"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            confidence=data.get("confidence", 0.0),
            tags=data.get("tags", []),
            related_entries=data.get("related_entries", []),
            artifacts=data.get("artifacts", []),
            commands=data.get("commands", []),
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
        )
        if "created_at" in data:
            entry.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            entry.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("accessed_at"):
            entry.accessed_at = datetime.fromisoformat(data["accessed_at"])
        entry.access_count = data.get("access_count", 0)
        return entry


@dataclass
class Finding:
    """Structured finding record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    challenge_id: Optional[str] = None
    type: str = "observation"  # observation|hypothesis|evidence|exploit|proof
    title: str = ""
    content: str = ""
    confidence: float = 0.0
    related_findings: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_memory_entry(self) -> MemoryEntry:
        """Convert to memory entry."""
        return MemoryEntry(
            id=self.id,
            type=MemoryType(self.type),
            layer=MemoryLayer.TASK,
            agent_id=self.agent_id,
            challenge_id=self.challenge_id,
            title=self.title,
            content=self.content,
            confidence=self.confidence,
            related_entries=self.related_findings,
            artifacts=self.artifacts,
            commands=self.commands,
            source=f"agent:{self.agent_id}",
            metadata=self.metadata,
            created_at=self.timestamp,
        )


@dataclass
class Experiment:
    """Experiment record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    challenge_id: Optional[str] = None
    hypothesis: str = ""
    setup: str = ""
    command: str = ""
    expected_result: str = ""
    actual_result: str = ""
    evidence: List[str] = field(default_factory=list)
    conclusion: str = ""
    status: str = "pending"  # pending|running|completed|failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)