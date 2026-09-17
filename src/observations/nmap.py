"""Nmap Service Observation Parser"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class Service:
    """Service discovered by nmap."""
    port: int
    protocol: str
    name: str
    version: Optional[str] = None
    extrainfo: Optional[str] = None


@dataclass
class ServiceObservation:
    """Normalized observation from nmap scan."""
    source_tool: str = "nmap"
    scan_type: str = "full_tcp_scan"
    services: List[Service] = field(default_factory=list)
    operating_system: Optional[Dict[str, Any]] = None
    os_match_confidence: Optional[float] = None
    total_ports: int = 0
    open_ports: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_tool": self.source_tool,
            "scan_type": self.scan_type,
            "services": [
                {
                    "port": s.port,
                    "protocol": s.protocol,
                    "name": s.name,
                    "version": s.version,
                    "extrainfo": s.extrainfo,
                }
                for s in self.services
            ],
            "operating_system": {
                "name": self.operating_system.get("name") if self.operating_system else None,
                "family": self.operating_system.get("family") if self.operating_system else None,
                "accuracy": self.operating_system.get("accuracy") if self.operating_system else None,
            } if self.operating_system else None,
            "total_ports": self.total_ports,
            "open_ports": self.open_ports,
        }
    
    @classmethod
    def from_raw(cls, raw_text: str) -> "ServiceObservation":
        """Parse nmap scan output."""
        observation = cls()
        
        # Parse service lines
        # nmap typical output: PORT/protocol/sname/version
        service_pattern = re.compile(
            r'(\d+)/(tcp|udp)/(\S+)(?:\s+(\S+))?(?:\s+(\S+))?'
        )
        
        services = []
        for line in raw_text.split('\n'):
            match = service_pattern.search(line)
            if match:
                port = int(match.group(1))
                protocol = match.group(2)
                name = match.group(3)
                version = match.group(4) if match.group(4) else None
                extrainfo = match.group(5) if match.group(5) else None
                
                service = Service(
                    port=port,
                    protocol=protocol,
                    name=name,
                    version=version,
                    extrainfo=extrainfo,
                )
                services.append(service)
        
        observation.services = services
        observation.total_ports = len(services)
        observation.open_ports = sum(1 for s in services if s.name and s.name != "filtered")
        
        # Try to extract OS info
        os_match = re.search(r'OS details:\s*(.+?)(?:\n|$)', raw_text, re.DOTALL)
        if os_match:
            observation.operating_system = {
                "name": os_match.group(1).strip(),
            }
        
        # Try to extract OS match confidence
        confidence_match = re.search(
            r'OS matches:\s+(\d+)%', raw_text
        )
        if confidence_match:
            observation.os_match_confidence = float(confidence_match.group(1)) / 100.0
        
        return observation