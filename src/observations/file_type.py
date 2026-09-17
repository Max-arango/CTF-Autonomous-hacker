"""File Type Observation Parser"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import magic


@dataclass
class FileTypeObservation:
    """Normalized observation from file type detection."""
    source_tool: str = "file"
    filename: str = ""
    detected_mime: str = ""
    detected_extension: str = ""
    confidence: float = 0.0
    bytes_analyzed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_tool": self.source_tool,
            "filename": self.filename,
            "detected_mime": self.detected_mime,
            "detected_extension": self.detected_extension,
            "confidence": self.confidence,
            "bytes_analyzed": self.bytes_analyzed,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_path(cls, file_path: str) -> "FileTypeObservation":
        """Detect file type from path."""
        observation = cls()
        observation.filename = file_path
        
        try:
            # Read file content for magic byte detection
            with open(file_path, "rb") as f:
                content = f.read(8192)  # Read first 8KB
                observation.bytes_analyzed = len(content)
                
                if content:
                    detected = magic.from_buffer(content, mime=True)
                    observation.detected_mime = detected
                    
                    # Extract extension from MIME type
                    mime_to_ext = {
                        "text/plain": ".txt",
                        "text/html": ".html",
                        "image/png": ".png",
                        "image/jpeg": ".jpg",
                        "image/gif": ".gif",
                        "application/pdf": ".pdf",
                        "application/zip": ".zip",
                        "application/gzip": ".gz",
                        "application/x-tar": ".tar",
                        "application/x-7z": ".7z",
                        "application/x-rar": ".rar",
                        "text/javascript": ".js",
                        "text/css": ".css",
                        "application/json": ".json",
                        "application/xml": ".xml",
                        "application/msword": ".doc",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                        "application/vnd.ms-excel": ".xls",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
                        "application/": ".bin",
                    }
                    
                    # Try to get extension
                    base_mime = detected.split("/")[0] if "/" in detected else detected
                    observation.detected_extension = mime_to_ext.get(detected, "")
                    
                    # Calculate confidence based on magic cookie strength
                    # Magic library returns confidence as part of the description
                    obs = magic.from_buffer(content)
                    if "[" in obs and "%" in obs:
                        try:
                            conf_str = obs.split("%")[1].split("]")[0]
                            observation.confidence = float(conf_str) / 100.0
                        except (ValueError, IndexError):
                            observation.confidence = 0.9
                    else:
                        observation.confidence = 0.9
                        
        except Exception:
            observation.detected_mime = "application/octet-stream"
            observation.detected_extension = ".bin"
            observation.confidence = 0.1
        
        return observation