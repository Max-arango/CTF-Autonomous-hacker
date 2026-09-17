"""Strings Observation Parser"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class StringObservation:
    """Normalized observation from strings extraction."""
    source_tool: str = "strings"
    filename: str = ""
    min_length: int = 4
    strings: List[str] = field(default_factory=list)
    string_count: int = 0
    interesting_strings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Analysis categories
    potential_secrets: List[str] = field(default_factory=list)
    potential_urls: List[str] = field(default_factory=list)
    potential_paths: List[str] = field(default_factory=list)
    potential_ips: List[str] = field(default_factory=list)
    potential_flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_tool": self.source_tool,
            "filename": self.filename,
            "min_length": self.min_length,
            "string_count": self.string_count,
            "strings": self.strings,
            "interesting_strings": self.interesting_strings,
            "potential_secrets": self.potential_secrets,
            "potential_urls": self.potential_urls,
            "potential_paths": self.potential_paths,
            "potential_ips": self.potential_ips,
            "potential_flags": self.potential_flags,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_raw(cls, raw_text: str, filename: str = "", min_length: int = 4) -> "StringObservation":
        """Parse strings output."""
        observation = cls()
        observation.filename = filename
        observation.min_length = min_length
        
        # Split by newlines and filter by minimum length
        all_strings = [s for s in raw_text.split('\n') if s.strip() and len(s.strip()) >= min_length]
        observation.strings = all_strings
        observation.string_count = len(all_strings)
        
        # Analyze strings for patterns
        url_pattern = re.compile(
            r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
        )
        ip_pattern = re.compile(
            r'(?:(?:25[0-5]|2[0-1]?[0-1]?[0-1])\.){3}(?:25[0-5]|2[0-1]?[0-1]?[0-1])'
        )
        path_pattern = re.compile(
            r'(/[^\s<>"]*|[A-Za-z]:\\[^<>"]*)'
        )
        secret_pattern = re.compile(
            r'(?:api[_-]?key|secret|password|token|auth[_-]?key)[=:]\s*["\']?([^\s"\']+)["\']?'
        )
        flag_pattern = re.compile(
            r'flag\{[^}]+\}'
        )
        
        for s in all_strings:
            # Check for URLs
            urls = url_pattern.findall(s)
            observation.potential_urls.extend(urls)
            
            # Check for IPs
            ips = ip_pattern.findall(s)
            observation.potential_ips.extend(ips)
            
            # Check for paths
            paths = path_pattern.findall(s)
            observation.potential_paths.extend(paths)
            
            # Check for secrets
            secrets = secret_pattern.findall(s)
            observation.potential_secrets.extend(secrets)
            
            # Check for flags
            flags = flag_pattern.findall(s)
            observation.potential_flags.extend(flags)
        
        # Deduplicate interesting strings
        observation.interesting_strings = list(set(
            observation.potential_urls + 
            observation.potential_ips + 
            observation.potential_paths + 
            observation.potential_secrets + 
            observation.potential_flags
        ))
        
        return observation