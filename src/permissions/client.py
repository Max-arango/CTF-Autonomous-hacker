"""Permission Client - Agent-side permission requests"""
import asyncio
import httpx
from typing import Dict, Any, Optional
from .models import PermissionRequest, PermissionResponse, Capability
from ..config.settings import get_settings
from ..observability import get_logger


class PermissionClient:
    """Client for requesting permissions from Permission Manager."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = f"http://permission-manager:{self.settings.security.permission_manager_port}"
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    async def request(
        self,
        agent_id: str,
        capability: str,
        reason: str,
        parameters: Dict[str, Any],
        scope: str = "",
        risk: str = "low",
    ) -> Dict[str, Any]:
        """Request a privileged operation."""
        if not self._client:
            await self.initialize()

        request = PermissionRequest(
            agent_id=agent_id,
            capability=Capability(capability),
            reason=reason,
            parameters=parameters,
            scope=scope,
            risk=risk,
        )

        try:
            response = await self._client.post(
                f"{self.base_url}/permissions/request",
                json=request.to_dict(),
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "request_id": request.id,
            }

    async def install_package(
        self,
        agent_id: str,
        package_name: str,
        package_manager: str = "apt",
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request package installation."""
        return await self.request(
            agent_id=agent_id,
            capability="INSTALL_PACKAGE",
            reason=f"Install {package_name} for agent execution",
            parameters={
                "package_name": package_name,
                "package_manager": package_manager,
                "version": version,
            },
            risk="medium",
        )

    async def create_mount(
        self,
        agent_id: str,
        source: str,
        target: str,
        readonly: bool = True,
    ) -> Dict[str, Any]:
        """Request restricted mount creation."""
        return await self.request(
            agent_id=agent_id,
            capability="CREATE_RESTRICTED_MOUNT",
            reason=f"Create mount for {source} -> {target}",
            parameters={
                "source": source,
                "target": target,
                "readonly": readonly,
            },
            risk="high",
        )


_permission_client: Optional[PermissionClient] = None


async def get_permission_client() -> PermissionClient:
    """Get global permission client."""
    global _permission_client
    if _permission_client is None:
        _permission_client = PermissionClient()
        await _permission_client.initialize()
    return _permission_client