"""Capability Definitions - Fine-grained permissions for agent actions"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from pathlib import Path


class Capability(str, Enum):
    """Fine-grained capabilities that agents can possess."""
    
    # Network capabilities
    NETWORK_TCP_CONNECT = "network.tcp.connect"
    NETWORK_UDP_SEND = "network.udp.send"
    NETWORK_RAW_SOCKET = "network.raw_socket"
    NETWORK_DNS_RESOLVE = "network.dns.resolve"
    NETWORK_ICMP_PING = "network.icmp.ping"
    
    # Filesystem capabilities
    FS_READ_CHALLENGE = "fs.read.challenge"
    FS_READ_WORKSPACE = "fs.read.workspace"
    FS_WRITE_WORKSPACE = "fs.write.workspace"
    FS_READ_ARTIFACTS = "fs.read.artifacts"
    FS_WRITE_ARTIFACTS = "fs.write.artifacts"
    FS_READ_LOGS = "fs.read.logs"
    FS_WRITE_LOGS = "fs.write.logs"
    FS_READ_TMP = "fs.read.tmp"
    FS_WRITE_TMP = "fs.write.tmp"
    
    # Tool capabilities (each tool is a capability)
    TOOL_NMAP = "tool.nmap"
    TOOL_CURL = "tool.curl"
    TOOL_FFUF = "tool.ffuf"
    TOOL_HTTPX = "tool.httpx"
    TOOL_NUCLEI = "tool.nuclei"
    TOOL_SQLMAP = "tool.sqlmap"
    TOOL_GDB = "tool.gdb"
    TOOL_PWNTOOLS = "tool.pwntools"
    TOOL_CHECKSEC = "tool.checksec"
    TOOL_ROPGADGET = "tool.ropgadget"
    TOOL_ROPPER = "tool.ropper"
    TOOL_GHIDRA = "tool.ghidra"
    TOOL_RADARE2 = "tool.radare2"
    TOOL_ANGRI = "tool.angr"
    TOOL_VOLATILITY = "tool.volatility"
    TOOL_BINWALK = "tool.binwalk"
    TOOL_FOREMOST = "tool.foremost"
    TOOL_EXIFTOOL = "tool.exiftool"
    TOOL_YARA = "tool.yara"
    TOOL_HASHCAT = "tool.hashcat"
    TOOL_JOHN = "tool.john"
    TOOL_OPENSSL = "tool.openssl"
    TOOL_STEGHIDE = "tool.steghide"
    TOOL_ZSTEG = "tool.zsteg"
    TOOL_ADB = "tool.adb"
    TOOL_APKTOOL = "tool.apktool"
    TOOL_FRIDA = "tool.frida"
    TOOL_IMPACKET = "tool.impacket"
    TOOL_KERBRUTE = "tool.kerbrute"
    TOOL_NETEXEC = "tool.netexec"
    TOOL_FOUNDRY = "tool.foundry"
    TOOL_SLITHER = "tool.slither"
    TOOL_MYTHRIL = "tool.mythril"
    TOOL_AWSCLI = "tool.awscli"
    TOOL_KUBECTL = "tool.kubectl"
    TOOL_TRIVY = "tool.trivy"
    TOOL_KNOCK = "tool.knock"
    TOOL_MASSCAN = "tool.masscan"
    TOOL_RUSTSCAN = "tool.rustscan"
    TOOL_TSHARK = "tool.tshark"
    TOOL_SCATTER = "tool.scatter"
    TOOL_PYTHON = "tool.python"
    TOOL_BASH = "tool.bash"
    
    # Execution capabilities
    EXEC_COMMAND = "exec.command"
    EXEC_PYTHON_SCRIPT = "exec.python_script"
    EXEC_BASH_SCRIPT = "exec.bash_script"
    
    # Privileged operations (require approval)
    PRIV_INSTALL_PACKAGE = "priv.install_package"
    PRIV_CREATE_MOUNT = "priv.create_mount"
    PRIV_CONFIGURE_NETWORK = "priv.configure_network"
    PRIV_DEVICE_PERMISSION = "priv.device_permission"
    PRIV_SYSCTL_MODIFY = "priv.sysctl_modify"
    PRIV_NAMESPACE_ENTER = "priv.namespace_enter"
    PRIV_TCPDUMP = "priv.tcpdump"
    
    # Agent lifecycle
    AGENT_SPAWN = "agent.spawn"
    AGENT_CANCEL = "agent.cancel"
    
    # Evidence/Artifact
    EVIDENCE_SUBMIT = "evidence.submit"
    EVIDENCE_VERIFY = "evidence.verify"
    ARTIFACT_STORE = "artifact.store"
    ARTIFACT_RETRIEVE = "artifact.retrieve"
    
    # Memory
    MEMORY_STORE = "memory.store"
    MEMORY_QUERY = "memory.query"
    MEMORY_PROMOTE = "memory.promote"


@dataclass
class CapabilityDefinition:
    """Definition of a capability with its constraints."""
    capability: Capability
    description: str
    risk_level: str  # low, medium, high, critical
    requires_approval: bool = False
    allowed_agent_roles: List[str] = field(default_factory=lambda: ["*"])
    allowed_networks: List[str] = field(default_factory=lambda: ["*"])
    allowed_targets: List[str] = field(default_factory=lambda: ["*"])
    max_uses_per_challenge: Optional[int] = None
    max_duration_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """Registry of all capabilities with their definitions."""
    
    def __init__(self):
        self._capabilities: Dict[Capability, CapabilityDefinition] = {}
        self._register_default_capabilities()
    
    def _register_default_capabilities(self):
        """Register default capability definitions."""
        defaults = [
            # Network capabilities
            CapabilityDefinition(
                capability=Capability.NETWORK_TCP_CONNECT,
                description="Establish TCP connections",
                risk_level="low",
                allowed_agent_roles=["web", "network", "osint", "ad", "cloud", "orchestrator"],
                allowed_networks=["ctf_targets", "ctf_workspace"],
            ),
            CapabilityDefinition(
                capability=Capability.NETWORK_UDP_SEND,
                description="Send UDP packets",
                risk_level="low",
                allowed_agent_roles=["network", "osint"],
                allowed_networks=["ctf_targets"],
            ),
            CapabilityDefinition(
                capability=Capability.NETWORK_DNS_RESOLVE,
                description="DNS resolution",
                risk_level="low",
                allowed_agent_roles=["web", "network", "osint", "orchestrator"],
                allowed_networks=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.NETWORK_ICMP_PING,
                description="ICMP ping",
                risk_level="low",
                allowed_agent_roles=["network", "osint", "orchestrator"],
                allowed_networks=["ctf_targets", "ctf_workspace"],
            ),
            CapabilityDefinition(
                capability=Capability.NETWORK_RAW_SOCKET,
                description="Raw socket access (requires root)",
                risk_level="critical",
                requires_approval=True,
                allowed_agent_roles=["network"],
                allowed_networks=["ctf_targets"],
            ),
            
            # Filesystem capabilities
            CapabilityDefinition(
                capability=Capability.FS_READ_CHALLENGE,
                description="Read challenge files (read-only)",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_READ_WORKSPACE,
                description="Read own workspace",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_WRITE_WORKSPACE,
                description="Write to own workspace",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_READ_ARTIFACTS,
                description="Read artifacts",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_WRITE_ARTIFACTS,
                description="Write artifacts",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_READ_LOGS,
                description="Read logs",
                risk_level="low",
                allowed_agent_roles=["orchestrator", "meta"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_WRITE_LOGS,
                description="Write logs",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_READ_TMP,
                description="Read /tmp",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.FS_WRITE_TMP,
                description="Write /tmp",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            
            # Tool capabilities - Web
            CapabilityDefinition(
                capability=Capability.TOOL_NMAP,
                description="Network port scanning",
                risk_level="medium",
                allowed_agent_roles=["network", "web", "ad", "orchestrator"],
                allowed_networks=["ctf_targets"],
                max_duration_seconds=300,
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_MASSCAN,
                description="Fast port scanning",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["network"],
                allowed_networks=["ctf_targets"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_RUSTSCAN,
                description="Fast port scanning (rust)",
                risk_level="medium",
                allowed_agent_roles=["network", "web"],
                allowed_networks=["ctf_targets"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_CURL,
                description="HTTP client",
                risk_level="low",
                allowed_agent_roles=["*"],
                allowed_networks=["ctf_targets", "ctf_workspace"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_FFUF,
                description="Web fuzzing",
                risk_level="medium",
                allowed_agent_roles=["web"],
                allowed_networks=["ctf_targets"],
                max_duration_seconds=300,
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_HTTPX,
                description="HTTP probing",
                risk_level="low",
                allowed_agent_roles=["web", "network", "orchestrator"],
                allowed_networks=["ctf_targets", "ctf_workspace"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_NUCLEI,
                description="Vulnerability scanning",
                risk_level="medium",
                allowed_agent_roles=["web", "orchestrator"],
                allowed_networks=["ctf_targets"],
                max_duration_seconds=300,
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_SQLMAP,
                description="SQL injection testing",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["web"],
                allowed_networks=["ctf_targets"],
                max_duration_seconds=600,
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_KNOCK,
                description="Subdomain enumeration",
                risk_level="low",
                allowed_agent_roles=["web", "osint"],
                allowed_networks=["ctf_targets"],
            ),
            
            # Tool capabilities - Pwn/Reverse
            CapabilityDefinition(
                capability=Capability.TOOL_GDB,
                description="GDB debugger",
                risk_level="medium",
                allowed_agent_roles=["pwn", "reverse"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_PWNTOOLS,
                description="Pwntools exploit framework",
                risk_level="medium",
                allowed_agent_roles=["pwn"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_CHECKSEC,
                description="Binary protection checking",
                risk_level="low",
                allowed_agent_roles=["pwn", "reverse"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_ROPGADGET,
                description="ROP gadget finder",
                risk_level="low",
                allowed_agent_roles=["pwn", "reverse"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_ROPPER,
                description="ROP chain builder",
                risk_level="low",
                allowed_agent_roles=["pwn", "reverse"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_GHIDRA,
                description="Ghidra reverse engineering",
                risk_level="low",
                allowed_agent_roles=["reverse", "malware", "firmware"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_RADARE2,
                description="Radare2 reverse engineering",
                risk_level="low",
                allowed_agent_roles=["reverse", "malware", "firmware", "pwn"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_ANGRI,
                description="Angr symbolic execution",
                risk_level="medium",
                allowed_agent_roles=["reverse", "pwn"],
            ),
            
            # Tool capabilities - Crypto
            CapabilityDefinition(
                capability=Capability.TOOL_HASHCAT,
                description="Hash cracking",
                risk_level="medium",
                allowed_agent_roles=["crypto", "forensics"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_JOHN,
                description="John the Ripper",
                risk_level="medium",
                allowed_agent_roles=["crypto", "forensics"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_OPENSSL,
                description="OpenSSL crypto operations",
                risk_level="low",
                allowed_agent_roles=["crypto", "web", "reverse"],
            ),
            
            # Tool capabilities - Forensics
            CapabilityDefinition(
                capability=Capability.TOOL_VOLATILITY,
                description="Memory forensics",
                risk_level="low",
                allowed_agent_roles=["forensics", "malware"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_BINWALK,
                description="Firmware/artifact analysis",
                risk_level="low",
                allowed_agent_roles=["forensics", "firmware", "stego", "malware"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_FOREMOST,
                description="File carving",
                risk_level="low",
                allowed_agent_roles=["forensics"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_EXIFTOOL,
                description="Metadata extraction",
                risk_level="low",
                allowed_agent_roles=["forensics", "stego"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_YARA,
                description="Pattern matching",
                risk_level="low",
                allowed_agent_roles=["forensics", "malware"],
            ),
            
            # Tool capabilities - Stego
            CapabilityDefinition(
                capability=Capability.TOOL_STEGHIDE,
                description="Steganography hide/extract",
                risk_level="low",
                allowed_agent_roles=["stego"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_ZSTEG,
                description="PNG steganography",
                risk_level="low",
                allowed_agent_roles=["stego"],
            ),
            
            # Tool capabilities - Mobile
            CapabilityDefinition(
                capability=Capability.TOOL_ADB,
                description="Android Debug Bridge",
                risk_level="medium",
                allowed_agent_roles=["mobile"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_APKTOOL,
                description="APK reverse engineering",
                risk_level="low",
                allowed_agent_roles=["mobile"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_FRIDA,
                description="Dynamic instrumentation",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["mobile"],
            ),
            
            # Tool capabilities - AD
            CapabilityDefinition(
                capability=Capability.TOOL_IMPACKET,
                description="Impacket AD protocols",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["ad"],
                allowed_networks=["ctf_targets", "ctf_attack_defense"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_KERBRUTE,
                description="Kerberos brute force",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["ad"],
                allowed_networks=["ctf_targets", "ctf_attack_defense"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_NETEXEC,
                description="NetExec AD exploitation",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["ad"],
                allowed_networks=["ctf_targets", "ctf_attack_defense"],
            ),
            
            # Tool capabilities - Web3
            CapabilityDefinition(
                capability=Capability.TOOL_FOUNDRY,
                description="Foundry smart contract toolkit",
                risk_level="medium",
                allowed_agent_roles=["web3"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_SLITHER,
                description="Slither static analysis",
                risk_level="medium",
                allowed_agent_roles=["web3"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_MYTHRIL,
                description="Mythril symbolic execution",
                risk_level="medium",
                allowed_agent_roles=["web3"],
            ),
            
            # Tool capabilities - Cloud
            CapabilityDefinition(
                capability=Capability.TOOL_AWSCLI,
                description="AWS CLI",
                risk_level="medium",
                allowed_agent_roles=["cloud"],
                allowed_networks=["ctf_targets"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_KUBECTL,
                description="Kubernetes CLI",
                risk_level="medium",
                allowed_agent_roles=["cloud"],
                allowed_networks=["ctf_targets"],
            ),
            CapabilityDefinition(
                capability=Capability.TOOL_TRIVY,
                description="Container vulnerability scanner",
                risk_level="medium",
                allowed_agent_roles=["cloud", "supply_chain"],
            ),
            
            # Execution capabilities
            CapabilityDefinition(
                capability=Capability.EXEC_COMMAND,
                description="Execute arbitrary command",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["programming", "orchestrator"],
            ),
            CapabilityDefinition(
                capability=Capability.EXEC_PYTHON_SCRIPT,
                description="Execute Python script",
                risk_level="medium",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.EXEC_BASH_SCRIPT,
                description="Execute Bash script",
                risk_level="medium",
                allowed_agent_roles=["programming", "orchestrator"],
            ),
            
            # Privileged operations
            CapabilityDefinition(
                capability=Capability.PRIV_INSTALL_PACKAGE,
                description="Install system package",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["orchestrator", "programming"],
                max_uses_per_challenge=5,
            ),
            CapabilityDefinition(
                capability=Capability.PRIV_CREATE_MOUNT,
                description="Create bind mount",
                risk_level="critical",
                requires_approval=True,
                allowed_agent_roles=["orchestrator"],
            ),
            CapabilityDefinition(
                capability=Capability.PRIV_CONFIGURE_NETWORK,
                description="Configure network namespace",
                risk_level="critical",
                requires_approval=True,
                allowed_agent_roles=["orchestrator"],
            ),
            CapabilityDefinition(
                capability=Capability.PRIV_DEVICE_PERMISSION,
                description="Grant device access",
                risk_level="critical",
                requires_approval=True,
                allowed_agent_roles=["orchestrator"],
            ),
            CapabilityDefinition(
                capability=Capability.PRIV_SYSCTL_MODIFY,
                description="Modify sysctl parameters",
                risk_level="critical",
                requires_approval=True,
                allowed_agent_roles=["orchestrator"],
            ),
            CapabilityDefinition(
                capability=Capability.PRIV_NAMESPACE_ENTER,
                description="Enter namespace",
                risk_level="critical",
                requires_approval=True,
                allowed_agent_roles=["orchestrator"],
            ),
            CapabilityDefinition(
                capability=Capability.PRIV_TCPDUMP,
                description="Packet capture",
                risk_level="high",
                requires_approval=True,
                allowed_agent_roles=["network", "forensics"],
                allowed_networks=["ctf_targets"],
            ),
            
            # Agent lifecycle
            CapabilityDefinition(
                capability=Capability.AGENT_SPAWN,
                description="Spawn sub-agent",
                risk_level="low",
                allowed_agent_roles=["orchestrator"],
            ),
            CapabilityDefinition(
                capability=Capability.AGENT_CANCEL,
                description="Cancel agent",
                risk_level="low",
                allowed_agent_roles=["orchestrator"],
            ),
            
            # Evidence/Artifact
            CapabilityDefinition(
                capability=Capability.EVIDENCE_SUBMIT,
                description="Submit evidence claim",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.EVIDENCE_VERIFY,
                description="Verify evidence",
                risk_level="low",
                allowed_agent_roles=["orchestrator", "meta"],
            ),
            CapabilityDefinition(
                capability=Capability.ARTIFACT_STORE,
                description="Store artifact",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.ARTIFACT_RETRIEVE,
                description="Retrieve artifact",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            
            # Memory
            CapabilityDefinition(
                capability=Capability.MEMORY_STORE,
                description="Store memory entry",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.MEMORY_QUERY,
                description="Query memory",
                risk_level="low",
                allowed_agent_roles=["*"],
            ),
            CapabilityDefinition(
                capability=Capability.MEMORY_PROMOTE,
                description="Promote memory layer",
                risk_level="low",
                allowed_agent_roles=["orchestrator", "meta"],
            ),
        ]
        
        for cap_def in defaults:
            self._capabilities[cap_def.capability] = cap_def
    
    def get(self, capability: Capability) -> Optional[CapabilityDefinition]:
        """Get capability definition."""
        return self._capabilities.get(capability)
    
    def get_for_agent(self, agent_role: str) -> List[CapabilityDefinition]:
        """Get all capabilities allowed for an agent role."""
        return [
            cap for cap in self._capabilities.values()
            if "*" in cap.allowed_agent_roles or agent_role in cap.allowed_agent_roles
        ]
    
    def has_capability(self, agent_role: str, capability: Capability) -> bool:
        """Check if agent role has a capability."""
        cap_def = self._capabilities.get(capability)
        if not cap_def:
            return False
        return "*" in cap_def.allowed_agent_roles or agent_role in cap_def.allowed_agent_roles
    
    def all_capabilities(self) -> List[CapabilityDefinition]:
        """Get all capability definitions."""
        return list(self._capabilities.values())


# Global registry
_capability_registry: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """Get global capability registry."""
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
    return _capability_registry