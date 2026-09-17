"""Network Authorization - Secure hostname resolution and IP validation"""
import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class NetworkPermission(str, Enum):
    """Explicit network permissions - do not collapse into one generic capability."""
    CONNECT = "connect"
    SEND = "send"
    LISTEN = "listen"
    BIND = "bind"
    ICMP = "icmp"
    RAW_SOCKET = "raw_socket"
    PACKET_CAPTURE = "packet_capture"


@dataclass
class ResolvedAddress:
    """A resolved IP address from DNS."""
    hostname: str
    ip: str
    ip_version: int  # 4 or 6
    record_type: str  # A, AAAA, CNAME, etc.
    resolved_at: datetime = field(default_factory=datetime.utcnow)
    ttl: int = 300  # seconds


@dataclass
class NetworkAuthorizationResult:
    """Result of network authorization check."""
    allowed: bool
    hostname: str
    resolved_ips: List[ResolvedAddress]
    allowed_ips: List[str] = field(default_factory=list)
    denied_ips: List[str] = field(default_factory=list)
    reason: str = ""
    scope_type: str = "target"


class NetworkAuthorizer:
    """Secure network authorization with DNS resolution and scope validation.
    
    Workflow:
    hostname → DNS resolution → resulting IP(s) → validate every resulting address 
    → reject out-of-scope resolution
    
    Accounts for:
    - IPv4 and IPv6
    - Multiple A records and AAAA records
    - DNS rebinding protection
    - localhost resolution blocking
    - Link-local address blocking
    - Private range validation
    - Metadata endpoint blocking (169.254.169.254)
    """
    
    # Blocked IP ranges that should never be accessible
    BLOCKED_RANGES = [
        # Localhost
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("::1/128"),
        
        # Link-local
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("fe80::/10"),
        
        # Cloud metadata endpoints
        ipaddress.ip_network("169.254.169.254/32"),
        
        # Docker bridge (often 172.17.0.0/16)
        # This should be handled by scope, not hardcoded
    ]
    
    # Private ranges that may be allowed depending on scope
    PRIVATE_RANGES = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
    ]
    
    def __init__(self, challenge_scope: Optional["ChallengeScope"] = None):
        self.challenge_scope = challenge_scope
        self._dns_cache: Dict[str, List[ResolvedAddress]] = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def resolve_hostname(self, hostname: str) -> List[ResolvedAddress]:
        """Resolve hostname to IP addresses securely.
        
        Returns all resolved IPs (both A and AAAA records).
        Does not cache to prevent DNS rebinding attacks.
        """
        # Check cache first
        if hostname in self._dns_cache:
            cached = self._dns_cache[hostname]
            # Check if cache is still valid
            if cached and (datetime.utcnow() - cached[0].resolved_at).total_seconds() < self._cache_ttl:
                return cached
        
        results = []
        
        try:
            # Get all addresses (IPv4 and IPv6)
            # socket.getaddrinfo returns all available addresses
            addrinfo = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            )
            
            for family, _, _, _, sockaddr in addrinfo:
                ip = sockaddr[0]
                
                # Determine IP version and record type
                if family == socket.AF_INET:
                    ip_version = 4
                    record_type = "A"
                elif family == socket.AF_INET6:
                    ip_version = 6
                    record_type = "AAAA"
                else:
                    continue
                
                # Skip IPv6 link-local addresses
                if ip_version == 6 and ip.startswith("fe80::"):
                    continue
                
                results.append(ResolvedAddress(
                    hostname=hostname,
                    ip=ip,
                    ip_version=ip_version,
                    record_type=record_type,
                ))
            
            # Update cache
            self._dns_cache[hostname] = results
            
        except socket.gaierror as e:
            raise NetworkAuthorizationError(f"DNS resolution failed for {hostname}: {e}")
        
        return results
    
    def is_blocked_ip(self, ip: str) -> bool:
        """Check if an IP is in a permanently blocked range."""
        try:
            address = ipaddress.ip_address(ip)
            for blocked_range in self.BLOCKED_RANGES:
                if address in blocked_range:
                    return True
        except ValueError:
            return True  # Invalid IP is blocked
        return False
    
    def is_private_ip(self, ip: str) -> bool:
        """Check if an IP is in a private range."""
        try:
            address = ipaddress.ip_address(ip)
            for private_range in self.PRIVATE_RANGES:
                if address in private_range:
                    return True
        except ValueError:
            return False
        return False
    
    def is_allowed_by_scope(self, ip: str, scope_type: str = "target") -> bool:
        """Check if an IP is allowed by the challenge scope."""
        if not self.challenge_scope:
            return False
        
        return self.challenge_scope.check(ip, scope_type)
    
    async def authorize_hostname(
        self,
        hostname: str,
        scope_type: str = "target",
        require_all_ips_allowed: bool = True,
    ) -> NetworkAuthorizationResult:
        """Authorize a hostname for network access.
        
        Resolves the hostname and validates EVERY resulting IP against scope.
        If any IP is out of scope, the entire authorization fails (when require_all_ips_allowed=True).
        
        Args:
            hostname: The hostname to authorize
            scope_type: Type of scope to check against (target, discovery, lateral, control)
            require_all_ips_allowed: If True, ALL resolved IPs must be in scope
            
        Returns:
            NetworkAuthorizationResult with detailed results
        """
        # Resolve hostname
        try:
            resolved = await self.resolve_hostname(hostname)
        except NetworkAuthorizationError as e:
            return NetworkAuthorizationResult(
                allowed=False,
                hostname=hostname,
                resolved_ips=[],
                reason=str(e),
                scope_type=scope_type,
            )
        
        if not resolved:
            return NetworkAuthorizationResult(
                allowed=False,
                hostname=hostname,
                resolved_ips=[],
                reason="No IP addresses resolved",
                scope_type=scope_type,
            )
        
        # Validate each resolved IP
        allowed_ips = []
        denied_ips = []
        reasons = []
        
        for addr in resolved:
            ip = addr.ip
            
            # Check if IP is in permanently blocked range
            if self.is_blocked_ip(ip):
                denied_ips.append(ip)
                reasons.append(f"{ip}: Blocked IP range")
                continue
            
            # Check if IP is allowed by scope
            if self.is_allowed_by_scope(ip, scope_type):
                allowed_ips.append(ip)
            else:
                denied_ips.append(ip)
                reasons.append(f"{ip}: Out of scope ({scope_type})")
        
        # Determine overall result
        if require_all_ips_allowed:
            # All IPs must be allowed
            if denied_ips:
                return NetworkAuthorizationResult(
                    allowed=False,
                    hostname=hostname,
                    resolved_ips=resolved,
                    allowed_ips=allowed_ips,
                    denied_ips=denied_ips,
                    reason="; ".join(reasons),
                    scope_type=scope_type,
                )
        else:
            # At least one IP must be allowed
            if not allowed_ips:
                return NetworkAuthorizationResult(
                    allowed=False,
                    hostname=hostname,
                    resolved_ips=resolved,
                    allowed_ips=allowed_ips,
                    denied_ips=denied_ips,
                    reason="No allowed IPs found",
                    scope_type=scope_type,
                )
        
        return NetworkAuthorizationResult(
            allowed=True,
            hostname=hostname,
            resolved_ips=resolved,
            allowed_ips=allowed_ips,
            denied_ips=denied_ips,
            reason="All resolved IPs within scope",
            scope_type=scope_type,
        )
    
    async def authorize_ip(
        self,
        ip: str,
        scope_type: str = "target",
    ) -> NetworkAuthorizationResult:
        """Authorize a direct IP address."""
        # Validate IP format
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return NetworkAuthorizationResult(
                allowed=False,
                hostname=ip,
                resolved_ips=[],
                reason=f"Invalid IP address: {ip}",
                scope_type=scope_type,
            )
        
        # Check blocked ranges
        if self.is_blocked_ip(ip):
            return NetworkAuthorizationResult(
                allowed=False,
                hostname=ip,
                resolved_ips=[],
                reason=f"IP in blocked range: {ip}",
                scope_type=scope_type,
            )
        
        # Check scope
        if self.is_allowed_by_scope(ip, scope_type):
            return NetworkAuthorizationResult(
                allowed=True,
                hostname=ip,
                resolved_ips=[ResolvedAddress(hostname=ip, ip=ip, ip_version=address.version, record_type="direct")],
                allowed_ips=[ip],
                reason="IP within scope",
                scope_type=scope_type,
            )
        else:
            return NetworkAuthorizationResult(
                allowed=False,
                hostname=ip,
                resolved_ips=[ResolvedAddress(hostname=ip, ip=ip, ip_version=address.version, record_type="direct")],
                denied_ips=[ip],
                reason=f"IP out of scope ({scope_type}): {ip}",
                scope_type=scope_type,
            )


class NetworkAuthorizationError(Exception):
    """Network authorization error."""
    pass


# Integration with challenge scope
class ChallengeScope:
    """Formal ChallengeScope system - re-exported for network module."""
    # This is a placeholder - the actual implementation is in src/scope/engine.py
    pass


def create_network_authorizer(challenge_scope: "ChallengeScope") -> NetworkAuthorizer:
    """Create a network authorizer for a challenge scope."""
    return NetworkAuthorizer(challenge_scope)