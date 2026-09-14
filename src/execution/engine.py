"""Execution Engine - Core tool execution"""
import asyncio
import json
import uuid
import shlex
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Awaitable
from pathlib import Path

from ..config.settings import get_settings
from ..config.loader import get_config_manager
from ..artifacts import ArtifactManager, get_artifact_manager
from ..observability import get_logger, log_command_execution
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
    """Base class for tool wrappers."""

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


class CommandWrapper(ToolWrapperBase):
    """Wrapper for direct command execution."""

    def __init__(self, tool_name: str, execution_engine: "ExecutionEngine", command_template: str):
        super().__init__(tool_name, execution_engine)
        self.command_template = command_template

    async def execute(self, arguments: Dict[str, Any], agent_id: str) -> ToolResult:
        """Execute command template with arguments."""
        # Format command
        try:
            command = self.command_template.format(**arguments)
        except KeyError as e:
            return ToolResult(
                tool_name=self.tool_name,
                success=False,
                error=f"Missing argument for command template: {e}",
            )

        return await self.execution_engine.execute_command(
            command=command,
            agent_id=agent_id,
            timeout=arguments.get("timeout", self.get_timeout(arguments)),
            working_dir=arguments.get("working_dir"),
        )


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

    def is_available_for_agent(self, agent_role: str) -> bool:
        """Check if tool is available for agent role."""
        return "*" in self.supported_agents or agent_role in self.supported_agents


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._tools: Dict[str, ToolWrapper] = {}
        self._wrappers: Dict[str, ToolWrapperBase] = {}
        self._load_config()

    def _load_config(self):
        """Load tool configuration."""
        config_manager = get_config_manager()
        tools_config = config_manager.get("tools", {})

        for category, tools in tools_config.items():
            if isinstance(tools, list):
                for tool_config in tools:
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
    """Main execution engine for tool execution."""

    def __init__(self):
        self.settings = get_settings()
        self.registry = ToolRegistry()
        self.artifact_manager: Optional[ArtifactManager] = None
        self.permission_client: Optional[PermissionClient] = None

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
        """Register built-in tool wrappers."""
        # These would be specialized wrappers for each tool
        # For now, we use the generic command wrapper
        pass

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: str,
        allowed_tools: Optional[List[str]] = None,
    ) -> ToolResult:
        """Execute a tool."""
        start_time = time.time()

        # Check if tool is allowed
        if allowed_tools and tool_name not in allowed_tools and "*" not in allowed_tools:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not allowed for this agent",
            )

        # Get tool info
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found in registry",
            )

        # Check if agent role is supported
        # (would need agent role from agent_id)

        # Run pre-execution hooks
        for hook in self.pre_execution_hooks:
            await hook(tool_name, arguments, agent_id)

        # Execute
        try:
            if tool.wrapper:
                result = await tool.wrapper.execute(arguments, agent_id)
            else:
                # Generic command execution
                result = await self._execute_generic(tool, arguments, agent_id)
        except Exception as e:
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

        result.execution_time = time.time() - start_time

        # Run post-execution hooks
        for hook in self.post_execution_hooks:
            await hook(result)

        # Log execution
        await log_command_execution(
            agent_id=agent_id,
            tool=tool_name,
            arguments=arguments,
            result=result,
        )

        return result

    async def _execute_generic(
        self,
        tool: ToolWrapper,
        arguments: Dict[str, Any],
        agent_id: str,
    ) -> ToolResult:
        """Execute tool generically via command line."""
        # Build command based on tool and arguments
        if tool.name in ("python3", "python"):
            command = self._build_python_command(arguments)
        elif tool.name in ("bash", "sh"):
            command = self._build_bash_command(arguments)
        else:
            command = self._build_generic_command(tool, arguments)

        return await self.execute_command(
            command=command,
            agent_id=agent_id,
            timeout=arguments.get("timeout", 60),
            working_dir=arguments.get("working_dir"),
        )

    def _build_python_command(self, arguments: Dict[str, Any]) -> str:
        """Build Python command."""
        script = arguments.get("script", "")
        args = arguments.get("args", [])
        if script:
            return f"python3 -c {shlex.quote(script)} {' '.join(shlex.quote(a) for a in args)}"
        return "python3"

    def _build_bash_command(self, arguments: Dict[str, Any]) -> str:
        """Build bash command."""
        script = arguments.get("script", "")
        if script:
            return f"bash -c {shlex.quote(script)}"
        return "bash"

    def _build_generic_command(self, tool: ToolWrapper, arguments: Dict[str, Any]) -> str:
        """Build generic command."""
        args = arguments.get("args", [])
        return f"{tool.binary} {' '.join(shlex.quote(str(a)) for a in args)}"

    async def execute_command(
        self,
        command: str,
        agent_id: str,
        timeout: int = 60,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ToolResult:
        """Execute a raw command."""
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
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
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
                    metadata={"agent_id": agent_id, "command": command, "type": "stdout"},
                )
                artifacts.append(artifact_id)

            if stderr and len(stderr) > 100:
                artifact_id = await self.artifact_manager.store(
                    content=stderr.decode("utf-8", errors="replace"),
                    filename=f"stderr_{agent_id}_{int(time.time())}.txt",
                    metadata={"agent_id": agent_id, "command": command, "type": "stderr"},
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
                "package_manager": "apt",  # Would be determined from tool config
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