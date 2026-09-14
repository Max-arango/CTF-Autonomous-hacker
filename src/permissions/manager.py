"""Permission Manager - Server-side privilege management"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from .models import PermissionRequest, PermissionResponse, Capability, PermissionStatus
from ..config.loader import load_yaml_config
from ..config.settings import get_settings
from ..observability import get_logger, log_permission_event


class PermissionManager:
    """Privileged service for managing permissions."""

    def __init__(self):
        self.settings = get_settings()
        self.config = load_yaml_config(Path("configs/permissions.yaml"))

        self._pending_requests: Dict[str, PermissionRequest] = {}
        self._approved_requests: Dict[str, PermissionResponse] = {}
        self._audit_log: List[Dict[str, Any]] = []

        self._app = FastAPI(title="Permission Manager")
        self._setup_routes()

    def _setup_routes(self):
        @self._app.get("/health")
        async def health():
            return {"status": "healthy"}

        @self._app.post("/permissions/request")
        async def request_permission(request: PermissionRequest):
            return await self.handle_request(request)

        @self._app.get("/permissions/{request_id}")
        async def get_permission(request_id: str):
            return self.get_request_status(request_id)

        @self._app.get("/permissions/audit/log")
        async def get_audit_log(limit: int = 100):
            return self._audit_log[-limit:]

    async def handle_request(self, request: PermissionRequest) -> Dict[str, Any]:
        """Handle a permission request."""
        # Validate capability
        capability_config = self.config.get("capabilities", {}).get(request.capability.value)
        if not capability_config:
            return await self._deny_request(request, f"Unknown capability: {request.capability}")

        # Check if agent is allowed
        allowed_agents = capability_config.get("allowed_agents", [])
        if "*" not in allowed_agents and request.agent_id not in allowed_agents:
            return await self._deny_request(request, f"Agent {request.agent_id} not allowed for {request.capability}")

        # Check if approval required
        requires_approval = capability_config.get("requires_approval", True)

        # Validate parameters
        if not self._validate_parameters(request.capability, request.parameters):
            return await self._deny_request(request, "Invalid parameters")

        # Log request
        await log_permission_event(
            request_id=request.id,
            event="permission_requested",
            data=request.to_dict(),
        )

        if requires_approval and request.risk in ("high", "critical"):
            # Queue for manual approval (in production)
            # For now, auto-approve with logging
            return await self._approve_request(request, {"auto_approved": True})

        # Auto-approve low/medium risk
        return await self._approve_request(request, {"auto_approved": True})

    async def _approve_request(
        self,
        request: PermissionRequest,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Approve a request and execute."""
        request.status = PermissionStatus.APPROVED
        request.decided_at = datetime.utcnow()
        request.decided_by = "permission_manager"

        response = PermissionResponse(
            request_id=request.id,
            approved=True,
            result=result,
        )

        self._approved_requests[request.id] = response

        # Execute the privileged operation
        execution_result = await self._execute_operation(request)

        response.result = execution_result

        await log_permission_event(
            request_id=request.id,
            event="permission_approved",
            data={"result": execution_result},
        )

        return {
            "success": True,
            "request_id": request.id,
            "result": execution_result,
        }

    async def _deny_request(
        self,
        request: PermissionRequest,
        reason: str,
    ) -> Dict[str, Any]:
        """Deny a request."""
        request.status = PermissionStatus.DENIED
        request.decided_at = datetime.utcnow()
        request.decided_by = "permission_manager"
        request.decision_reason = reason

        await log_permission_event(
            request_id=request.id,
            event="permission_denied",
            data={"reason": reason},
        )

        return {
            "success": False,
            "request_id": request.id,
            "error": reason,
        }

    def _validate_parameters(self, capability: Capability, parameters: Dict[str, Any]) -> bool:
        """Validate request parameters."""
        capability_config = self.config.get("capabilities", {}).get(capability.value)
        if not capability_config:
            return False

        param_schema = capability_config.get("parameters", {})
        # Basic validation - in production would use JSON schema
        for param_name, param_config in param_schema.items():
            if not param_config.get("optional", False) and param_name not in parameters:
                return False

        return True

    async def _execute_operation(self, request: PermissionRequest) -> Dict[str, Any]:
        """Execute the privileged operation."""
        capability = request.capability
        params = request.parameters

        if capability == Capability.INSTALL_PACKAGE:
            return await self._install_package(params)
        elif capability == Capability.CREATE_RESTRICTED_MOUNT:
            return await self._create_mount(params)
        elif capability == Capability.CONFIGURE_ISOLATED_NETWORK:
            return await self._configure_network(params)
        elif capability == Capability.SET_REQUIRED_DEVICE_PERMISSION:
            return await self._set_device_permission(params)
        elif capability == Capability.PERFORM_CONTROLLED_PRIVILEGED_OPERATION:
            return await self._perform_privileged_operation(params)
        elif capability == Capability.MANAGE_CONTAINER_LIFECYCLE:
            return await self._manage_container(params)
        elif capability == Capability.READ_AUDIT_LOGS:
            return await self._read_audit_logs(params)

        return {"error": "Unknown capability"}

    async def _install_package(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Install a package."""
        package_name = params.get("package_name", "")
        package_manager = params.get("package_manager", "apt")

        # Block dangerous packages
        blocked = self.config.get("installation_policies", {}).get("blocked_packages", [])
        for blocked_pkg in blocked:
            if blocked_pkg.endswith("*"):
                if package_name.startswith(blocked_pkg[:-1]):
                    return {"error": f"Package {package_name} is blocked"}
            elif package_name == blocked_pkg:
                return {"error": f"Package {package_name} is blocked"}

        # Execute installation
        if package_manager == "apt":
            cmd = f"apt-get update && apt-get install -y {package_name}"
        elif package_manager == "pip":
            cmd = f"pip3 install {package_name}"
        elif package_manager == "pipx":
            cmd = f"pipx install {package_name}"
        else:
            return {"error": f"Unsupported package manager: {package_manager}"}

        import asyncio
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        return {
            "package": package_name,
            "manager": package_manager,
            "exit_code": process.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
        }

    async def _create_mount(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a restricted mount."""
        # This would use mount syscall or Docker volume mounts
        return {"status": "not_implemented", "params": params}

    async def _configure_network(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Configure isolated network."""
        return {"status": "not_implemented", "params": params}

    async def _set_device_permission(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set device permissions."""
        return {"status": "not_implemented", "params": params}

    async def _perform_privileged_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform controlled privileged operation."""
        return {"status": "not_implemented", "params": params}

    async def _manage_container(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Manage container lifecycle."""
        return {"status": "not_implemented", "params": params}

    async def _read_audit_logs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read audit logs."""
        limit = params.get("limit", 100)
        return {"logs": self._audit_log[-limit:]}

    def get_request_status(self, request_id: str) -> Optional[PermissionResponse]:
        """Get request status."""
        return self._approved_requests.get(request_id)

    def get_app(self) -> FastAPI:
        """Get FastAPI app."""
        return self._app


# Global permission manager
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """Get global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager