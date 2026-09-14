"""Permission Models"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Capability(str, Enum):
    INSTALL_PACKAGE = "INSTALL_PACKAGE"
    CREATE_RESTRICTED_MOUNT = "CREATE_RESTRICTED_MOUNT"
    CONFIGURE_ISOLATED_NETWORK = "CONFIGURE_ISOLATED_NETWORK"
    SET_REQUIRED_DEVICE_PERMISSION = "SET_REQUIRED_DEVICE_PERMISSION"
    PERFORM_CONTROLLED_PRIVILEGED_OPERATION = "PERFORM_CONTROLLED_PRIVILEGED_OPERATION"
    MANAGE_CONTAINER_LIFECYCLE = "MANAGE_CONTAINER_LIFECYCLE"
    READ_AUDIT_LOGS = "READ_AUDIT_LOGS"


class PermissionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class PermissionRequest:
    """Request for privileged operation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    capability: Capability = Capability.INSTALL_PACKAGE
    reason: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    scope: str = ""
    risk: str = "low"  # low|medium|high|critical
    status: PermissionStatus = PermissionStatus.PENDING
    requested_at: datetime = field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None
    decided_by: str = ""
    decision_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "capability": self.capability.value,
            "reason": self.reason,
            "parameters": self.parameters,
            "scope": self.scope,
            "risk": self.risk,
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "decision_reason": self.decision_reason,
        }


@dataclass
class PermissionResponse:
    """Response to permission request."""
    request_id: str
    approved: bool
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    granted_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None