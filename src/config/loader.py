"""Configuration loader"""
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load a YAML configuration file with environment variable substitution."""
    if not config_path.exists():
        return {}

    with open(config_path, "r") as f:
        content = f.read()

    # Simple environment variable substitution
    import os
    import re

    def replace_env(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))

    content = re.sub(r"\$\{([^}]+)\}", replace_env, content)

    return yaml.safe_load(content) or {}


def load_all_configs(config_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load all YAML configuration files from a directory."""
    configs = {}
    for config_file in config_dir.glob("*.yaml"):
        key = config_file.stem
        configs[key] = load_yaml_config(config_file)
    return configs


class ConfigManager:
    """Manages configuration loading and access."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent.parent.parent / "configs"
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._load_all()

    def _load_all(self):
        """Load all configuration files."""
        self._configs = load_all_configs(self.config_dir)

    def get(self, config_name: str, default: Any = None) -> Any:
        """Get a configuration section."""
        return self._configs.get(config_name, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get a nested configuration value."""
        if not keys:
            return default

        config_name = keys[0]
        config = self._configs.get(config_name, {})
        current = config

        for key in keys[1:]:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default

        return current

    def reload(self):
        """Reload all configurations."""
        self._load_all()


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: Optional[Path] = None) -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager