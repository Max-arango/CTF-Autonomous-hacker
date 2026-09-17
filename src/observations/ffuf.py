"""FFUF Endpoint Observation Parser"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class Endpoint:
    """API endpoint discovered by ffuf."""
    method: str
    url: str
    status: int
    size: int = 0
    length: int = 0
    words: int = 0
    lines: int = 0
    response_time: float = 0.0


@dataclass
class EndpointObservation:
    """Normalized observation from ffuf scan."""
    source_tool: str = "ffuf"
    target: str = ""
    wordlist: str = ""
    endpoints: List[Endpoint] = field(default_factory=list)
    total_requests: int = 0
    successful_requests: int = 0
    status_distribution: Dict[int, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_tool": self.source_tool,
            "target": self.target,
            "wordlist": self.wordlist,
            "endpoints": [
                {
                    "method": e.method,
                    "url": e.url,
                    "status": e.status,
                    "size": e.size,
                    "length": e.length,
                    "words": e.words,
                    "lines": e.lines,
                    "response_time": e.response_time,
                }
                for e in self.endpoints
            ],
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "status_distribution": dict(self.status_distribution),
        }
    
    @classmethod
    def from_raw(cls, raw_text: str) -> "EndpointObservation":
        """Parse ffuf scan output."""
        observation = cls()
        
        # Parse the ffuf output format
        # Typical ffuf output lines look like:
        #         200      123       45       GET     /endpoint
        #         404        0        0       GET     /nonexistent
        
        endpoint_pattern = re.compile(
            r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(GET|POST|PUT|DELETE|HEAD|OPTIONS)\s+(\S+)',
            re.MULTILINE
        )
        
        targets = re.findall(r'-u\s+(\S+)', raw_text)
        if targets:
            observation.target = targets[0]
        
        # Wordlist flag
        wordlist_match = re.search(r'-w\s+(\S+)', raw_text)
        if wordlist_match:
            observation.wordlist = wordlist_match.group(1)
        
        for match in endpoint_pattern.finditer(raw_text):
            status = int(match.group(1))
            size = int(match.group(2)) if match.group(2) else 0
            words = int(match.group(3)) if match.group(3) else 0
            method = match.group(4)
            url = match.group(5)
            
            endpoint = Endpoint(
                method=method,
                url=url,
                status=status,
                size=size,
                words=words,
                lines=0,
                response_time=0.0,
            )
            observation.endpoints.append(endpoint)
        
        observation.total_requests = len(observation.endpoints)
        observation.successful_requests = sum(
            1 for e in observation.endpoints if 200 <= e.status < 300
        )
        
        # Build status distribution
        for e in observation.endpoints:
            observation.status_distribution[e.status] = (
                observation.status_distribution.get(e.status, 0) + 1
            )
        
        return observation