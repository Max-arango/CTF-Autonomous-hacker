"""Tool Schema Validation - Strict argument schemas for all tools"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import re


class SchemaType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolArgumentSchema:
    """Schema for a single tool argument."""
    name: str
    type: SchemaType
    required: bool = True
    description: str = ""
    default: Any = None
    pattern: Optional[str] = None  # regex for strings
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    enum: Optional[List[Any]] = None
    items: Optional["ToolArgumentSchema"] = None  # for arrays
    properties: Optional[Dict[str, "ToolArgumentSchema"]] = None  # for objects


@dataclass
class ToolSchema:
    """Complete schema for a tool."""
    name: str
    description: str
    arguments: List[ToolArgumentSchema] = field(default_factory=list)
    returns: Optional[ToolArgumentSchema] = None
    examples: List[Dict[str, Any]] = field(default_factory=list)
    risk_level: str = "low"
    requires_approval: bool = False
    timeout_default: int = 60
    timeout_max: int = 300


class ToolSchemaRegistry:
    """Registry of tool schemas with validation."""
    
    def __init__(self):
        self._schemas: Dict[str, ToolSchema] = {}
        self._register_default_schemas()
    
    def _register_default_schemas(self):
        """Register default tool schemas."""
        
        # Network tools
        self.register(ToolSchema(
            name="nmap",
            description="Network port scanner",
            risk_level="medium",
            requires_approval=False,
            timeout_default=120,
            timeout_max=300,
            arguments=[
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Target IP, CIDR, or hostname",
                    pattern=r"^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$|^[a-zA-Z0-9.-]+$"
                ),
                ToolArgumentSchema(
                    name="ports", type=SchemaType.STRING, required=False,
                    description="Port range (e.g., '1-1000', '80,443,8080')",
                    pattern=r"^([0-9]{1,5}(-[0-9]{1,5})?)(,[0-9]{1,5}(-[0-9]{1,5})?)*$"
                ),
                ToolArgumentSchema(
                    name="scan_type", type=SchemaType.STRING, required=False,
                    description="Scan type",
                    default="-sS",
                    enum=["-sS", "-sT", "-sU", "-sA", "-sW", "-sM"]
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional nmap arguments",
                    default=""
                ),
                ToolArgumentSchema(
                    name="timeout", type=SchemaType.INTEGER, required=False,
                    description="Timeout in seconds",
                    default=120, min_value=10, max_value=300
                ),
            ],
            examples=[
                {"target": "10.10.10.5", "ports": "80,443", "scan_type": "-sS"},
                {"target": "10.10.10.0/24", "ports": "1-1000"},
            ]
        ))
        
        self.register(ToolSchema(
            name="masscan",
            description="Fast port scanner",
            risk_level="high",
            requires_approval=True,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Target CIDR",
                    pattern=r"^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$"
                ),
                ToolArgumentSchema(
                    name="ports", type=SchemaType.STRING, required=True,
                    description="Port range",
                    pattern=r"^[0-9]{1,5}(-[0-9]{1,5})?$"
                ),
                ToolArgumentSchema(
                    name="rate", type=SchemaType.INTEGER, required=False,
                    description="Packets per second",
                    default=1000, min_value=100, max_value=100000
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="rustscan",
            description="Fast port scanner (Rust)",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Target IP or CIDR"
                ),
                ToolArgumentSchema(
                    name="ports", type=SchemaType.STRING, required=False,
                    description="Port range"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        # Web tools
        self.register(ToolSchema(
            name="curl",
            description="HTTP client",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="url", type=SchemaType.STRING, required=True,
                    description="Target URL",
                    pattern=r"^https?://.+"
                ),
                ToolArgumentSchema(
                    name="method", type=SchemaType.STRING, required=False,
                    description="HTTP method",
                    default="GET",
                    enum=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]
                ),
                ToolArgumentSchema(
                    name="headers", type=SchemaType.OBJECT, required=False,
                    description="HTTP headers",
                    properties={
                        k: ToolArgumentSchema(name=k, type=SchemaType.STRING) for k in ["User-Agent", "Authorization", "Cookie", "Content-Type"]
                    }
                ),
                ToolArgumentSchema(
                    name="data", type=SchemaType.STRING, required=False,
                    description="Request body"
                ),
                ToolArgumentSchema(
                    name="timeout", type=SchemaType.INTEGER, required=False,
                    description="Timeout in seconds",
                    default=30, min_value=5, max_value=60
                ),
            ],
            examples=[
                {"url": "http://10.10.10.5/", "method": "GET"},
                {"url": "http://10.10.10.5/login", "method": "POST", "data": "user=admin&pass=admin"},
            ]
        ))
        
        self.register(ToolSchema(
            name="ffuf",
            description="Web fuzzer",
            risk_level="medium",
            requires_approval=False,
            timeout_default=120,
            timeout_max=300,
            arguments=[
                ToolArgumentSchema(
                    name="url", type=SchemaType.STRING, required=True,
                    description="Target URL with FUZZ keyword",
                    pattern=r".*FUZZ.*"
                ),
                ToolArgumentSchema(
                    name="wordlist", type=SchemaType.STRING, required=True,
                    description="Path to wordlist",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional ffuf arguments",
                    default="-mc 200,204,301,302,307,401,403 -t 50"
                ),
            ],
            examples=[
                {"url": "http://10.10.10.5/FUZZ", "wordlist": "/usr/share/wordlists/dirb/common.txt"},
            ]
        ))
        
        self.register(ToolSchema(
            name="httpx",
            description="HTTP probe",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="targets", type=SchemaType.ARRAY, required=True,
                    description="List of targets",
                    items=ToolArgumentSchema(name="target", type=SchemaType.STRING)
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional httpx arguments",
                    default="-title -tech-detect -status-code -json"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="nuclei",
            description="Vulnerability scanner",
            risk_level="medium",
            requires_approval=False,
            timeout_default=120,
            timeout_max=300,
            arguments=[
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Target URL or IP"
                ),
                ToolArgumentSchema(
                    name="templates", type=SchemaType.STRING, required=False,
                    description="Template path or tag"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional nuclei arguments",
                    default="-json -silent"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="sqlmap",
            description="SQL injection testing",
            risk_level="high",
            requires_approval=True,
            timeout_default=300,
            timeout_max=600,
            arguments=[
                ToolArgumentSchema(
                    name="url", type=SchemaType.STRING, required=True,
                    description="Target URL with injection point",
                    pattern=r"^https?://.+"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional sqlmap arguments",
                    default="--batch --random-agent --level=2 --risk=2"
                ),
            ]
        ))
        
        # Pwn/Reverse tools
        self.register(ToolSchema(
            name="gdb",
            description="GDB debugger",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="binary", type=SchemaType.STRING, required=True,
                    description="Binary path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="commands", type=SchemaType.ARRAY, required=False,
                    description="GDB commands",
                    items=ToolArgumentSchema(name="cmd", type=SchemaType.STRING),
                    default=["info functions", "info registers"]
                ),
                ToolArgumentSchema(
                    name="script", type=SchemaType.STRING, required=False,
                    description="GDB script path"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="pwntools",
            description="Pwntools script execution",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="script", type=SchemaType.STRING, required=True,
                    description="Python script using pwntools"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.ARRAY, required=False,
                    description="Script arguments",
                    items=ToolArgumentSchema(name="arg", type=SchemaType.STRING)
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="checksec",
            description="Check binary protections",
            risk_level="low",
            requires_approval=False,
            timeout_default=10,
            timeout_max=30,
            arguments=[
                ToolArgumentSchema(
                    name="binary", type=SchemaType.STRING, required=True,
                    description="Binary path",
                    pattern=r"^/.*"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="ROPgadget",
            description="Find ROP gadgets",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="binary", type=SchemaType.STRING, required=True,
                    description="Binary path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="ropper",
            description="ROP chain builder",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="binary", type=SchemaType.STRING, required=True,
                    description="Binary path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default="--search 'pop rdi'"
                ),
            ]
        ))
        
        # Reverse engineering
        self.register(ToolSchema(
            name="ghidra",
            description="Ghidra headless analysis",
            risk_level="low",
            requires_approval=False,
            timeout_default=300,
            timeout_max=600,
            arguments=[
                ToolArgumentSchema(
                    name="binary", type=SchemaType.STRING, required=True,
                    description="Binary path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="script", type=SchemaType.STRING, required=False,
                    description="Ghidra script path"
                ),
                ToolArgumentSchema(
                    name="output_dir", type=SchemaType.STRING, required=False,
                    description="Output directory",
                    default="/tmp/ghidra_out"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="radare2",
            description="Radare2 analysis",
            risk_level="low",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="binary", type=SchemaType.STRING, required=True,
                    description="Binary path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="commands", type=SchemaType.ARRAY, required=False,
                    description="Radare2 commands",
                    items=ToolArgumentSchema(name="cmd", type=SchemaType.STRING),
                    default=["aaa", "afl", "pdf @ main"]
                ),
            ]
        ))
        
        # Crypto tools
        self.register(ToolSchema(
            name="hashcat",
            description="Hash cracking",
            risk_level="medium",
            requires_approval=False,
            timeout_default=300,
            timeout_max=3600,
            arguments=[
                ToolArgumentSchema(
                    name="hash_file", type=SchemaType.STRING, required=True,
                    description="Hash file path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="mode", type=SchemaType.STRING, required=True,
                    description="Hash mode (e.g., '0' for MD5)"
                ),
                ToolArgumentSchema(
                    name="wordlist", type=SchemaType.STRING, required=True,
                    description="Wordlist path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="john",
            description="John the Ripper",
            risk_level="medium",
            requires_approval=False,
            timeout_default=300,
            timeout_max=3600,
            arguments=[
                ToolArgumentSchema(
                    name="hash_file", type=SchemaType.STRING, required=True,
                    description="Hash file path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="wordlist", type=SchemaType.STRING, required=False,
                    description="Wordlist path",
                    default="/usr/share/wordlists/rockyou.txt"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="openssl",
            description="OpenSSL operations",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="subcommand", type=SchemaType.STRING, required=True,
                    description="OpenSSL subcommand",
                    enum=["enc", "dec", "dgst", "rsa", "ec", "x509", "genrsa", "rand"]
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=True,
                    description="Subcommand arguments"
                ),
            ]
        ))
        
        # Forensics tools
        self.register(ToolSchema(
            name="volatility",
            description="Volatility 3 memory forensics",
            risk_level="low",
            requires_approval=False,
            timeout_default=120,
            timeout_max=300,
            arguments=[
                ToolArgumentSchema(
                    name="memory_file", type=SchemaType.STRING, required=True,
                    description="Memory dump path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="plugin", type=SchemaType.STRING, required=True,
                    description="Volatility plugin",
                    enum=["windows.pslist", "windows.netscan", "windows.filescan", "linux.pslist", "linux.netstat"]
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="binwalk",
            description="Firmware analysis",
            risk_level="low",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="file", type=SchemaType.STRING, required=True,
                    description="File path",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default="-e"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="exiftool",
            description="Metadata extraction",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="file", type=SchemaType.STRING, required=True,
                    description="File path",
                    pattern=r"^/.*"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="yara",
            description="Pattern matching",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="rules", type=SchemaType.STRING, required=True,
                    description="YARA rules file or directory",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Target file or directory",
                    pattern=r"^/.*"
                ),
            ]
        ))
        
        # Stego tools
        self.register(ToolSchema(
            name="steghide",
            description="Steganography hide/extract",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="action", type=SchemaType.STRING, required=True,
                    description="Action",
                    enum=["extract", "embed"]
                ),
                ToolArgumentSchema(
                    name="file", type=SchemaType.STRING, required=True,
                    description="Carrier file",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="passphrase", type=SchemaType.STRING, required=False,
                    description="Passphrase"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="zsteg",
            description="PNG steganography",
            risk_level="low",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="file", type=SchemaType.STRING, required=True,
                    description="PNG file path",
                    pattern=r"^/.*\.png$"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default="-a"
                ),
            ]
        ))
        
        # Mobile tools
        self.register(ToolSchema(
            name="apktool",
            description="APK reverse engineering",
            risk_level="low",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="action", type=SchemaType.STRING, required=True,
                    description="Action",
                    enum=["d", "b"]
                ),
                ToolArgumentSchema(
                    name="apk", type=SchemaType.STRING, required=True,
                    description="APK file path",
                    pattern=r"^/.*\.apk$"
                ),
                ToolArgumentSchema(
                    name="output", type=SchemaType.STRING, required=False,
                    description="Output directory"
                ),
            ]
        ))
        
        # AD tools
        self.register(ToolSchema(
            name="impacket",
            description="Impacket tool execution",
            risk_level="high",
            requires_approval=True,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="tool", type=SchemaType.STRING, required=True,
                    description="Impacket tool name",
                    enum=["secretsdump.py", "getST.py", "getTGT.py", "smbclient.py", "wmiexec.py", "psexec.py", "atexec.py", "smbexec.py"]
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=True,
                    description="Tool arguments"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="kerbrute",
            description="Kerberos brute force",
            risk_level="high",
            requires_approval=True,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="action", type=SchemaType.STRING, required=True,
                    description="Action",
                    enum=["userenum", "passwordspray", "bruteforce"]
                ),
                ToolArgumentSchema(
                    name="domain", type=SchemaType.STRING, required=True,
                    description="Domain name"
                ),
                ToolArgumentSchema(
                    name="wordlist", type=SchemaType.STRING, required=False,
                    description="Wordlist path"
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="netexec",
            description="NetExec AD exploitation",
            risk_level="high",
            requires_approval=True,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="protocol", type=SchemaType.STRING, required=True,
                    description="Protocol",
                    enum=["smb", "ldap", "ssh", "winrm", "rdp"]
                ),
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Target IP or CIDR"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        # Web3 tools
        self.register(ToolSchema(
            name="foundry",
            description="Foundry smart contract toolkit",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="command", type=SchemaType.STRING, required=True,
                    description="Forge command",
                    enum=["build", "test", "script", "deploy", "verify"]
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Command arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="slither",
            description="Slither static analysis",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Contract file or directory",
                    pattern=r"^/.*"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="mythril",
            description="Mythril symbolic execution",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Contract file or address",
                    pattern=r"^/.*|^0x[a-fA-F0-9]{40}$"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        # Cloud tools
        self.register(ToolSchema(
            name="awscli",
            description="AWS CLI",
            risk_level="medium",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="service", type=SchemaType.STRING, required=True,
                    description="AWS service"
                ),
                ToolArgumentSchema(
                    name="command", type=SchemaType.STRING, required=True,
                    description="Service command"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="kubectl",
            description="Kubernetes CLI",
            risk_level="medium",
            requires_approval=False,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="subcommand", type=SchemaType.STRING, required=True,
                    description="kubectl subcommand"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default=""
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="trivy",
            description="Container vulnerability scanner",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="target", type=SchemaType.STRING, required=True,
                    description="Target (image, fs, repo)"
                ),
                ToolArgumentSchema(
                    name="scan_type", type=SchemaType.STRING, required=False,
                    description="Scan type",
                    default="fs",
                    enum=["fs", "image", "repo", "config"]
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.STRING, required=False,
                    description="Additional arguments",
                    default="--format json"
                ),
            ]
        ))
        
        # Execution tools
        self.register(ToolSchema(
            name="python",
            description="Execute Python script",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="script", type=SchemaType.STRING, required=True,
                    description="Python script content"
                ),
                ToolArgumentSchema(
                    name="args", type=SchemaType.ARRAY, required=False,
                    description="Script arguments",
                    items=ToolArgumentSchema(name="arg", type=SchemaType.STRING)
                ),
                ToolArgumentSchema(
                    name="timeout", type=SchemaType.INTEGER, required=False,
                    description="Timeout in seconds",
                    default=60, min_value=10, max_value=120
                ),
            ]
        ))
        
        self.register(ToolSchema(
            name="bash",
            description="Execute Bash script",
            risk_level="medium",
            requires_approval=False,
            timeout_default=60,
            timeout_max=120,
            arguments=[
                ToolArgumentSchema(
                    name="script", type=SchemaType.STRING, required=True,
                    description="Bash script content"
                ),
                ToolArgumentSchema(
                    name="timeout", type=SchemaType.INTEGER, required=False,
                    description="Timeout in seconds",
                    default=60, min_value=10, max_value=120
                ),
            ]
        ))
        
        # Generic command execution (restricted)
        self.register(ToolSchema(
            name="execute_command",
            description="Execute arbitrary command (restricted)",
            risk_level="high",
            requires_approval=True,
            timeout_default=30,
            timeout_max=60,
            arguments=[
                ToolArgumentSchema(
                    name="command", type=SchemaType.STRING, required=True,
                    description="Command to execute",
                    # Restricted pattern - no shell metacharacters
                    pattern=r"^[a-zA-Z0-9_/.-]+(\s+[a-zA-Z0-9_/.-]+)*$"
                ),
                ToolArgumentSchema(
                    name="timeout", type=SchemaType.INTEGER, required=False,
                    description="Timeout in seconds",
                    default=30, min_value=5, max_value=60
                ),
                ToolArgumentSchema(
                    name="working_dir", type=SchemaType.STRING, required=False,
                    description="Working directory",
                    default="/workspace"
                ),
            ]
        ))
    
    def register(self, schema: ToolSchema):
        """Register a tool schema."""
        self._schemas[schema.name] = schema
    
    def get(self, name: str) -> Optional[ToolSchema]:
        """Get tool schema."""
        return self._schemas.get(name)
    
    def validate(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, str, Dict[str, Any]]:
        """
        Validate arguments against tool schema.
        
        Returns:
            (valid, error_message, validated_arguments)
        """
        schema = self._schemas.get(tool_name)
        if not schema:
            return False, f"Unknown tool: {tool_name}", {}
        
        validated = {}
        
        # Check required arguments
        for arg_schema in schema.arguments:
            if arg_schema.required and arg_schema.name not in arguments:
                return False, f"Missing required argument: {arg_schema.name}", {}
            
            if arg_schema.name in arguments:
                value = arguments[arg_schema.name]
                valid, error, validated_value = self._validate_argument(arg_schema, value)
                if not valid:
                    return False, f"Argument '{arg_schema.name}': {error}", {}
                validated[arg_schema.name] = validated_value
            elif arg_schema.default is not None:
                validated[arg_schema.name] = arg_schema.default
        
        # Check for unexpected arguments
        expected_names = {a.name for a in schema.arguments}
        for key in arguments:
            if key not in expected_names:
                return False, f"Unexpected argument: {key}", {}
        
        return True, "Valid", validated
    
    def _validate_argument(self, arg_schema: ToolArgumentSchema, value: Any) -> tuple[bool, str, Any]:
        """Validate a single argument."""
        # Type validation
        if arg_schema.type == SchemaType.STRING:
            if not isinstance(value, str):
                return False, f"Expected string, got {type(value).__name__}", None
            if arg_schema.pattern and not re.match(arg_schema.pattern, value):
                return False, f"String does not match pattern: {arg_schema.pattern}", None
            if arg_schema.min_length is not None and len(value) < arg_schema.min_length:
                return False, f"String too short (min {arg_schema.min_length})", None
            if arg_schema.max_length is not None and len(value) > arg_schema.max_length:
                return False, f"String too long (max {arg_schema.max_length})", None
            if arg_schema.enum and value not in arg_schema.enum:
                return False, f"Value not in enum: {arg_schema.enum}", None
        
        elif arg_schema.type == SchemaType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                return False, f"Expected integer, got {type(value).__name__}", None
            if arg_schema.min_value is not None and value < arg_schema.min_value:
                return False, f"Value below minimum: {arg_schema.min_value}", None
            if arg_schema.max_value is not None and value > arg_schema.max_value:
                return False, f"Value above maximum: {arg_schema.max_value}", None
            if arg_schema.enum and value not in arg_schema.enum:
                return False, f"Value not in enum: {arg_schema.enum}", None
        
        elif arg_schema.type == SchemaType.NUMBER:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False, f"Expected number, got {type(value).__name__}", None
            if arg_schema.min_value is not None and value < arg_schema.min_value:
                return False, f"Value below minimum: {arg_schema.min_value}", None
            if arg_schema.max_value is not None and value > arg_schema.max_value:
                return False, f"Value above maximum: {arg_schema.max_value}", None
        
        elif arg_schema.type == SchemaType.BOOLEAN:
            if not isinstance(value, bool):
                return False, f"Expected boolean, got {type(value).__name__}", None
        
        elif arg_schema.type == SchemaType.ARRAY:
            if not isinstance(value, list):
                return False, f"Expected array, got {type(value).__name__}", None
            if arg_schema.items:
                validated_items = []
                for item in value:
                    valid, error, validated_item = self._validate_argument(arg_schema.items, item)
                    if not valid:
                        return False, f"Array item: {error}", None
                    validated_items.append(validated_item)
                return True, "Valid", validated_items
        
        elif arg_schema.type == SchemaType.OBJECT:
            if not isinstance(value, dict):
                return False, f"Expected object, got {type(value).__name__}", None
            if arg_schema.properties:
                validated_obj = {}
                for prop_name, prop_schema in arg_schema.properties.items():
                    if prop_name in value:
                        valid, error, validated_value = self._validate_argument(prop_schema, value[prop_name])
                        if not valid:
                            return False, f"Property '{prop_name}': {error}", None
                        validated_obj[prop_name] = validated_value
                return True, "Valid", validated_obj
        
        return True, "Valid", value
    
    def get_schema_names(self) -> List[str]:
        """Get all registered schema names."""
        return list(self._schemas.keys())


# Global registry
_tool_schema_registry: Optional[ToolSchemaRegistry] = None


def get_tool_schema_registry() -> ToolSchemaRegistry:
    """Get global tool schema registry."""
    global _tool_schema_registry
    if _tool_schema_registry is None:
        _tool_schema_registry = ToolSchemaRegistry()
    return _tool_schema_registry