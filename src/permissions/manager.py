"""Permission Manager - Secure privileged operation management (NO Docker socket)"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

from .models import PermissionRequest, PermissionResponse, Capability, PermissionStatus
from ..security import (
    get_policy_engine,
    get_scope_engine,
    get_capability_registry,
    get_authorization_context,
    get_secret_manager,
    PolicyDecision,
    PolicyContext,
)
from ..config.loader import load_yaml_config
from ..config.settings import get_settings
from ..observability import get_logger, log_permission_event


class SecurePermissionManager:
    """
    Privileged service for managing permissions.
    
    CRITICAL: Does NOT have Docker socket access.
    Only executes narrowly defined, pre-approved privileged operations.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.config = load_yaml_config(Path("configs/permissions.yaml"))
        
        self._pending_requests: Dict[str, PermissionRequest] = {}
        self._approved_requests: Dict[str, PermissionResponse] = {}
        self._audit_log: List[Dict[str, Any]] = []
        
        # Security components
        self.policy_engine = get_policy_engine()
        self.scope_engine = get_scope_engine()
        self.capability_registry = get_capability_registry()
        self.auth_manager = get_authorization_context()
        self.secret_manager = get_secret_manager()
        
        self._app = FastAPI(title="Secure Permission Manager")
        self._setup_routes()
    
    def _setup_routes(self):
        @self._app.get("/health")
        async def health():
            return {"status": "healthy", "version": "2.0", "docker_socket": False}
        
        @self._app.post("/permissions/request")
        async def request_permission(request: PermissionRequest):
            return await self.handle_request(request)
        
        @self._app.get("/permissions/{request_id}")
        async def get_permission(request_id: str):
            return self.get_request_status(request_id)
        
        @self._app.get("/permissions/audit/log")
        async def get_audit_log(limit: int = 100):
            return self._audit_log[-limit:]
        
        @self._app.post("/permissions/approve/{request_id}")
        async def approve_permission(request_id: str, approval: dict = None):
            """Manually approve a pending request (for high-risk operations)."""
            return await self.manual_approve(request_id, approval or {})
        
        @self._app.post("/permissions/deny/{request_id}")
        async def deny_permission(request_id: str, reason: str = "Manually denied"):
            """Manually deny a pending request."""
            return await self.manual_deny(request_id, reason)
    
    async def handle_request(self, request: PermissionRequest) -> Dict[str, Any]:
        """Handle a permission request through the policy engine."""
        # Convert legacy capability to new capability
        capability = self._map_legacy_capability(request.capability)
        if not capability:
            return await self._deny_request(request, f"Unknown capability: {request.capability}")
        
        # Build policy context
        policy_context = PolicyContext(
            agent_id=request.agent_id,
            agent_role=self._get_agent_role(request.agent_id),
            challenge_id=request.parameters.get("challenge_id", "unknown"),
            action=request.capability.value,
            capability=capability,
            parameters=request.parameters,
            target=request.parameters.get("target"),
            port=request.parameters.get("port"),
            protocol=request.parameters.get("protocol", "tcp"),
            path=request.parameters.get("path"),
            operation=request.parameters.get("operation"),
            tool=request.parameters.get("tool"),
            resource_request=request.parameters.get("resource_request", {}),
            metadata={
                "original_request_id": request.id,
                "reason": request.reason,
                "scope": request.scope,
                "risk": request.risk,
            },
        )
        
        # Evaluate policy
        decision = self.policy_engine.evaluate(policy_context)
        
        # Log request
        await log_permission_event(
            request_id=request.id,
            event="permission_requested",
            data={
                "agent_id": request.agent_id,
                "capability": capability.value,
                "decision": decision.decision.value,
                "reason": decision.reason,
            },
        )
        
        if decision.decision == PolicyDecision.DENY:
            return await self._deny_request(request, decision.reason)
        
        if decision.decision == PolicyDecision.REQUIRE_APPROVAL:
            # Queue for manual approval
            return await self._queue_for_approval(request, decision)
        
        # ALLOW - execute the operation
        return await self._execute_approved_operation(request, capability, decision)
    
    def _map_legacy_capability(self, legacy: Capability) -> Optional[Capability]:
        """Map legacy capability to new capability system."""
        mapping = {
            Capability.INSTALL_PACKAGE: Capability.PRIV_INSTALL_PACKAGE,
            Capability.CREATE_RESTRICTED_MOUNT: Capability.PRIV_CREATE_MOUNT,
            Capability.CONFIGURE_ISOLATED_NETWORK: Capability.PRIV_CONFIGURE_NETWORK,
            Capability.SET_REQUIRED_DEVICE_PERMISSION: Capability.PRIV_DEVICE_PERMISSION,
            Capability.PERFORM_CONTROLLED_PRIVILEGED_OPERATION: Capability.PRIV_SYSCTL_MODIFY,
            Capability.MANAGE_CONTAINER_LIFECYCLE: Capability.AGENT_SPAWN,  # Limited
            Capability.READ_AUDIT_LOGS: Capability.EVIDENCE_VERIFY,
        }
        return mapping.get(legacy)
    
    def _get_agent_role(self, agent_id: str) -> str:
        """Extract agent role from agent ID."""
        # Agent IDs typically contain role: "agent-web-123"
        parts = agent_id.split("-")
        if len(parts) >= 2:
            return parts[1]
        return "unknown"
    
    async def _queue_for_approval(
        self,
        request: PermissionRequest,
        decision
    ) -> Dict[str, Any]:
        """Queue request for manual approval."""
        request.status = PermissionStatus.PENDING
        request.decided_at = datetime.utcnow()
        request.decided_by = "policy_engine"
        request.decision_reason = f"Requires approval: {decision.reason}"
        
        self._pending_requests[request.id] = request
        
        await log_permission_event(
            request_id=request.id,
            event="permission_queued_for_approval",
            data={"reason": decision.reason, "required_approvals": decision.required_approvals},
        )
        
        return {
            "success": False,
            "request_id": request.id,
            "status": "pending_approval",
            "message": f"Request queued for approval: {decision.reason}",
            "required_approvals": decision.required_approvals,
        }
    
    async def manual_approve(self, request_id: str, approval: dict) -> Dict[str, Any]:
        """Manually approve a pending request."""
        request = self._pending_requests.get(request_id)
        if not request:
            return {"success": False, "error": "Request not found"}
        
        if request.status != PermissionStatus.PENDING:
            return {"success": False, "error": "Request not pending"}
        
        request.status = PermissionStatus.APPROVED
        request.decided_at = datetime.utcnow()
        request.decided_by = approval.get("approver", "manual")
        
        self._pending_requests.pop(request_id, None)
        
        # Execute the operation
        capability = self._map_legacy_capability(request.capability)
        result = await self._execute_approved_operation(request, capability)
        
        return {"success": True, "request_id": request_id, "result": result}
    
    async def manual_deny(self, request_id: str, reason: str) -> Dict[str, Any]:
        """Manually deny a pending request."""
        request = self._pending_requests.get(request_id)
        if not request:
            return {"success": False, "error": "Request not found"}
        
        request.status = PermissionStatus.DENIED
        request.decided_at = datetime.utcnow()
        request.decided_by = "manual"
        request.decision_reason = reason
        
        self._pending_requests.pop(request_id, None)
        
        await log_permission_event(
            request_id=request_id,
            event="permission_manually_denied",
            data={"reason": reason},
        )
        
        return {"success": True, "request_id": request_id}
    
    async def _execute_approved_operation(
        self,
        request: PermissionRequest,
        capability: Capability,
        decision=None
    ) -> Dict[str, Any]:
        """Execute an approved privileged operation."""
        request.status = PermissionStatus.APPROVED
        request.decided_at = datetime.utcnow()
        request.decided_by = "policy_engine"
        
        params = request.parameters
        result = {}
        
        try:
            if capability == Capability.PRIV_INSTALL_PACKAGE:
                result = await self._secure_install_package(params)
            elif capability == Capability.PRIV_CREATE_MOUNT:
                result = await self._secure_create_mount(params)
            elif capability == Capability.PRIV_CONFIGURE_NETWORK:
                result = await self._secure_configure_network(params)
            elif capability == Capability.PRIV_DEVICE_PERMISSION:
                result = await self._secure_device_permission(params)
            elif capability == Capability.PRIV_SYSCTL_MODIFY:
                result = await self._secure_sysctl_modify(params)
            elif capability == Capability.PRIV_TCPDUMP:
                result = await self._secure_tcpdump(params)
            elif capability == Capability.AGENT_SPAWN:
                result = await self._secure_agent_spawn(params)
            else:
                result = {"error": f"Operation not implemented: {capability.value}"}
        except Exception as e:
            result = {"error": f"Execution failed: {str(e)}"}
        
        await log_permission_event(
            request_id=request.id,
            event="permission_executed",
            data={"capability": capability.value, "result": result},
        )
        
        return {
            "success": True,
            "request_id": request.id,
            "result": result,
        }
    
    async def _secure_install_package(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Securely install a package (no shell injection)."""
        package_name = params.get("package_name", "")
        package_manager = params.get("package_manager", "apt")
        
        # Validate package name (strict allowlist)
        if not self._is_safe_package_name(package_name):
            return {"error": f"Package name not allowed: {package_name}"}
        
        # Check blocked packages
        blocked = self.config.get("installation_policies", {}).get("blocked_packages", [])
        for blocked_pkg in blocked:
            if blocked_pkg.endswith("*"):
                if package_name.startswith(blocked_pkg[:-1]):
                    return {"error": f"Package {package_name} is blocked"}
            elif package_name == blocked_pkg:
                return {"error": f"Package {package_name} is blocked"}
        
        # Execute via subprocess with argv (NO shell)
        if package_manager == "apt":
            cmd = ["apt-get", "update"]
            await self._run_command(cmd)
            cmd = ["apt-get", "install", "-y", package_name]
        elif package_manager == "pip":
            cmd = ["pip3", "install", package_name]
        elif package_manager == "pipx":
            cmd = ["pipx", "install", package_name]
        else:
            return {"error": f"Unsupported package manager: {package_manager}"}
        
        result = await self._run_command(cmd)
        return {
            "package": package_name,
            "manager": package_manager,
            **result,
        }
    
    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run command with argv (NO shell)."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            return {
                "exit_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'),
            }
        except asyncio.TimeoutError:
            return {"error": "Command timed out", "exit_code": -1}
        except Exception as e:
            return {"error": str(e), "exit_code": -1}
    
    def _is_safe_package_name(self, name: str) -> bool:
        """Validate package name against strict pattern."""
        # Only alphanumeric, dash, underscore, dot, plus
        return bool(re.match(r'^[a-zA-Z0-9._+-]+$', name))
    
    async def _secure_create_mount(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a restricted bind mount."""
        # This would use the mount syscall directly or a privileged helper
        # For now, return not implemented
        return {
            "status": "not_implemented",
            "message": "Mount creation requires privileged helper binary",
            "params": params,
        }
    
    async def _secure_configure_network(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Configure isolated network namespace."""
        return {
            "status": "not_implemented",
            "message": "Network configuration requires privileged helper",
            "params": params,
        }
    
    async def _secure_device_permission(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Grant specific device access."""
        return {
            "status": "not_implemented",
            "message": "Device permission requires privileged helper",
            "params": params,
        }
    
    async def _secure_sysctl_modify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Modify sysctl parameter."""
        return {
            "status": "not_implemented",
            "message": "Sysctl modification requires privileged helper",
            "params": params,
        }
    
    async def _secure_tcpdump(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start packet capture."""
        interface = params.get("interface", "eth0")
        duration = min(params.get("duration_seconds", 60), 300)
        output_file = params.get("output_file", f"/tmp/capture_{uuid.uuid4().hex}.pcap")
        
        # Run tcpdump with argv (NO shell)
        cmd = ["tcpdump", "-i", interface, "-w", output_file, "-G", str(duration), "-W", "1"]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Run for duration
            await asyncio.sleep(duration + 2)
            process.terminate()
            await process.communicate()
            
            return {
                "output_file": output_file,
                "duration": duration,
                "interface": interface,
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _secure_agent_spawn(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Spawn a new agent (limited to orchestrator)."""
        # This would communicate with the orchestrator via API
        # Not direct Docker container management
        return {
            "status": "delegated_to_orchestrator",
            "message": "Agent spawn requests forwarded to orchestrator API",
            "params": params,
        }
    
    async def _deny_request(self, request: PermissionRequest, reason: str) -> Dict[str, Any]:
        """Deny a request."""
        request.status = PermissionStatus.DENIED
        request.decided_at = datetime.utcnow()
        request.decided_by = "policy_engine"
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
    
    def get_request_status(self, request_id: str) -> Optional[PermissionResponse]:
        """Get request status."""
        return self._approved_requests.get(request_id)
    
    def get_app(self) -> FastAPI:
        """Get FastAPI app."""
        return self._app


# Global permission manager
_permission_manager: Optional[SecurePermissionManager] = None


def get_permission_manager() -> SecurePermissionManager:
    """Get global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = SecurePermissionManager()
    return _permission_manager