"""Artifact Models"""
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, BinaryIO
from pathlib import Path


@dataclass
class ArtifactMetadata:
    """Artifact metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    sha256: str = ""
    mime_type: str = "application/octet-stream"
    size: int = 0
    creator: str = ""
    source: str = ""
    tags: List[str] = field(default_factory=list)
    relationships: Dict[str, List[str]] = field(default_factory=dict)  # type -> [artifact_ids]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "sha256": self.sha256,
            "mime_type": self.mime_type,
            "size": self.size,
            "creator": self.creator,
            "source": self.source,
            "tags": self.tags,
            "relationships": self.relationships,
            "timestamp": self.timestamp.isoformat(),
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactMetadata":
        metadata = cls(
            id=data.get("id", str(uuid.uuid4())),
            filename=data.get("filename", ""),
            sha256=data.get("sha256", ""),
            mime_type=data.get("mime_type", "application/octet-stream"),
            size=data.get("size", 0),
            creator=data.get("creator", ""),
            source=data.get("source", ""),
            tags=data.get("tags", []),
            relationships=data.get("relationships", {}),
            custom=data.get("custom", {}),
        )
        if "timestamp" in data:
            metadata.timestamp = datetime.fromisoformat(data["timestamp"])
        return metadata


@dataclass
class Artifact:
    """Artifact with content and metadata."""
    metadata: ArtifactMetadata
    content: bytes = b""
    _path: Optional[Path] = None

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def filename(self) -> str:
        return self.metadata.filename

    @property
    def sha256(self) -> str:
        return self.metadata.sha256

    def compute_hash(self) -> str:
        """Compute SHA256 of content."""
        return hashlib.sha256(self.content).hexdigest()

    def verify_hash(self) -> bool:
        """Verify content matches stored hash."""
        return self.compute_hash() == self.metadata.sha256