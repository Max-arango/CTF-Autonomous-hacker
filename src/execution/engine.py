"""Execution Engine - Secure tool execution with schema validation and authorization"""
import asyncio
import json
import uuid
import shlex
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Awaitable
from pathlib import Path
import re

from ..config.settings import get_settings
from ..config.loader import get_config_manager
from ..artifacts import ArtifactManager, get_artifact_manager
from ..observability import get_logger, log_command_execution
from ..security import (
    get_tool_schema_registry,
    get_authorization_context,
    get_scope_engine,
    ToolSchema,
    ToolArgumentSchema,
    SchemaType,
)
from ..permissions import PermissionClient, get_permission_client


@dataclass
class ToolResult:
    """Result of tool execution."""
    tool_name: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class ToolWrapperBase:
    """Base class for tool wrappers - secure execution without shell."""

    def __init__(self, tool_name: str, execution_engine: "ExecutionEngine"):
        self.tool_name = tool_name
        self.execution_engine = execution_engine

    async def execute(self, arguments: Dict[str, Any], agent_id: str) -> ToolResult:
        """Execute the tool with given arguments."""
        raise NotImplementedError

    def validate_arguments(self, arguments: Dict[str, Any]) -> bool:
        """Validate arguments."""
        return True

    def get_timeout(self, arguments: Dict[str, Any]) -> int:
        """Get timeout for this execution."""
        return arguments.get("timeout", 60)

    def build_command(self, arguments: Dict[str, Any]) -> List[str]:
        """Build command as argv list (NO shell). Override in subclasses."""
        raise NotImplementedError


class CommandWrapper(ToolWrapperBase):
    """Wrapper for direct command execution with argv (NO shell)."""

    def __init__(self, tool_name: str, execution_engine: "ExecutionEngine", command_template: List[str]):
        super().__init__(tool_name, execution_engine)
        self.command_template = command_template

    def build_command(self, arguments: Dict[str, Any]) -> List[str]:
        """Build command as argv list with argument substitution."""
        cmd = []
        for part in self.command_template:
            if isinstance(part, str) and "{" in part and "}" in part:
                # Substitute arguments
                try:
                    cmd.append(part.format(**arguments))
                except KeyError as e:
                    raise ValueError(f"Missing argument for command template: {e}")
            else:
                cmd.append(str(part))
        return cmd


class ToolWrapper:
    """Tool wrapper with metadata."""

    def __init__(
        self,
        name: str,
        category: str,
        binary: str,
        version_check: str,
        requires_root: bool = False,
        network_required: bool = False,
        container_profile: str = "base",
        security_risk: str = "low",
        supported_agents: List[str] = None,
        wrapper: Optional[ToolWrapperBase] = None,
        schema: Optional[ToolSchema] = None,
    ):
        self.name = name
        self.category = category
        self.binary = binary
        self.version_check = version_check
        self.requires_root = requires_root
        self.network_required = network_required
        self.container_profile = container_profile
        self.security_risk = security_risk
        self.supported_agents = supported_agents or ["*"]
        self.wrapper = wrapper
        self.schema = schema

    def is_available_for_agent(self, agent_role: str) -> bool:
        """Check if tool is available for agent role."""
        return "*" in self.supported_agents or agent_role in self.supported_agents


class ToolRegistry:
    """Registry of available tools with schemas."""

    def __init__(self):
        self._tools: Dict[str, ToolWrapper] = {}
        self._wrappers: Dict[str, ToolWrapperBase] = {}
        self._schema_registry = get_tool_schema_registry()
        self._load_config()

    def _load_config(self):
        """Load tool configuration."""
        config_manager = get_config_manager()
        tools_config = config_manager.get("tools", {})

        for category, tools in tools_config.items():
            if isinstance(tools, list):
                for tool_config in tools:
                    # Get schema if available
                    tool_name = tool_config.get("name")
                    schema = self._schema_registry.get(tool_name) if tool_name else None
                    tool_config["schema"] = schema
                    self.register_tool(ToolWrapper(**tool_config))

    def register_tool(self, tool: ToolWrapper):
        """Register a tool."""
        self._tools[tool.name] = tool

    def register_wrapper(self, tool_name: str, wrapper: ToolWrapperBase):
        """Register a custom wrapper."""
        self._wrappers[tool_name] = wrapper

    def get_tool(self, name: str) -> Optional[ToolWrapper]:
        """Get tool by name."""
        return self._tools.get(name)

    def get_wrapper(self, name: str) -> Optional[ToolWrapperBase]:
        """Get wrapper for tool."""
        return self._wrappers.get(name)

    def get_schema(self, name: str) -> Optional[ToolSchema]:
        """Get schema for tool."""
        return self._schema_registry.get(name)

    def list_tools(
        self,
        category: Optional[str] = None,
        agent_role: Optional[str] = None,
    ) -> List[ToolWrapper]:
        """List tools with optional filters."""
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if agent_role:
            tools = [t for t in tools if t.is_available_for_agent(agent_role)]

        return tools

    def get_categories(self) -> List[str]:
        """Get all categories."""
        return list(set(t.category for t in self._tools.values()))


class ExecutionEngine:
    """Main execution engine for secure tool execution."""

    def __init__(self):
        self.settings = get_settings()
        self.registry = ToolRegistry()
        self.artifact_manager: Optional[ArtifactManager] = None
        self.permission_client: Optional[PermissionClient] = None
        self.auth_manager = get_authorization_context()
        self.scope_engine = get_scope_engine()
        self.schema_registry = get_tool_schema_registry()

        # Tool execution hooks
        self.pre_execution_hooks: List[Callable[[str, Dict[str, Any], str], Awaitable[None]]] = []
        self.post_execution_hooks: List[Callable[[ToolResult], Awaitable[None]]] = []

    async def initialize(self):
        """Initialize the engine."""
        self.artifact_manager = await get_artifact_manager()
        self.permission_client = await get_permission_client()

        # Register built-in tool wrappers
        self._register_builtin_wrappers()

    def _register_builtin_wrappers(self):
        """Register built-in tool wrappers with secure argv-based execution."""
        # Network tools
        self.registry.register_wrapper("nmap", CommandWrapper("nmap", self, ["nmap"]))
        self.registry.register_wrapper("masscan", CommandWrapper("masscan", self, ["masscan"]))
        self.registry.register_wrapper("rustscan", CommandWrapper("rustscan", self, ["rustscan"]))
        
        # Web tools
        self.registry.register_wrapper("curl", CommandWrapper("curl", self, ["curl"]))
        self.registry.register_wrapper("ffuf", CommandWrapper("ffuf", self, ["ffuf"]))
        self.registry.register_wrapper("httpx", CommandWrapper("httpx", self, ["httpx"]))
        self.registry.register_wrapper("nuclei", CommandWrapper("nuclei", self, ["nuclei"]))
        self.registry.register_wrapper("sqlmap", CommandWrapper("sqlmap", self, ["sqlmap"]))
        
        # Pwn/Reverse tools
        self.registry.register_wrapper("gdb", CommandWrapper("gdb", self, ["gdb"]))
        self.registry.register_wrapper("pwntools", CommandWrapper("pwntools", self, ["python3", "-c"]))
        self.registry.register_wrapper("checksec", CommandWrapper("checksec", self, ["checksec"]))
        self.registry.register_wrapper("ROPgadget", CommandWrapper("ROPgadget", self, ["ROPgadget"]))
        self.registry.register_wrapper("ropper", CommandWrapper("ropper", self, ["ropper"]))
        self.registry.register_wrapper("ghidra", CommandWrapper("ghidra", self, ["ghidra"]))
        self.registry.register_wrapper("radare2", CommandWrapper("radare2", self, ["r2"]))
        
        # Crypto tools
        self.registry.register_wrapper("hashcat", CommandWrapper("hashcat", self, ["hashcat"]))
        self.registry.register_wrapper("john", CommandWrapper("john", self, ["john"]))
        self.registry.register_wrapper("openssl", CommandWrapper("openssl", self, ["openssl"]))
        
        # Forensics tools
        self.registry.register_wrapper("volatility", CommandWrapper("volatility", self, ["python3", "-m", "volatility"]))
        self.registry.register_wrapper("binwalk", CommandWrapper("binwalk", self, ["binwalk"]))
        self.registry.register_wrapper("exiftool", CommandWrapper("exiftool", self, ["exiftool"]))
        self.registry.register_wrapper("yara", CommandWrapper("yara", self, ["yara"]))
        
        # Stego tools
        self.registry.register_wrapper("steghide", CommandWrapper("steghide", self, ["steghide"]))
        self.registry.register_wrapper("zsteg", CommandWrapper("zsteg", self, ["zsteg"]))
        
        # AD tools
        self.registry.register_wrapper("impacket", CommandWrapper("impacket", self, ["python3", "-m", "impacket"]))
        self.registry.register_wrapper("kerbrute", CommandWrapper("kerbrute", self, ["kerbrute"]))
        self.registry.register_wrapper("netexec", CommandWrapper("netexec", self, ["nxc"]))
        
        # Web3 tools
        self.registry.register_wrapper("foundry", CommandWrapper("foundry", self, ["forge"]))
        self.registry.register_wrapper("slither", CommandWrapper("slither", self, ["slither"]))
        self.registry.register_wrapper("mythril", CommandWrapper("mythril", self, ["mythril"]))
        
        # Cloud tools
        self.registry.register_wrapper("awscli", CommandWrapper("awscli", self, ["aws"]))
        self.registry.register_wrapper("kubectl", CommandWrapper("kubectl", self, ["kubectl"]))
        self.registry.register_wrapper("trivy", CommandWrapper("trivy", self, ["trivy"]))
        
        # Execution tools
        self.registry.register_wrapper("python", CommandWrapper("python", self, ["python3", "-c"]))
        self.registry.register_wrapper("bash", CommandWrapper("bash", self, ["bash", "-c"]))
        
        # Generic command (restricted)
        self.registry.register_wrapper("execute_command", CommandWrapper("execute_command", self, ["/bin/bash", "-c"]))

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: str,
        allowed_tools: Optional[List[str]] = None,
    ) -> ToolResult:
        """Execute a tool with full security validation."""
        start_time = time.time()

        # 1. Get authorization context
        auth_manager = get_authorization_context()
        auth_context = auth_manager.get_context(agent_id)
        if not auth_context:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"No authorization context for agent {agent_id}",
            )

        # 2. Determine capability for this tool
        capability = self._tool_to_capability(tool_name)
        if not capability:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"No capability mapping for tool: {tool_name}",
            )

        # 3. Authorize the action
        auth_result = auth_manager.authorize_action(
            agent_id=agent_id,
            action=f"execute_{tool_name}",
            capability=capability,
            tool=tool_name,
            target=arguments.get("target") or arguments.get("url"),
            port=arguments.get("port"),
            protocol=arguments.get("protocol", "tcp"),
            path=arguments.get("path") or arguments.get("file"),
            operation=arguments.get("operation"),
            resource_request=arguments.get("resource_request", {}),
            metadata={"arguments": arguments},
        )

        if not auth_result.allowed:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Authorization denied: {auth_result.reason}",
            )

        if auth_result.requires_approval:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Requires approval: {auth_result.reason}",
            )

        # 4. Check if tool is allowed
        if allowed_tools and tool_name not in allowed_tools and "*" not in allowed_tools:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not allowed for this agent",
            )

        # 5. Get tool info
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found in registry",
            )

        # 6. Validate arguments against schema
        schema = self.registry.get_schema(tool_name) or tool.schema
        if schema:
            valid, error, validated_args = self.schema_registry.validate(tool_name, arguments)
            if not valid:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Argument validation failed: {error}",
                )
        else:
            validated_args = arguments

        # 7. Check agent role support
        agent_role = self._get_agent_role(agent_id)
        if not tool.is_available_for_agent(agent_role):
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not available for agent role '{agent_role}'",
            )

        # 8. Run pre-execution hooks
        for hook in self.pre_execution_hooks:
            await hook(tool_name, validated_args, agent_id)

        # 9. Execute
        try:
            if tool.wrapper:
                result = await tool.wrapper.execute(validated_args, agent_id)
            else:
                result = await self._execute_generic(tool, validated_args, agent_id)
        except Exception as e:
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

        result.execution_time = time.time() - start_time

        # 10. Record command in authorization context
        auth_context.record_command()

        # 11. Run post-execution hooks
        for hook in self.post_execution_hooks:
            await hook(result)

        # 12. Log execution
        await log_command_execution(
            agent_id=agent_id,
            tool=tool_name,
            arguments=validated_args,
            result=result,
        )

        return result

    def _tool_to_capability(self, tool_name: str) -> Optional[Capability]:
        """Map tool name to capability."""
        from ..security.capabilities import Capability
        
        mapping = {
            "nmap": Capability.TOOL_NMAP,
            "masscan": Capability.TOOL_MASSCAN,
            "rustscan": Capability.TOOL_RUSTSCAN,
            "curl": Capability.TOOL_CURL,
            "ffuf": Capability.TOOL_FFUF,
            "httpx": Capability.TOOL_HTTPX,
            "nuclei": Capability.TOOL_NUCLEI,
            "sqlmap": Capability.TOOL_SQLMAP,
            "gdb": Capability.TOOL_GDB,
            "pwntools": Capability.TOOL_PWNTOOLS,
            "checksec": Capability.TOOL_CHECKSEC,
            "ROPgadget": Capability.TOOL_ROPGADGET,
            "ropper": Capability.TOOL_ROPPER,
            "ghidra": Capability.TOOL_GHIDRA,
            "radare2": Capability.TOOL_RADARE2,
            "angr": Capability.TOOL_ANGRI,
            "hashcat": Capability.TOOL_HASHCAT,
            "john": Capability.TOOL_JOHN,
            "openssl": Capability.TOOL_OPENSSL,
            "volatility": Capability.TOOL_VOLATILITY,
            "binwalk": Capability.TOOL_BINWALK,
            "foremost": Capability.TOOL_FOREMOST,
            "exiftool": Capability.TOOL_EXIFTOOL,
            "yara": Capability.TOOL_YARA,
            "steghide": Capability.TOOL_STEGHIDE,
            "zsteg": Capability.TOOL_ZSTEG,
            "apktool": Capability.TOOL_APKTOOL,
            "frida": Capability.TOOL_FRIDA,
            "impacket": Capability.TOOL_IMPACKET,
            "kerbrute": Capability.TOOL_KERBRUTE,
            "netexec": Capability.TOOL_NETEXEC,
            "foundry": Capability.TOOL_FOUNDRY,
            "slither": Capability.TOOL_SLITHER,
            "mythril": Capability.TOOL_MYTHRIL,
            "awscli": Capability.TOOL_AWSCLI,
            "kubectl": Capability.TOOL_KUBECTL,
            "trivy": Capability.TOOL_TRIVY,
            "python": Capability.EXEC_PYTHON_SCRIPT,
            "bash": Capability.EXEC_BASH_SCRIPT,
            "execute_command": Capability.EXEC_COMMAND,
        }
        return mapping.get(tool_name)

    def _get_agent_role(self, agent_id: str) -> str:
        """Extract agent role from agent ID."""
        parts = agent_id.split("-")
        if len(parts) >= 2:
            return parts[1]
        return "unknown"

    async def _execute_generic(
        self,
        tool: ToolWrapper,
        arguments: Dict[str, Any],
        agent_id: str,
    ) -> ToolResult:
        """Execute tool generically via secure argv-based command."""
        # Build command as argv list (NO shell)
        if tool.name in ("python3", "python"):
            command = self._build_python_argv(arguments)
        elif tool.name in ("bash", "sh"):
            command = self._build_bash_argv(arguments)
        else:
            command = self._build_generic_argv(tool, arguments)

        return await self.execute_command_argv(
            command=command,
            agent_id=agent_id,
            timeout=arguments.get("timeout", 60),
            working_dir=arguments.get("working_dir"),
        )

    def _build_python_argv(self, arguments: Dict[str, Any]) -> List[str]:
        """Build Python command as argv."""
        script = arguments.get("script", "")
        args = arguments.get("args", [])
        if script:
            return ["python3", "-c", script] + [str(a) for a in args]
        return ["python3"]

    def _build_bash_argv(self, arguments: Dict[str, Any]) -> List[str]:
        """Build Bash command as argv."""
        script = arguments.get("script", "")
        if script:
            return ["bash", "-c", script]
        return ["bash"]

    def _build_generic_argv(self, tool: ToolWrapper, arguments: Dict[str, Any]) -> List[str]:
        """Build generic command as argv."""
        args = arguments.get("args", [])
        return [tool.binary] + [str(a) for a in args]

    async def execute_command_argv(
        self,
        command: List[str],
        agent_id: str,
        timeout: int = 60,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ToolResult:
        """Execute a command as argv list (NO shell)."""
        start_time = time.time()

        # Prepare environment
        exec_env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/home/ctf",
            "USER": "ctf",
        }
        if env:
            exec_env.update(env)

        # Prepare working directory
        cwd = Path(working_dir) if working_dir else Path("/workspace")
        cwd.mkdir(parents=True, exist_ok=True)

        try:
            # Execute command with argv (NO shell)
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=exec_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
                exit_code = process.returncode
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return ToolResult(
                    tool_name="execute_command",
                    success=False,
                    stdout="",
                    stderr=f"Command timed out after {timeout} seconds",
                    exit_code=-1,
                    execution_time=time.time() - start_time,
                    error=f"Timeout after {timeout}s",
                )

            execution_time = time.time() - start_time

            # Store stdout/stderr as artifacts if significant
            artifacts = []
            if stdout and len(stdout) > 100:
                artifact_id = await self.artifact_manager.store(
                    content=stdout.decode("utf-8", errors="replace"),
                    filename=f"stdout_{agent_id}_{int(time.time())}.txt",
                    metadata={"agent_id": agent_id, "command": " ".join(command), "type": "stdout"},
                )
                artifacts.append(artifact_id)

            if stderr and len(stderr) > 100:
                artifact_id = await self.artifact_manager.store(
                    content=stderr.decode("utf-8", errors="replace"),
                    filename=f"stderr_{agent_id}_{int(time.time())}.txt",
                    metadata={"agent_id": agent_id, "command": " ".join(command), "type": "stderr"},
                )
                artifacts.append(artifact_id)

            return ToolResult(
                tool_name="execute_command",
                success=exit_code == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=exit_code,
                execution_time=execution_time,
                artifacts=artifacts,
            )

        except Exception as e:
            return ToolResult(
                tool_name="execute_command",
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def install_tool(self, tool_name: str, agent_id: str) -> ToolResult:
        """Install a tool via permission manager."""
        if not self.permission_client:
            return ToolResult(
                tool_name="install_tool",
                success=False,
                error="Permission client not available",
            )

        tool = self.registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name="install_tool",
                success=False,
                error=f"Tool '{tool_name}' not in registry",
            )

        # Request installation via permission manager
        result = await self.permission_client.request(
            agent_id=agent_id,
            operation="INSTALL_PACKAGE",
            reason=f"Install {tool_name} for agent execution",
            parameters={
                "package_name": tool_name,
                "package_manager": "apt",
            },
        )

        return ToolResult(
            tool_name="install_tool",
            success=result.get("success", False),
            stdout=result.get("output", ""),
            stderr=result.get("error", ""),
            metadata=result,
        )


# Global execution engine
_execution_engine: Optional[ExecutionEngine] = None


async def get_execution_engine() -> ExecutionEngine:
    """Get global execution engine."""
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = ExecutionEngine()
        await _execution_engine.initialize()
    return _execution_engine