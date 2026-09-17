"""Agent Identity Model"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class IdentityType(str, Enum):
    """Type of agent identity."""
    ORCHESTRATOR = "orchestrator"
    SPECIALIST = "specialist"
    SUB_AGENT = "sub_agent"
    SERVICE = "service"


@dataclass
class AgentIdentity:
    """Trusted agent identity model.
    
    The Permission Manager must authenticate the identity before authorization.
    Never derive security-sensitive role information using:
    agent_id.split("-")[1] or equivalent naming conventions.
    
    Agent identity must be explicit.
    """
    agent_id: str
    role: str
    challenge_id: str
    parent_id: Optional[str] = None
    issued_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    capabilities: List[str] = field(default_factory=list)
    policy_version: str = "1.0"
    identity_signature: str = ""
    identity_type: IdentityType = IdentityType.SPECIALIST
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize defaults."""
        if not self.identity_signature:
            # Generate a deterministic signature based on identity fields
            import hashlib
            sig_data = f"{self.agent_id}:{self.role}:{self.challenge_id}:{self.issued_at.isoformat()}:{self.policy_version}"
            self.identity_signature = hashlib.sha256(sig_data.encode()).hexdigest()[:32]
        
        if self.expires_at is None:
            # Default expiry: 24 hours
            self.expires_at = self.issued_at + timedelta(hours=24)
    
    def is_valid(self) -> bool:
        """Check if identity is still valid."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def is_expired(self) -> bool:
        """Check if identity has expired."""
        return not self.is_valid()
    
    def get_effective_capabilities(self) -> List[str]:
        """Get effective capabilities for this identity.
        
        In a full implementation, this would also consider:
        - Parent agent capabilities (for sub-agents)
        - Policy version constraints
        - Challenge scope restrictions
        """
        return list(self.capabilities)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "challenge_id": self.challenge_id,
            "parent_id": self.parent_id,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "capabilities": self.capabilities,
            "policy_version": self.policy_version,
            "identity_signature": self.identity_signature,
            "identity_type": self.identity_type.value,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentIdentity":
        """Create from dictionary."""
        identity = cls(
            agent_id=data.get("agent_id", ""),
            role=data.get("role", ""),
            challenge_id=data.get("challenge_id", ""),
            parent_id=data.get("parent_id"),
            capabilities=data.get("capabilities", []),
            policy_version=data.get("policy_version", "1.0"),
            identity_signature=data.get("identity_signature", ""),
            identity_type=IdentityType(data.get("identity_type", "specialist")),
            metadata=data.get("metadata", {}),
        )
        
        if "issued_at" in data:
            identity.issued_at = datetime.fromisoformat(data["issued_at"])
        if "expires_at" in data and data["expires_at"]:
            identity.expires_at = datetime.fromisoformat(data["expires_at"])
        
        return identity


class AgentIdentityManager:
    """Manages agent identities and their lifecycle."""
    
    def __init__(self):
        self._identities: Dict[str, AgentIdentity] = {}
        self._lock = None  # asyncio.Lock() when used in async context
    
    def create_identity(
        self,
        agent_id: str,
        role: str,
        challenge_id: str,
        parent_id: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        identity_type: IdentityType = IdentityType.SPECIALIST,
        ttl_hours: int = 24,
    ) -> AgentIdentity:
        """Create a new agent identity."""
        identity = AgentIdentity(
            agent_id=agent_id,
            role=role,
            challenge_id=challenge_id,
            parent_id=parent_id,
            capabilities=capabilities or [],
            identity_type=identity_type,
        )
        
        # Set expiry based on TTL
        identity.expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        self._identities[agent_id] = identity
        return identity
    
    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """Get agent identity by ID."""
        return self._identities.get(agent_id)
    
    def validate_identity(self, agent_id: str) -> bool:
        """Validate that an agent identity exists and is not expired."""
        identity = self._identities.get(agent_id)
        if not identity:
            return False
        return identity.is_valid()
    
    def revoke_identity(self, agent_id: str) -> bool:
        """Revoke an agent identity."""
        if agent_id in self._identities:
            del self._identities[agent_id]
            return True
        return False
    
    def update_capabilities(self, agent_id: str, capabilities: List[str]) -> bool:
        """Update agent capabilities."""
        identity = self._identities.get(agent_id)
        if not identity:
            return False
        
        # In a full implementation, this would check if capabilities are a subset
        # of parent capabilities (for sub-agents)
        identity.capabilities = capabilities
        return True
    
    def list_identities(
        self,
        challenge_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[AgentIdentity]:
        """List identities with optional filters."""
        results = list(self._identities.values())
        
        if challenge_id:
            results = [i for i in results if i.challenge_id == challenge_id]
        if role:
            results = [i for i in results if i.role == role]
        
        return results


# Global identity manager
_identity_manager: Optional[AgentIdentityManager] = None


def get_identity_manager() -> AgentIdentityManager:
    """Get global identity manager."""
    global _identity_manager
    if _identity_manager is None:
        _identity_manager = AgentIdentityManager()
    return _identity_manager