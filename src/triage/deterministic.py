"""Deterministic Challenge Triage - File-based classification without LLM"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import mimetypes
import re
from enum import Enum


# Optional import for file type detection
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


# Lightweight models to avoid circular dependencies
class ChallengeCategory(str, Enum):
    WEB = "web"
    CRYPTO = "crypto"
    PWN = "pwn"
    REVERSE = "reverse"
    FORENSICS = "forensics"
    OSINT = "osint"
    STEGO = "stego"
    MOBILE = "mobile"
    MALWARE = "malware"
    CLOUD = "cloud"
    NETWORK = "network"
    SUPPLY_CHAIN = "supply_chain"
    AD = "ad"
    WEB3 = "web3"
    AI_SECURITY = "ai_security"
    SIDECHANNEL = "sidechannel"
    FIRMWARE = "firmware"
    SOCIAL = "social"
    PROGRAMMING = "programming"
    META = "meta"
    UNKNOWN = "unknown"


class ChallengeType(str, Enum):
    JEOPARDY = "jeopardy"
    MACHINE = "machine"
    ATTACK_DEFENSE = "attack_defense"


@dataclass
class Challenge:
    id: str = ""
    name: str = ""
    description: str = ""
    category: List[ChallengeCategory] = field(default_factory=list)
    challenge_type: ChallengeType = ChallengeType.JEOPARDY
    files: List[str] = field(default_factory=list)
    target_info: Dict[str, Any] = field(default_factory=dict)
    credentials: Dict[str, str] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    flag_format: str = "flag{.*}"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackSurface:
    services: List[Dict[str, Any]] = field(default_factory=list)
    web_endpoints: List[str] = field(default_factory=list)
    open_ports: List[int] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    potential_vulnerabilities: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)


@dataclass
class DeterministicTriageResult:
    categories: List[ChallengeCategory]
    confidence: float
    reasoning: str
    suggested_agents: List[str]
    attack_surface: AttackSurface
    file_types: List[str] = field(default_factory=list)
    detected_technologies: List[str] = field(default_factory=list)


class DeterministicTriage:
    """Classify challenges using deterministic file analysis."""
    
    def __init__(self):
        # File extension -> category mapping
        self.extension_categories = {
            # Web
            ".html": ChallengeCategory.WEB,
            ".htm": ChallengeCategory.WEB,
            ".js": ChallengeCategory.WEB,
            ".ts": ChallengeCategory.WEB,
            ".jsx": ChallengeCategory.WEB,
            ".tsx": ChallengeCategory.WEB,
            ".php": ChallengeCategory.WEB,
            ".asp": ChallengeCategory.WEB,
            ".aspx": ChallengeCategory.WEB,
            ".jsp": ChallengeCategory.WEB,
            ".css": ChallengeCategory.WEB,
            ".scss": ChallengeCategory.WEB,
            ".json": ChallengeCategory.WEB,
            ".xml": ChallengeCategory.WEB,
            ".yaml": ChallengeCategory.WEB,
            ".yml": ChallengeCategory.WEB,
            
            # Crypto
            ".pem": ChallengeCategory.CRYPTO,
            ".key": ChallengeCategory.CRYPTO,
            ".crt": ChallengeCategory.CRYPTO,
            ".csr": ChallengeCategory.CRYPTO,
            ".der": ChallengeCategory.CRYPTO,
            ".p12": ChallengeCategory.CRYPTO,
            ".pfx": ChallengeCategory.CRYPTO,
            ".gpg": ChallengeCategory.CRYPTO,
            ".asc": ChallengeCategory.CRYPTO,
            ".sig": ChallengeCategory.CRYPTO,
            
            # Pwn/Reverse
            ".elf": ChallengeCategory.PWN,
            ".bin": ChallengeCategory.PWN,
            ".exe": ChallengeCategory.PWN,
            ".dll": ChallengeCategory.PWN,
            ".so": ChallengeCategory.PWN,
            ".o": ChallengeCategory.PWN,
            ".out": ChallengeCategory.PWN,
            ".c": ChallengeCategory.REVERSE,
            ".cpp": ChallengeCategory.REVERSE,
            ".cc": ChallengeCategory.REVERSE,
            ".h": ChallengeCategory.REVERSE,
            ".hpp": ChallengeCategory.REVERSE,
            ".asm": ChallengeCategory.REVERSE,
            ".s": ChallengeCategory.REVERSE,
            ".pyc": ChallengeCategory.REVERSE,
            ".pyo": ChallengeCategory.REVERSE,
            
            # Forensics
            ".pcap": ChallengeCategory.FORENSICS,
            ".pcapng": ChallengeCategory.FORENSICS,
            ".cap": ChallengeCategory.FORENSICS,
            ".raw": ChallengeCategory.FORENSICS,
            ".dd": ChallengeCategory.FORENSICS,
            ".img": ChallengeCategory.FORENSICS,
            ".iso": ChallengeCategory.FORENSICS,
            ".vmdk": ChallengeCategory.FORENSICS,
            ".vhd": ChallengeCategory.FORENSICS,
            ".qcow2": ChallengeCategory.FORENSICS,
            ".mem": ChallengeCategory.FORENSICS,
            ".dmp": ChallengeCategory.FORENSICS,
            ".log": ChallengeCategory.FORENSICS,
            ".evtx": ChallengeCategory.FORENSICS,
            
            # Mobile
            ".apk": ChallengeCategory.MOBILE,
            ".ipa": ChallengeCategory.MOBILE,
            ".dex": ChallengeCategory.MOBILE,
            ".aar": ChallengeCategory.MOBILE,
            
            # Stego
            ".png": ChallengeCategory.STEGO,
            ".jpg": ChallengeCategory.STEGO,
            ".jpeg": ChallengeCategory.STEGO,
            ".bmp": ChallengeCategory.STEGO,
            ".gif": ChallengeCategory.STEGO,
            ".tiff": ChallengeCategory.STEGO,
            ".wav": ChallengeCategory.STEGO,
            ".mp3": ChallengeCategory.STEGO,
            ".mp4": ChallengeCategory.STEGO,
            ".avi": ChallengeCategory.STEGO,
            
            # Firmware
            ".fw": ChallengeCategory.FIRMWARE,
            ".bin": ChallengeCategory.FIRMWARE,
            ".img": ChallengeCategory.FIRMWARE,
            
            # Archives
            ".zip": ChallengeCategory.PROGRAMMING,
            ".tar": ChallengeCategory.PROGRAMMING,
            ".gz": ChallengeCategory.PROGRAMMING,
            ".tgz": ChallengeCategory.PROGRAMMING,
            ".rar": ChallengeCategory.PROGRAMMING,
            ".7z": ChallengeCategory.PROGRAMMING,
        }
        
        # MIME type -> category mapping
        self.mime_categories = {
            "text/html": ChallengeCategory.WEB,
            "application/javascript": ChallengeCategory.WEB,
            "text/css": ChallengeCategory.WEB,
            "application/x-httpd-php": ChallengeCategory.WEB,
            "application/x-executable": ChallengeCategory.PWN,
            "application/x-sharedlib": ChallengeCategory.PWN,
            "application/x-object": ChallengeCategory.REVERSE,
            "application/x-dosexec": ChallengeCategory.PWN,
            "application/vnd.android.package-archive": ChallengeCategory.MOBILE,
            "application/x-ios-app": ChallengeCategory.MOBILE,
            "application/x-mach-binary": ChallengeCategory.REVERSE,
            "application/vnd.tcpdump.pcap": ChallengeCategory.FORENSICS,
            "application/vnd.tcpdump.pcapng": ChallengeCategory.FORENSICS,
            "image/png": ChallengeCategory.STEGO,
            "image/jpeg": ChallengeCategory.STEGO,
            "image/gif": ChallengeCategory.STEGO,
            "audio/x-wav": ChallengeCategory.STEGO,
            "audio/mpeg": ChallengeCategory.STEGO,
            "video/mp4": ChallengeCategory.STEGO,
            "application/zip": ChallengeCategory.PROGRAMMING,
            "application/x-tar": ChallengeCategory.PROGRAMMING,
            "application/gzip": ChallengeCategory.PROGRAMMING,
            "application/x-rar-compressed": ChallengeCategory.PROGRAMMING,
            "application/x-7z-compressed": ChallengeCategory.PROGRAMMING,
        }
        
        # Content patterns for category detection
        self.content_patterns = {
            ChallengeCategory.WEB: [
                r"<html", r"<script", r"<form", r"SELECT\s+.*\s+FROM", r"UNION\s+SELECT",
                r"INSERT\s+INTO", r"UPDATE\s+.*\s+SET", r"DELETE\s+FROM",
                r"localhost", r"127\.0\.0\.1", r"admin", r"password", r"login",
                r"csrf", r"xss", r"sqli", r"injection"
            ],
            ChallengeCategory.CRYPTO: [
                r"BEGIN\s+(RSA|PUBLIC|PRIVATE)\s+KEY", r"BEGIN\s+CERTIFICATE",
                r"ssh-rsa", r"ssh-ed25519", r"ecdsa-sha2-nistp",
                r"[A-Za-z0-9+/]{40,}={0,2}",
                r"[0-9a-fA-F]{64}",
                r"[0-9a-fA-F]{40}",
                r"[0-9a-fA-F]{32}",
            ],
            ChallengeCategory.PWN: [
                r"gets\(|strcpy\(|sprintf\(|strcat\(",
                r"system\(|exec\(|popen\(",
                r"buffer|overflow|overflow",
                r"ROP|gadget|shellcode",
                r"stack|heap|canary|ASLR|NX|PIE",
            ],
            ChallengeCategory.REVERSE: [
                r"Ghidra|IDA|radare2|r2|angr",
                r"decompil|disassembl|control.flow",
                r"function|procedure|subroutine",
                r"xref|cross.reference",
            ],
            ChallengeCategory.FORENSICS: [
                r"forensic|evidence|artifact",
                r"timeline|superblock|inode",
                r"MFT|NTFS|FAT|ext[234]",
                r"volatility|rekall|autopsy",
            ],
            ChallengeCategory.CRYPTO: [
                r"encrypt|decrypt|cipher|hash",
                r"AES|RSA|ECC|SHA|MD5",
                r"key|iv|nonce|salt",
            ],
        }
        
        # Technology detection patterns
        self.tech_patterns = {
            "WordPress": [r"wp-content", r"wp-includes", r"xmlrpc\.php", r"wp-admin"],
            "Drupal": [r"drupal", r"sites/default/files"],
            "Joomla": [r"joomla", r"components/com_"],
            "React": [r"react\.js", r"__REACT_DEVTOOLS", r"data-reactroot"],
            "Vue": [r"vue\.js", r"__VUE_DEVTOOLS", r"v-if", r"v-for"],
            "Angular": [r"angular\.js", r"ng-app", r"ng-controller"],
            "jQuery": [r"jquery", r"\$\(", r"jQuery"],
            "Apache": [r"Apache/", r"mod_"],
            "Nginx": [r"nginx", r"X-Powered-By.*nginx"],
            "IIS": [r"IIS/", r"X-Powered-By.*ASP\.NET"],
            "PHP": [r"X-Powered-By.*PHP", r"\.php"],
            "ASP.NET": [r"ASP\.NET", r"__VIEWSTATE", r"\.aspx"],
            "Node.js": [r"express", r"X-Powered-By.*Express", r"next\.js"],
            "Python": [r"Python/", r"Django", r"Flask", r"FastAPI"],
            "Java": [r"Java/", r"Tomcat", r"Spring", r"JSESSIONID"],
            "Go": [r"Go-http-client", r"golang"],
            "Database": [r"MySQL", r"PostgreSQL", r"MongoDB", r"Redis", r"SQLite"],
        }
    
    async def classify(self, challenge: Challenge) -> DeterministicTriageResult:
        """Classify challenge using deterministic analysis."""
        categories = set()
        file_types = []
        detected_technologies = []
        attack_surface = AttackSurface()
        
        # Analyze each file
        for file_id in challenge.files:
            file_type = self._analyze_file(file_id)
            if file_type:
                file_types.append(file_type)
        
        # Analyze from extension
        for file_id in challenge.files:
            ext = Path(file_id).suffix.lower()
            if ext in self.extension_categories:
                categories.add(self.extension_categories[ext])
        
        # Analyze from description
        desc_categories = self._analyze_text(challenge.description)
        categories.update(desc_categories)
        
        # If no categories found, check target info
        if not categories:
            target_info = challenge.target_info
            if target_info.get("url") or target_info.get("web"):
                categories.add(ChallengeCategory.WEB)
            if target_info.get("ports"):
                categories.add(ChallengeCategory.NETWORK)
            if target_info.get("binary"):
                categories.add(ChallengeCategory.PWN)
            if target_info.get("crypto"):
                categories.add(ChallengeCategory.CRYPTO)
        
        # Default to web if nothing found
        if not categories:
            categories.add(ChallengeCategory.WEB)
        
        # Determine suggested agents
        suggested_agents = self._get_suggested_agents(categories)
        
        # Calculate confidence
        confidence = self._calculate_confidence(categories, challenge)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(categories, challenge, file_types)
        
        return DeterministicTriageResult(
            categories=list(categories),
            confidence=confidence,
            reasoning=reasoning,
            suggested_agents=suggested_agents,
            attack_surface=attack_surface,
            file_types=file_types,
            detected_technologies=detected_technologies,
        )
    
    def _analyze_file(self, file_id: str) -> Optional[str]:
        """Analyze file by ID - would fetch and analyze actual file."""
        return None
    
    def _analyze_text(self, text: str) -> Set[ChallengeCategory]:
        """Analyze text for category indicators."""
        categories = set()
        text_lower = text.lower()
        
        for category, patterns in self.content_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    categories.add(category)
                    break
        
        return categories
    
    def _get_suggested_agents(self, categories: Set[ChallengeCategory]) -> List[str]:
        """Map categories to suggested agent roles."""
        agent_map = {
            ChallengeCategory.WEB: ["web"],
            ChallengeCategory.CRYPTO: ["crypto"],
            ChallengeCategory.PWN: ["pwn"],
            ChallengeCategory.REVERSE: ["reverse"],
            ChallengeCategory.FORENSICS: ["forensics"],
            ChallengeCategory.OSINT: ["osint"],
            ChallengeCategory.STEGO: ["stego"],
            ChallengeCategory.MOBILE: ["mobile"],
            ChallengeCategory.MALWARE: ["malware"],
            ChallengeCategory.CLOUD: ["cloud"],
            ChallengeCategory.NETWORK: ["network"],
            ChallengeCategory.SUPPLY_CHAIN: ["supply_chain"],
            ChallengeCategory.AD: ["ad"],
            ChallengeCategory.WEB3: ["web3"],
            ChallengeCategory.AI_SECURITY: ["ai_security"],
            ChallengeCategory.SIDECHANNEL: ["sidechannel"],
            ChallengeCategory.FIRMWARE: ["firmware"],
            ChallengeCategory.SOCIAL: ["social"],
            ChallengeCategory.PROGRAMMING: ["programming"],
            ChallengeCategory.META: ["meta"],
        }
        
        agents = []
        for cat in categories:
            agents.extend(agent_map.get(cat, []))
        
        # Deduplicate while preserving order
        seen = set()
        unique_agents = []
        for agent in agents:
            if agent not in seen:
                seen.add(agent)
                unique_agents.append(agent)
        
        return unique_agents
    
    def _calculate_confidence(self, categories: Set[ChallengeCategory], challenge: Challenge) -> float:
        """Calculate confidence score."""
        confidence = 0.5
        confidence += min(len(categories) * 0.1, 0.3)
        if challenge.files:
            confidence += 0.1
        if challenge.target_info:
            confidence += 0.1
        if challenge.description and len(challenge.description) > 50:
            confidence += 0.1
        return min(confidence, 0.95)
    
    def _generate_reasoning(
        self,
        categories: Set[ChallengeCategory],
        challenge: Challenge,
        file_types: List[str]
    ) -> str:
        """Generate human-readable reasoning."""
        parts = []
        if categories:
            cat_names = [c.value for c in categories]
            parts.append(f"Detected categories: {', '.join(cat_names)}")
        if challenge.files:
            parts.append(f"Challenge includes {len(challenge.files)} files")
        if challenge.target_info:
            target_desc = []
            if challenge.target_info.get("url"):
                target_desc.append("web target")
            if challenge.target_info.get("ip"):
                target_desc.append(f"IP: {challenge.target_info['ip']}")
            if challenge.target_info.get("ports"):
                target_desc.append(f"ports: {challenge.target_info['ports']}")
            if target_desc:
                parts.append(f"Target info: {', '.join(target_desc)}")
        if file_types:
            parts.append(f"File types: {', '.join(file_types)}")
        return "; ".join(parts) if parts else "Limited information available for classification"


# Global deterministic triage
_deterministic_triage: Optional[DeterministicTriage] = None


def get_deterministic_triage() -> DeterministicTriage:
    """Get global deterministic triage instance."""
    global _deterministic_triage
    if _deterministic_triage is None:
        _deterministic_triage = DeterministicTriage()
    return _deterministic_triage