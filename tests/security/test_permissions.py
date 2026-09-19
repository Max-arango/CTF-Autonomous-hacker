"""Security tests for permission system"""
import pytest
from src.permissions import PermissionManager
from src.permissions.models import PermissionRequest, Capability, PermissionStatus
from src.permissions.client import PermissionClient


@pytest.fixture
def permission_manager():
    return PermissionManager()


@pytest.mark.asyncio
async def test_deny_unknown_capability(permission_manager):
    """Test that unknown capabilities are denied."""
    request = PermissionRequest(
        agent_id="test-agent",
        capability=Capability("UNKNOWN_CAPABILITY"),
        reason="Test",
        parameters={},
    )
    
    result = await permission_manager.handle_request(request)
    
    assert result["success"] is False
    assert "Unknown capability" in result["error"]


@pytest.mark.asyncio
async def test_deny_unauthorized_agent(permission_manager):
    """Test that unauthorized agents are denied."""
    request = PermissionRequest(
        agent_id="unauthorized-agent",
        capability=Capability.INSTALL_PACKAGE,
        reason="Install package",
        parameters={"package_name": "curl", "package_manager": "apt"},
    )
    
    result = await permission_manager.handle_request(request)
    
    # Should be denied because agent not in allowed_agents
    assert result["success"] is False


@pytest.mark.asyncio
async def test_allow_orchestrator_install(permission_manager):
    """Test that orchestrator can install packages."""
    request = PermissionRequest(
        agent_id="orchestrator",
        capability=Capability.INSTALL_PACKAGE,
        reason="Install needed tool",
        parameters={"package_name": "nmap", "package_manager": "apt"},
    )
    
    result = await permission_manager.handle_request(request)
    
    # Orchestrator is allowed, but actual install would run
    # In test env, apt might not be available, but request should be approved
    assert result["success"] is True or "not_implemented" in str(result.get("result", {}))


@pytest.mark.asyncio
async def test_block_dangerous_packages(permission_manager):
    """Test that dangerous packages are blocked."""
    request = PermissionRequest(
        agent_id="orchestrator",
        capability=Capability.INSTALL_PACKAGE,
        reason="Install docker",
        parameters={"package_name": "docker.io", "package_manager": "apt"},
    )
    
    result = await permission_manager.handle_request(request)
    
    assert result["success"] is False
    assert "blocked" in result["error"].lower()


@pytest.mark.asyncio
async def test_parameter_validation(permission_manager):
    """Test parameter validation for capabilities."""
    # Missing required parameter
    request = PermissionRequest(
        agent_id="orchestrator",
        capability=Capability.INSTALL_PACKAGE,
        reason="Install package",
        parameters={"package_manager": "apt"},  # missing package_name
    )
    
    result = await permission_manager.handle_request(request)
    
    assert result["success"] is False
    assert "Invalid parameters" in result["error"]


@pytest.mark.asyncio
async def test_audit_logging(permission_manager):
    """Test that requests are audit logged."""
    initial_log_count = len(permission_manager._audit_log)
    
    request = PermissionRequest(
        agent_id="orchestrator",
        capability=Capability.READ_AUDIT_LOGS,
        reason="Read logs",
        parameters={"limit": 10},
    )
    
    await permission_manager.handle_request(request)
    
    assert len(permission_manager._audit_log) > initial_log_count
    log_entry = permission_manager._audit_log[-1]
    assert log_entry["event"] == "permission_requested"
    assert log_entry["data"]["agent_id"] == "orchestrator"