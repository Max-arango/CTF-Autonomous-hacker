"""Scope Engine - Challenge scope management"""
import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ScopeType(str, Enum):
    TARGET_SCOPE = "target"
    DISCOVERY_SCOPE = "discovery"
    LATERAL_MOVEMENT_SCOPE = "lateral"
    CONTROL_SCOPE = "control"


@dataclass
class NetworkRange:
    """Represents a network range with CIDR notation."""
    network: str  # CIDR notation, e.g., "10.10.10.0/24"
    exact: bool = False  # Whether this is an exact match or a range
    
    def contains(self, ip: str) -> bool:
        """Check if this range contains the given IP."""
        try:
            network = ipaddress.ip_network(self.network, strict=False)
            address = ipaddress.ip_address(ip)
            return address in network
        except ValueError:
            return False


@dataclass
class ChallengeScope:
    """Formal ChallengeScope system.
    
    Separates:
    - TARGET_SCOPE: The exact targets an agent is allowed to interact with
    - DISCOVERY_SCOPE: Allowed discovery range (may be broader than target)
    - LATERAL_MOVEMENT_SCOPE: Allowed lateral movement between targets
    - CONTROL_SCOPE: Control plane and infrastructure targets
    
    Defaults to exact scope. Does NOT automatically expand
    10.10.10.42 into 10.10.10.0/24 unless explicit challenge
    configuration permits subnet discovery.
    """
    challenge_id: str
    
    # Target scope - exact IPs or ranges the agent can target
    target_scope: List[NetworkRange] = field(default_factory=list)
    
    # Discovery scope - broader range for scanning/discovery
    discovery_scope: List[NetworkRange] = field(default_factory=list)
    
    # Lateral movement scope - allowed movement between discovered targets
    lateral_movement_scope: List[NetworkRange] = field(default_factory=list)
    
    # Control scope - infrastructure and control plane targets
    control_scope: List[NetworkRange] = field(default_factory=list)
    
    # Whether subnet expansion is permitted (e.g., 10.10.10.42 -> 10.10.10.0/24)
    # Default: False - default to exact scope
    allow_subnet_expansion: bool = False
    
    # Timestamp
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_target(self, ip: str) -> bool:
        """Check if IP is within target scope."""
        # If target_scope is empty, check discovery_scope
        if not self.target_scope:
            return self._is_in_any_scope(ip, self.discovery_scope)
        
        return self._is_in_any_scope(ip, self.target_scope)
    
    def is_discovery(self, ip: str) -> bool:
        """Check if IP is within discovery scope."""
        return self._is_in_any_scope(ip, self.discovery_scope)
    
    def is_lateral(self, ip: str) -> bool:
        """Check if IP is within lateral movement scope."""
        return self._is_in_any_scope(ip, self.lateral_movement_scope)
    
    def is_control(self, ip: str) -> bool:
        """Check if IP is within control scope."""
        return self._is_in_any_scope(ip, self.control_scope)
    
    def _is_in_any_scope(self, ip: str, scopes: List[NetworkRange]) -> bool:
        """Check if IP is within any of the given scopes."""
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return False
        
        for scope in scopes:
            if scope.contains(ip):
                return True
        return False
    
    def check_scope(self, ip: str, scope_type: ScopeType) -> bool:
        """Check if an IP is within the specified scope type."""
        if scope_type == ScopeType.TARGET:
            return self.is_target(ip)
        elif scope_type == ScopeType.DISCOVERY:
            return self.is_discovery(ip)
        elif scope_type == ScopeType.LATERAL:
            return self.is_lateral(ip)
        elif scope_type == ScopeType.CONTROL:
            return self.is_control(ip)
        return False
    
    def add_range(self, scope_type: ScopeType, network: str, overwrite: bool = False):
        """Add a network range to the specified scope type."""
        range_obj = NetworkRange(network=network, exact=not self.allow_subnet_expansion)
        
        if scope_type == ScopeType.TARGET:
            self.target_scope.append(range_obj)
        elif scope_type == ScopeType.DISCOVERY:
            self.discovery_scope.append(range_obj)
        elif scope_type == ScopeType.LATERAL:
            self.lateral_movement_scope.append(range_obj)
        elif scope_type == ScopeType.CONTROL:
            self.control_scope.append(range_obj)
        
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "challenge_id": self.challenge_id,
            "target_scope": [{"network": r.network, "exact": r.exact} for r in self.target_scope],
            "discovery_scope": [{"network": r.network, "exact": r.exact} for r in self.discovery_scope],
            "lateral_movement_scope": [{"network": r.network, "exact": r.exact} for r in self.lateral_movement_scope],
            "control_scope": [{"network": r.network, "exact": r.exact} for r in self.control_scope],
            "allow_subnet_expansion": self.allow_subnet_expansion,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChallengeScope":
        """Create from dictionary."""
        scope = cls(challenge_id=data.get("challenge_id", ""))
        scope.allow_subnet_expansion = data.get("allow_subnet_expansion", False)
        
        for rng in data.get("target_scope", []):
            scope.add_range(ScopeType.TARGET, rng["network"], overwrite=True)
        for rng in data.get("discovery_scope", []):
            scope.add_range(ScopeType.DISCOVERY, rng["network"], overwrite=True)
        for rng in data.get("lateral_movement_scope", []):
            scope.add_range(ScopeType.LATERAL, rng["network"], overwrite=True)
        for rng in data.get("control_scope", []):
            scope.add_range(ScopeType.CONTROL, rng["network"], overwrite=True)
        
        return scope


@dataclass
class AgentScope:
    """Scope assigned to an agent for a specific challenge."""
    agent_id: str
    challenge_id: str
    
    # Inherited from challenge scope
    target_scope: List[NetworkRange] = field(default_factory=list)
    discovery_scope: List[NetworkRange] = field(default_factory=list)
    lateral_movement_scope: List[NetworkRange] = field(default_factory=list)
    control_scope: List[NetworkRange] = field(default_factory=list)
    
    # Agent-specific overrides
    custom_restrictions: Dict[str, Any] = field(default_factory=dict)
    
    def check(self, ip: str, scope_type: str) -> bool:
        """Check if IP is within the specified scope."""
        scope_map = {
            "target": self.target_scope,
            "discovery": self.discovery_scope,
            "lateral": self.lateral_movement_scope,
            "control": self.control_scope,
        }
        
        if scope_type not in scope_map:
            return False
        
        return self._is_in_any_scope(ip, scope_map[scope_type])
    
    @staticmethod
    def _is_in_any_scope(ip: str, scopes: List[NetworkRange]) -> bool:
        """Check if IP is within any of the given scopes."""
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return False
        
        for scope in scopes:
            if scope.contains(ip):
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "challenge_id": self.challenge_id,
            "target_scope": [{"network": r.network, "exact": r.exact} for r in self.target_scope],
            "discovery_scope": [{"network": r.network, "exact": r.exact} for r in self.discovery_scope],
            "lateral_movement_scope": [{"network": r.network, "exact": r.exact} for r in self.lateral_movement_scope],
            "control_scope": [{"network": r.network, "exact": r.exact} for r in self.control_scope],
            "custom_restrictions": self.custom_restrictions,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentScope":
        """Create from dictionary."""
        scope = cls(
            agent_id=data.get("agent_id", ""),
            challenge_id=data.get("challenge_id", ""),
        )
        
        for rng in data.get("target_scope", []):
            scope.add_range(ScopeType.TARGET, rng["network"])
        for rng in data.get("discovery_scope", []):
            scope.add_range(ScopeType.DISCOVERY, rng["network"])
        for rng in data.get("lateral_movement_scope", []):
            scope.add_range(ScopeType.LATERAL, rng["network"])
        for rng in data.get("control_scope", []):
            scope.add_range(ScopeType.CONTROL, rng["network"])
        
        scope.custom_restrictions = data.get("custom_restrictions", {})
        return scope