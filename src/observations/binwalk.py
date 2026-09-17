"""Binwalk Embedded Artifact Observation Parser"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class EmbeddedFile:
    """Embedded file found by binwalk."""
    offset: int
    size: int
    name: str
    type: str  # "file", "certificate", "gzip", etc.
    entrophy: Optional[float] = None


@dataclass
class EmbeddedArtifactObservation:
    """Normalized observation from binwalk analysis."""
    source_tool: str = "binwalk"
    filename: str = ""
    total_files: int = 0
    embedded_files: List[EmbeddedFile] = field(default_factory=list)
    firmware_info: Optional[Dict[str, Any]] = None
    filesystem_type: Optional[str] = None
    detected_signatures: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_tool": self.source_tool,
            "filename": self.filename,
            "total_files": self.total_files,
            "embedded_files": [
                {
                    "offset": f.offset,
                    "size": f.size,
                    "name": f.name,
                    "type": f.type,
                    "entrophy": f.entrophy,
                }
                for f in self.embedded_files
            ],
            "firmware_info": self.firmware_info,
            "filesystem_type": self.filesystem_type,
            "detected_signatures": self.detected_signatures,
        }
    
    @classmethod
    def from_raw(cls, raw_text: str, filename: str = "") -> "EmbeddedArtifactObservation":
        """Parse binwalk scan output."""
        observation = cls()
        observation.filename = filename
        
        # Parse binwalk output format
        # Typical binwalk output lines look like:
        #   123  123        4          0% lzma        compressed data
        #   456  456        8          0% ext2          data (metadata, sa_family = 2)
        #   789        0            0% squashfs     filesystem, gzip compressed
        
        # Pattern: offset  size  compressed  type
        file_pattern = re.compile(
            r'^\s*(\d+)\s+(\d+)?\s+(\d+)?\s+(\S+?)\s+(.+)$',
            re.MULTILINE
        )
        
        firmware_patterns = [
            r'firmware',
            r'signature',
            r'certificate',
            r'key',
            r'password',
        ]
        
        filesystem_patterns = [
            r'squashfs',
            r'cramfs',
            r'jffs2',
            r'yaffs',
            r'ext2',
            r'ext3',
            r'ext4',
        ]
        
        for match in file_pattern.finditer(raw_text):
            offset = int(match.group(1))
            size = int(match.group(2)) if match.group(2) else 0
            compressed = int(match.group(3)) if match.group(3) else 0
            ftype = match.group(4).strip()
            description = match.group(5).strip() if match.group(5) else ""
            
            # Determine file type
            ftype_lower = ftype.lower()
            type_label = "file"
            
            for fs_pat in filesystem_patterns:
                if fs_pat in ftype_lower:
                    type_label = "filesystem"
                    observation.filesystem_type = fs_pat
                    break
            
            if "lzma" in ftype_lower or "gzip" in ftype_lower or "compressed" in ftype_lower.lower():
                type_label = "compressed"
            
            if "certificate" in ftype_lower:
                type_label = "certificate"
            
            if "key" in ftype_lower:
                type_label = "key"
            
            # Check for signatures
            sig_matches = re.findall(r'signature[^\n]*', description.lower())
            if sig_matches:
                observation.detected_signatures.extend(sig_matches)
            
            embedded = EmbeddedFile(
                offset=offset,
                size=size if size > 0 else None,
                name=description[:100] if description else f"file_at_{offset}",
                type=type_label,
            )
            observation.embedded_files.append(embedded)
        
        observation.total_files = len(observation.embedded_files)
        
        # Extract firmware info if available
        firmware_match = re.search(
            r'BIOS\s+offset:\s+(\S+)|manufacturer:\s+(\S+)|model:\s+(\S+)',
            raw_text,
            re.IGNORECASE
        )
        if firmware_match:
            observation.firmware_info = {}
            if firmware_match.group(1):
                observation.firmware_info[" bios_offset"] = firmware_match.group(1)
            if firmware_match.group(2):
                observation.firmware_info[" manufacturer"] = firmware_match.group(2)
            if firmware_match.group(3):
                observation.firmware_info[" model"] = firmware_match.group(3)
        
        return observation