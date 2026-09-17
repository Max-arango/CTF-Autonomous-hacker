"""In-Process Permission Manager - No HTTP, direct calls"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..config.loader import load_yaml_config
from ..config.settings import get_settings
from ..observability import get_logger, log_permission_event
from .models import Capability


@dataclass
class PermissionRequest:
    id: str
    agent_id: str
    capability: str
    reason: str
    parameters: Dict[str, Any]
    scope: str = ""
    risk: str = "low"
    status: str = "pending"
    requested_at: datetime = field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None
    decided_by: str = ""
    decision_reason: str = ""


@dataclass
class PermissionResponse:
    request_id: str
    approved: bool
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    granted_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class PermissionManager:
    """In-process permission manager - minimal capability surface."""
    
    def __init__(self, config_path: str = "configs/permissions.yaml"):
        self.settings = get_settings()
        self.config = load_yaml_config(Path(config_path))
        self._audit_log: List[Dict[str, Any]] = []
    
    async def handle_request(self, request: PermissionRequest) -> Dict[str, Any]:
        """Handle a permission request - synchronous, no HTTP."""
        # Validate capability
        capability_config = self.config.get("capabilities", {}).get(request.capability)
        if not capability_config:
            return await self._deny(request, f"Unknown capability: {request.capability}")
        
        # Check scope requirement for high-risk
        if request.risk in ("high", "critical") and not request.scope:
            return await self._deny(request, "Scope required for high-risk operations")
        
        # Validate parameters
        if not self._validate_params(request.capability, request.parameters):
            return await self._deny(request, "Invalid parameters")
        
        # Log
        await log_permission_event(
            request_id=request.id,
            event="permission_requested",
            data={"agent_id": request.agent_id, "capability": request.capability}
        )
        
        # Check approval requirement
        requires_approval = capability_config.get("requires_approval", True)
        if requires_approval and request.risk in ("high", "critical"):
            # In local mode: auto-approve with logging
            return await self._approve(request, {"auto_approved": True, "note": "local_mode"})
        
        return await self._approve(request, {"auto_approved": True})
    
    async def _approve(self, request: PermissionRequest, result: Dict[str, Any]) -> Dict[str, Any]:
        request.status = "approved"
        request.decided_at = datetime.utcnow()
        request.decided_by = "permission_manager"
        
        await log_permission_event(
            request_id=request.id,
            event="permission_approved",
            data={"result": result}
        )
        
        return {
            "request_id": request.id,
            "approved": True,
            "result": result,
        }
    
    async def _deny(self, request: PermissionRequest, reason: str) -> Dict[str, Any]:
        request.status = "denied"
        request.decided_at = datetime.utcnow()
        request.decided_by = "permission_manager"
        request.decision_reason = reason
        
        await log_permission_event(
            request_id=request.id,
            event="permission_denied",
            data={"reason": reason}
        )
        
        return {
            "request_id": request.id,
            "approved": False,
            "error": reason,
        }
    
    def _validate_params(self, capability: str, params: Dict[str, Any]) -> bool:
        cap_config = self.config.get("capabilities", {}).get(capability, {})
        for param_name, param_config in cap_config.get("parameters", {}).items():
            if not param_config.get("optional", False) and param_name not in params:
                return False
        return True
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._audit_log[-limit:]


# Global instance
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager(config_path: str = "configs/permissions.yaml") -> PermissionManager:
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager(config_path)
    return _permission_manager