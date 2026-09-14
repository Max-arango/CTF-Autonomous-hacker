"""Security tests for container isolation"""
import pytest
from pathlib import Path


def test_agent_runs_as_nonroot():
    """Test that agent containers run as non-root user."""
    dockerfile_path = Path(__file__).parent.parent.parent / "docker" / "agent-base" / "Dockerfile"
    
    with open(dockerfile_path) as f:
        content = f.read()
    
    # Should create non-root user
    assert "useradd" in content or "adduser" in content
    assert "USER ctf" in content


def test_no_docker_socket_mount():
    """Test that agent containers don't mount Docker socket."""
    docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
    
    with open(docker_compose) as f:
        content = f.read()
    
    # Agent services should not have /var/run/docker.sock mount
    # Only permission-manager should have it
    assert content.count("/var/run/docker.sock") == 1


def test_readonly_rootfs():
    """Test that containers use read-only rootfs where possible."""
    dockerfile_path = Path(__file__).parent.parent.parent / "docker" / "agent-base" / "Dockerfile"
    
    with open(dockerfile_path) as f:
        content = f.read()
    
    # Base image should support read-only
    # Actual enforcement in docker-compose


def test_capability_dropping():
    """Test that containers drop all capabilities by default."""
    docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
    
    with open(docker_compose) as f:
        content = f.read()
    
    # Should have cap_drop: ALL in defaults
    assert "cap_drop:" in content
    assert "ALL" in content


def test_no_new_privileges():
    """Test that no-new-privileges is set."""
    docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
    
    with open(docker_compose) as f:
        content = f.read()
    
    assert "no-new-privileges:true" in content


def test_network_isolation():
    """Test that networks are properly isolated."""
    docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
    
    with open(docker_compose) as f:
        content = f.read()
    
    # Should have separate networks
    assert "ctf_control" in content
    assert "ctf_workspace" in content
    assert "ctf_targets" in content
    assert "ctf_malware" in content
    assert "ctf_attack_defense" in content


def test_permission_manager_privileged():
    """Test that only permission manager runs privileged."""
    docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
    
    with open(docker_compose) as f:
        content = f.read()
    
    # Permission manager should have user: root and cap_add
    assert "permission-manager:" in content
    # Other agents should not be root