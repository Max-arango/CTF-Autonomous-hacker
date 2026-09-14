"""Scope Engine - Validates agent actions against challenge scope"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from pathlib import Path
import ipaddress
import re


class NetworkPolicy(str, Enum):
    """Network access policies."""
    ALLOW_ALL = "allow_all"
    ALLOW_LIST = "allow_list"
    DENY_LIST = "deny_list"
    INTERNAL_ONLY = "internal_only"


@dataclass
class NetworkRule:
    """A single network access rule."""
    cidr: str  # CIDR notation (e.g., "10.10.10.0/24")
    ports: List[int] = field(default_factory=list)  # Empty = all ports
    protocols: List[str] = field(default_factory=lambda: ["tcp", "udp"])  # tcp, udp, icmp
    description: str = ""
    
    def matches(self, target_ip: str, port: Optional[int] = None, protocol: str = "tcp") -> bool:
        """Check if a target matches this rule."""
        try:
            network = ipaddress.ip_network(self.cidr, strict=False)
            target = ipaddress.ip_address(target_ip)
            if target not in network:
                return False
        except ValueError:
            # If not a valid IP/CIDR, try hostname match
            if self.cidr != target_ip and not self._match_hostname(self.cidr, target_ip):
                return False
        
        if port is not None and self.ports and port not in self.ports:
            return False
        
        if protocol.lower() not in [p.lower() for p in self.protocols]:
            return False
        
        return True
    
    def _match_hostname(self, pattern: str, hostname: str) -> bool:
        """Match hostname against pattern (supports wildcards)."""
        if pattern == "*":
            return True
        if pattern.startswith("*."):
            domain = pattern[2:]
            return hostname == domain or hostname.endswith("." + domain)
        return pattern == hostname


@dataclass
class FilesystemRule:
    """A filesystem access rule."""
    path: str  # Path prefix (e.g., "/workspace/agent-123")
    read: bool = True
    write: bool = False
    description: str = ""
    
    def matches(self, target_path: str, operation: str) -> bool:
        """Check if a path matches this rule for the given operation."""
        target = Path(target_path).resolve()
        rule_path = Path(self.path).resolve()
        
        try:
            target.relative_to(rule_path)
        except ValueError:
            return False
        
        if operation == "read" and not self.read:
            return False
        if operation == "write" and not self.write:
            return False
        
        return True


@dataclass
class ChallengeScope:
    """Complete scope definition for a challenge."""
    challenge_id: str
    mode: str  # JEOPARDY, MACHINES, ATTACK_DEFENSE
    
    # Network rules
    network_policy: NetworkPolicy = NetworkPolicy.ALLOW_LIST
    allowed_networks: List[NetworkRule] = field(default_factory=list)
    denied_networks: List[NetworkRule] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    allowed_ports: List[int] = field(default_factory=list)
    allowed_protocols: List[str] = field(default_factory=lambda: ["tcp", "udp"])
    
    # Filesystem rules
    allowed_paths: List[FilesystemRule] = field(default_factory=list)
    denied_paths: List[FilesystemRule] = field(default_factory=list)
    
    # Resource limits
    max_cpu_percent: float = 100.0
    max_memory_mb: int = 2048
    max_processes: int = 50
    max_open_files: int = 1024
    max_runtime_seconds: int = 3600
    
    # Tool restrictions
    allowed_tools: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if scope has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "challenge_id": self.challenge_id,
            "mode": self.mode,
            "network_policy": self.network_policy.value,
            "allowed_networks": [
                {"cidr": r.cidr, "ports": r.ports, "protocols": r.protocols, "description": r.description}
                for r in self.allowed_networks
            ],
            "denied_networks": [
                {"cidr": r.cidr, "ports": r.ports, "protocols": r.protocols, "description": r.description}
                for r in self.denied_networks
            ],
            "allowed_domains": self.allowed_domains,
            "allowed_ports": self.allowed_ports,
            "allowed_protocols": self.allowed_protocols,
            "allowed_paths": [
                {"path": r.path, "read": r.read, "write": r.write, "description": r.description}
                for r in self.allowed_paths
            ],
            "denied_paths": [
                {"path": r.path, "read": r.read, "write": r.write, "description": r.description}
                for r in self.denied_paths
            ],
            "max_cpu_percent": self.max_cpu_percent,
            "max_memory_mb": self.max_memory_mb,
            "max_processes": self.max_processes,
            "max_open_files": self.max_open_files,
            "max_runtime_seconds": self.max_runtime_seconds,
            "allowed_tools": self.allowed_tools,
            "blocked_tools": self.blocked_tools,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChallengeScope":
        """Deserialize from dictionary."""
        scope = cls(
            challenge_id=data["challenge_id"],
            mode=data["mode"],
            network_policy=NetworkPolicy(data.get("network_policy", "allow_list")),
            allowed_domains=data.get("allowed_domains", []),
            allowed_ports=data.get("allowed_ports", []),
            allowed_protocols=data.get("allowed_protocols", ["tcp", "udp"]),
            max_cpu_percent=data.get("max_cpu_percent", 100.0),
            max_memory_mb=data.get("max_memory_mb", 2048),
            max_processes=data.get("max_processes", 50),
            max_open_files=data.get("max_open_files", 1024),
            max_runtime_seconds=data.get("max_runtime_seconds", 3600),
            allowed_tools=data.get("allowed_tools", []),
            blocked_tools=data.get("blocked_tools", []),
            metadata=data.get("metadata", {}),
        )
        
        if data.get("created_at"):
            scope.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("expires_at"):
            scope.expires_at = datetime.fromisoformat(data["expires_at"])
        
        for r in data.get("allowed_networks", []):
            scope.allowed_networks.append(NetworkRule(**r))
        for r in data.get("denied_networks", []):
            scope.denied_networks.append(NetworkRule(**r))
        for r in data.get("allowed_paths", []):
            scope.allowed_paths.append(FilesystemRule(**r))
        for r in data.get("denied_paths", []):
            scope.denied_paths.append(FilesystemRule(**r))
        
        return scope
    
    @classmethod
    def create_for_jeopardy(cls, challenge_id: str, target_ip: Optional[str] = None) -> "ChallengeScope":
        """Create scope for Jeopardy challenge."""
        scope = cls(
            challenge_id=challenge_id,
            mode="JEOPARDY",
            network_policy=NetworkPolicy.ALLOW_LIST,
            allowed_ports=[22, 80, 443, 8080, 8443, 3306, 5432, 6379, 27017],
            allowed_protocols=["tcp", "udp"],
            max_runtime_seconds=3600,
        )
        
        if target_ip:
            scope.allowed_networks.append(NetworkRule(
                cidr=target_ip + "/32" if "/" not in target_ip else target_ip,
                description="Challenge target"
            ))
            # Also allow the /24 for service discovery
            try:
                ip = ipaddress.ip_address(target_ip)
                if isinstance(ip, ipaddress.IPv4Address):
                    network = ipaddress.ip_network(f"{ip.exploded}/24", strict=False)
                    scope.allowed_networks.append(NetworkRule(
                        cidr=str(network),
                        description="Target subnet for service discovery"
                    ))
            except ValueError:
                pass  # Not an IP
        
        # Default filesystem rules
        scope.allowed_paths = [
            FilesystemRule(path=f"/challenges/{challenge_id}", read=True, write=False, description="Challenge files"),
            FilesystemRule(path=f"/workspace/{challenge_id}", read=True, write=True, description="Agent workspace"),
            FilesystemRule(path="/artifacts", read=True, write=True, description="Artifact storage"),
            FilesystemRule(path="/tmp", read=True, write=True, description="Temporary files"),
        ]
        
        return scope
    
    @classmethod
    def create_for_machines(cls, challenge_id: str, target_cidr: str = "10.10.10.0/24") -> "ChallengeScope":
        """Create scope for Machines challenge."""
        scope = cls(
            challenge_id=challenge_id,
            mode="MACHINES",
            network_policy=NetworkPolicy.ALLOW_LIST,
            allowed_ports=list(range(1, 65536)),  # All ports for full enumeration
            allowed_protocols=["tcp", "udp", "icmp"],
            max_runtime_seconds=7200,
        )
        
        scope.allowed_networks.append(NetworkRule(
            cidr=target_cidr,
            description="Target network range"
        ))
        
        scope.allowed_paths = [
            FilesystemRule(path=f"/challenges/{challenge_id}", read=True, write=False, description="Challenge files"),
            FilesystemRule(path=f"/workspace/{challenge_id}", read=True, write=True, description="Agent workspace"),
            FilesystemRule(path="/artifacts", read=True, write=True, description="Artifact storage"),
            FilesystemRule(path="/tmp", read=True, write=True, description="Temporary files"),
        ]
        
        return scope
    
    @classmethod
    def create_for_attack_defense(cls, challenge_id: str, team_network: str) -> "ChallengeScope":
        """Create scope for Attack/Defense challenge."""
        scope = cls(
            challenge_id=challenge_id,
            mode="ATTACK_DEFENSE",
            network_policy=NetworkPolicy.ALLOW_LIST,
            allowed_ports=list(range(1, 65536)),
            allowed_protocols=["tcp", "udp", "icmp"],
            max_runtime_seconds=86400,  # 24 hours
        )
        
        scope.allowed_networks.append(NetworkRule(
            cidr=team_network,
            description="Team network"
        ))
        
        scope.allowed_paths = [
            FilesystemRule(path=f"/challenges/{challenge_id}", read=True, write=False, description="Challenge files"),
            FilesystemRule(path=f"/workspace/{challenge_id}", read=True, write=True, description="Agent workspace"),
            FilesystemRule(path="/artifacts", read=True, write=True, description="Artifact storage"),
            FilesystemRule(path="/tmp", read=True, write=True, description="Temporary files"),
        ]
        
        return scope


class ScopeEngine:
    """Engine for validating actions against challenge scope."""
    
    def __init__(self):
        self._scopes: Dict[str, ChallengeScope] = {}
    
    def register_scope(self, scope: ChallengeScope):
        """Register a challenge scope."""
        self._scopes[scope.challenge_id] = scope
    
    def get_scope(self, challenge_id: str) -> Optional[ChallengeScope]:
        """Get scope for a challenge."""
        return self._scopes.get(challenge_id)
    
    def validate_network_access(
        self,
        challenge_id: str,
        target: str,
        port: Optional[int] = None,
        protocol: str = "tcp"
    ) -> tuple[bool, str]:
        """
        Validate network access.
        
        Returns:
            (allowed, reason)
        """
        scope = self.get_scope(challenge_id)
        if not scope:
            return False, f"No scope registered for challenge {challenge_id}"
        
        if scope.is_expired():
            return False, "Scope has expired"
        
        # Resolve target to IP if hostname
        target_ip = target
        try:
            ipaddress.ip_address(target)
        except ValueError:
            # It's a hostname - check domain allowlist
            if scope.allowed_domains:
                allowed = False
                for domain in scope.allowed_domains:
                    if self._match_domain(domain, target):
                        allowed = True
                        break
                if not allowed:
                    return False, f"Domain {target} not in allowed list"
            # For hostname resolution, we'd need DNS - for now allow if in allowed_domains
            target_ip = target  # Keep as hostname for rule matching
        
        # Check denied networks first
        for rule in scope.denied_networks:
            if rule.matches(target_ip, port, protocol):
                return False, f"Target {target}:{port} matches denied network rule {rule.cidr}"
        
        # Check allowed networks
        if scope.network_policy == NetworkPolicy.ALLOW_ALL:
            return True, "Allowed by ALLOW_ALL policy"
        
        if scope.network_policy == NetworkPolicy.DENY_LIST:
            # Allow by default unless denied
            return True, "Allowed by DENY_LIST policy (not explicitly denied)"
        
        # ALLOW_LIST - must match at least one allowed rule
        if not scope.allowed_networks:
            return False, "No allowed networks configured"
        
        allowed = False
        for rule in scope.allowed_networks:
            if rule.matches(target_ip, port, protocol):
                allowed = True
                break
        
        if not allowed:
            return False, f"Target {target}:{port}/{protocol} not in allowed networks"
        
        # Check port restrictions
        if port is not None and scope.allowed_ports and port not in scope.allowed_ports:
            return False, f"Port {port} not in allowed ports"
        
        # Check protocol restrictions
        if protocol.lower() not in [p.lower() for p in scope.allowed_protocols]:
            return False, f"Protocol {protocol} not allowed"
        
        return True, "Allowed by scope"
    
    def validate_filesystem_access(
        self,
        challenge_id: str,
        path: str,
        operation: str  # "read" or "write"
    ) -> tuple[bool, str]:
        """Validate filesystem access."""
        scope = self.get_scope(challenge_id)
        if not scope:
            return False, f"No scope registered for challenge {challenge_id}"
        
        if scope.is_expired():
            return False, "Scope has expired"
        
        # Check denied paths first
        for rule in scope.denied_paths:
            if rule.matches(path, operation):
                return False, f"Path {path} matches denied filesystem rule {rule.path}"
        
        # Check allowed paths
        if not scope.allowed_paths:
            return False, "No allowed paths configured"
        
        allowed = False
        for rule in scope.allowed_paths:
            if rule.matches(path, operation):
                allowed = True
                break
        
        if not allowed:
            return False, f"Path {path} ({operation}) not in allowed paths"
        
        return True, "Allowed by scope"
    
    def validate_tool_access(
        self,
        challenge_id: str,
        tool: str
    ) -> tuple[bool, str]:
        """Validate tool access."""
        scope = self.get_scope(challenge_id)
        if not scope:
            return False, f"No scope registered for challenge {challenge_id}"
        
        if tool in scope.blocked_tools:
            return False, f"Tool {tool} is blocked"
        
        if scope.allowed_tools and tool not in scope.allowed_tools:
            return False, f"Tool {tool} not in allowed tools list"
        
        return True, "Tool allowed by scope"
    
    def validate_resource_request(
        self,
        challenge_id: str,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[int] = None,
        processes: Optional[int] = None,
        open_files: Optional[int] = None,
        runtime_seconds: Optional[int] = None,
    ) -> tuple[bool, str]:
        """Validate resource request against scope limits."""
        scope = self.get_scope(challenge_id)
        if not scope:
            return False, f"No scope registered for challenge {challenge_id}"
        
        if cpu_percent is not None and cpu_percent > scope.max_cpu_percent:
            return False, f"CPU {cpu_percent}% exceeds limit {scope.max_cpu_percent}%"
        
        if memory_mb is not None and memory_mb > scope.max_memory_mb:
            return False, f"Memory {memory_mb}MB exceeds limit {scope.max_memory_mb}MB"
        
        if processes is not None and processes > scope.max_processes:
            return False, f"Processes {processes} exceeds limit {scope.max_processes}"
        
        if open_files is not None and open_files > scope.max_open_files:
            return False, f"Open files {open_files} exceeds limit {scope.max_open_files}"
        
        if runtime_seconds is not None and runtime_seconds > scope.max_runtime_seconds:
            return False, f"Runtime {runtime_seconds}s exceeds limit {scope.max_runtime_seconds}s"
        
        return True, "Resources within limits"
    
    def _match_domain(self, pattern: str, hostname: str) -> bool:
        """Match hostname against pattern."""
        if pattern == "*":
            return True
        if pattern.startswith("*."):
            domain = pattern[2:]
            return hostname == domain or hostname.endswith("." + domain)
        return pattern == hostname
    
    def get_scope_summary(self, challenge_id: str) -> Dict[str, Any]:
        """Get human-readable scope summary."""
        scope = self.get_scope(challenge_id)
        if not scope:
            return {"error": "No scope registered"}
        return scope.to_dict()


# Global scope engine
_scope_engine: Optional[ScopeEngine] = None


def get_scope_engine() -> ScopeEngine:
    """Get global scope engine."""
    global _scope_engine
    if _scope_engine is None:
        _scope_engine = ScopeEngine()
    return _scope_engine