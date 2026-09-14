"""Unit tests for configuration"""
import pytest
from pathlib import Path
from src.config.loader import load_yaml_config, load_all_configs
from src.config.settings import get_settings, Settings


def test_load_yaml_config():
    """Test loading YAML config with env substitution."""
    config_dir = Path(__file__).parent.parent / "configs"
    system_config = load_yaml_config(config_dir / "system.yaml")
    
    assert "system" in system_config
    assert system_config["system"]["name"] == "autonomous-ctf-environment"


def test_load_all_configs():
    """Test loading all configs."""
    config_dir = Path(__file__).parent.parent / "configs"
    configs = load_all_configs(config_dir)
    
    assert "system" in configs
    assert "agents" in configs
    assert "tools" in configs
    assert "permissions" in configs
    assert "docker" in configs


def test_settings():
    """Test settings loading."""
    settings = get_settings()
    
    assert settings.system_name == "autonomous-ctf-environment"
    assert settings.mode == "JEOPARDY"
    assert settings.agent_runtime.max_agent_depth == 4
    assert settings.agent_runtime.max_active_agents == 32