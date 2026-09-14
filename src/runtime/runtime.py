"""Agent Runtime - Core execution engine"""
import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from .agent import Agent, AgentState, AgentConfig, ResourceBudget
from ..llm import get_llm_provider, LLMMessage, MessageRole, LLMConfig
from ..config.settings import get_settings
from ..memory import MemoryManager, get_memory_manager
from ..execution import ExecutionEngine, get_execution_engine
from ..evidence import EvidenceEngine, get_evidence_engine
from ..artifacts import ArtifactManager, get_artifact_manager
from ..observability import get_logger, log_agent_event


@dataclass
class AgentContext:
    """Runtime context for agent execution."""
    agent: Agent
    memory: MemoryManager
    execution: "ExecutionEngine"
    evidence: EvidenceEngine
    artifacts: ArtifactManager
    llm_provider: Any
    parent_context: Optional["AgentContext"] = None
    child_contexts: List["AgentContext"] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False


class AgentRuntime:
    """Main agent runtime for executing agents."""

    def __init__(
        self,
        max_depth: int = 4,
        max_active_agents: int = 32,
        default_timeout: int = 300,
    ):
        self.max_depth = max_depth
        self.max_active_agents = max_active_agents
        self.default_timeout = default_timeout

        self._active_agents: Dict[str, AgentContext] = {}
        self._agent_counter = 0
        self._lock = asyncio.Lock()

        # Callbacks
        self.on_agent_start: Optional[Callable[[Agent], Awaitable[None]]] = None
        self.on_agent_complete: Optional[Callable[[Agent], Awaitable[None]]] = None
        self.on_agent_error: Optional[Callable[[Agent, Exception], Awaitable[None]]] = None
        self.on_sub_agent_spawn: Optional[Callable[[Agent, Agent], Awaitable[None]]] = None

    async def create_agent(
        self,
        role: str,
        name: str,
        objective: str,
        parent_agent: Optional[Agent] = None,
        system_prompt: str = "",
        capabilities: Optional[List[str]] = None,
        allowed_tools: Optional[List[str]] = None,
        allowed_networks: Optional[List[str]] = None,
        resource_budget: Optional[ResourceBudget] = None,
        timeout_seconds: Optional[int] = None,
        token_budget: Optional[int] = None,
    ) -> Agent:
        """Create a new agent."""
        async with self._lock:
            if len(self._active_agents) >= self.max_active_agents:
                raise RuntimeError(f"Max active agents ({self.max_active_agents}) reached")

            depth = 0
            if parent_agent:
                depth = parent_agent.config.depth + 1
                if depth > self.max_depth:
                    raise RuntimeError(f"Max agent depth ({self.max_depth}) exceeded")

            config = AgentConfig(
                id=str(uuid.uuid4()),
                role=role,
                name=name,
                parent_id=parent_agent.config.id if parent_agent else None,
                depth=depth,
                objective=objective,
                system_prompt=system_prompt,
                capabilities=capabilities or [],
                allowed_tools=allowed_tools or [],
                allowed_networks=allowed_networks or [],
                resource_budget=resource_budget or ResourceBudget(
                    max_tokens=token_budget or self.default_timeout * 100,
                    max_time_seconds=timeout_seconds or self.default_timeout,
                ),
                timeout_seconds=timeout_seconds or self.default_timeout,
                token_budget=token_budget or self.default_timeout * 100,
            )

            agent = Agent(config=config)
            return agent

    async def spawn_agent(self, agent: Agent, parent_context: Optional[AgentContext] = None) -> AgentContext:
        """Spawn an agent with full runtime context."""
        # Get shared services
        memory = await get_memory_manager()
        execution = await get_execution_engine()
        evidence = await get_evidence_engine()
        artifacts = await get_artifact_manager()
        llm_provider = await get_llm_provider()

        context = AgentContext(
            agent=agent,
            memory=memory,
            execution=execution,
            evidence=evidence,
            artifacts=artifacts,
            llm_provider=llm_provider,
            parent_context=parent_context,
        )

        async with self._lock:
            self._active_agents[agent.config.id] = context
            self._agent_counter += 1

        if parent_context:
            parent_context.child_contexts.append(context)

        # Log agent spawn
        await log_agent_event(
            agent_id=agent.config.id,
            event="agent_spawned",
            data={
                "role": agent.config.role,
                "name": agent.config.name,
                "objective": agent.config.objective,
                "depth": agent.config.depth,
                "parent_id": agent.config.parent_id,
            },
        )

        # Callbacks
        if self.on_agent_start:
            await self.on_agent_start(agent)

        return context

    async def execute_agent(self, context: AgentContext) -> Agent:
        """Execute an agent to completion."""
        agent = context.agent

        try:
            # Transition to planning
            agent.transition_to(AgentState.PLANNING)

            # Generate plan
            plan = await self._generate_plan(context)
            agent.config.metadata["plan"] = plan

            # Transition to executing
            agent.transition_to(AgentState.EXECUTING)

            # Execute plan
            await self._execute_plan(context, plan)

            # Transition to validating
            agent.transition_to(AgentState.VALIDATING)

            # Validate results
            validation = await self._validate_results(context)
            agent.config.metadata["validation"] = validation

            # Complete
            agent.transition_to(AgentState.COMPLETED)
            agent.set_result({
                "status": "success",
                "plan": plan,
                "validation": validation,
                "findings": agent.findings,
                "evidence": agent.evidence,
            })

        except asyncio.CancelledError:
            agent.transition_to(AgentState.CANCELLED)
            agent.set_error("Agent cancelled")
            raise
        except Exception as e:
            agent.transition_to(AgentState.FAILED)
            agent.set_error(str(e))

            await log_agent_event(
                agent_id=agent.config.id,
                event="agent_failed",
                data={"error": str(e)},
            )

            if self.on_agent_error:
                await self.on_agent_error(agent, e)

            raise
        finally:
            # Cleanup
            async with self._lock:
                self._active_agents.pop(agent.config.id, None)

            await log_agent_event(
                agent_id=agent.config.id,
                event="agent_completed",
                data={
                    "state": agent.state.value,
                    "duration_seconds": (
                        (agent.completed_at - agent.started_at).total_seconds()
                        if agent.started_at and agent.completed_at
                        else 0
                    ),
                    "findings": len(agent.findings),
                    "evidence": len(agent.evidence),
                },
            )

            if self.on_agent_complete:
                await self.on_agent_complete(agent)

        return agent

    async def _generate_plan(self, context: AgentContext) -> Dict[str, Any]:
        """Generate execution plan using LLM."""
        agent = context.agent

        system_prompt = agent.config.system_prompt or self._get_default_system_prompt(agent.config.role)
        user_prompt = f"""Objective: {agent.config.objective}

Available tools: {', '.join(agent.config.allowed_tools) if agent.config.allowed_tools else 'All tools allowed'}
Allowed networks: {', '.join(agent.config.allowed_networks) if agent.config.allowed_networks else 'Default networks only'}

Create a detailed execution plan with:
1. Steps to achieve the objective
2. Tools to use for each step
3. Expected outputs/evidence for each step
4. Termination conditions

Return as JSON with keys: steps, tools_per_step, expected_evidence, termination_conditions"""

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system_prompt),
            LLMMessage(role=MessageRole.USER, content=user_prompt),
        ]

        response = await context.llm_provider.complete(messages)

        try:
            import json
            plan = json.loads(response.content)
        except:
            plan = {
                "steps": [response.content],
                "tools_per_step": [agent.config.allowed_tools],
                "expected_evidence": [],
                "termination_conditions": ["Objective achieved or max resources reached"],
            }

        return plan

    async def _execute_plan(self, context: AgentContext, plan: Dict[str, Any]):
        """Execute the plan step by step."""
        agent = context.agent
        steps = plan.get("steps", [])
        tools_per_step = plan.get("tools_per_step", [])

        for i, step in enumerate(steps):
            if context.cancelled:
                raise asyncio.CancelledError()

            if agent.config.resource_budget.is_exhausted():
                raise RuntimeError("Resource budget exhausted")

            tools = tools_per_step[i] if i < len(tools_per_step) else agent.config.allowed_tools

            # Execute step
            await self._execute_step(context, step, tools)

    async def _execute_step(self, context: AgentContext, step: str, allowed_tools: List[str]):
        """Execute a single step."""
        agent = context.agent

        # This is where the actual tool execution happens
        # For now, we'll use the LLM to determine tool usage
        system_prompt = f"""You are executing a step: {step}

Available tools: {', '.join(allowed_tools)}

Execute this step by calling appropriate tools. Return the tool calls needed."""

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system_prompt),
            LLMMessage(role=MessageRole.USER, content=f"Execute step: {step}"),
        ]

        response = await context.llm_provider.complete(
            messages,
            tools=self._get_tool_definitions(allowed_tools),
        )

        if response.tool_calls:
            for tool_call in response.tool_calls:
                await self._execute_tool_call(context, tool_call)

    async def _execute_tool_call(self, context: AgentContext, tool_call: Dict[str, Any]):
        """Execute a tool call."""
        agent = context.agent
        function_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]

        import json
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except:
            args = {}

        # Execute through execution engine
        result = await context.execution.execute_tool(
            tool_name=function_name,
            arguments=args,
            agent_id=agent.config.id,
            allowed_tools=agent.config.allowed_tools,
        )

        # Record command
        agent.record_command({
            "tool": function_name,
            "arguments": args,
            "result": result,
        })

        return result

    async def _validate_results(self, context: AgentContext) -> Dict[str, Any]:
        """Validate agent results."""
        agent = context.agent

        # Submit findings to evidence engine for verification
        validation_results = []
        for finding in agent.findings:
            if finding.get("type") in ("observation", "hypothesis", "evidence", "exploit", "proof"):
                evidence_result = await context.evidence.verify_claim(
                    claim=finding,
                    agent_id=agent.config.id,
                )
                validation_results.append({
                    "finding_id": finding.get("id"),
                    "verification": evidence_result,
                })

        return {
            "validated_findings": len([v for v in validation_results if v["verification"].status == "VERIFIED"]),
            "total_findings": len(validation_results),
            "details": validation_results,
        }

    def _get_default_system_prompt(self, role: str) -> str:
        """Get default system prompt for role."""
        return f"""You are a {role} specialist agent in an autonomous CTF environment.
Your role is to {self._get_role_description(role)}.

Follow these principles:
1. Be systematic and evidence-driven
2. Document all findings with supporting evidence
3. Use tools efficiently and within scope
4. Report failures and dead ends
5. Create sub-agents for independent sub-tasks when needed"""

    def _get_role_description(self, role: str) -> str:
        descriptions = {
            "orchestrator": "coordinate challenge solving across specialist agents",
            "web": "perform web application security testing",
            "crypto": "analyze and exploit cryptographic implementations",
            "pwn": "exploit binary vulnerabilities and memory corruption",
            "reverse": "reverse engineer binaries and analyze code",
            "forensics": "analyze digital artifacts and forensic images",
            "osint": "gather open source intelligence",
            "stego": "detect and extract hidden data",
            "mobile": "analyze mobile applications",
            "malware": "analyze malicious software",
            "cloud": "test cloud infrastructure security",
            "network": "analyze network protocols and services",
            "supply_chain": "analyze software supply chain security",
            "ad": "test Active Directory environments",
            "web3": "audit smart contracts and blockchain systems",
            "ai_security": "test AI/ML model security",
            "sidechannel": "perform side-channel analysis",
            "firmware": "analyze firmware and embedded systems",
            "social": "simulate social engineering attacks",
            "programming": "develop scripts, tools, and exploits",
            "meta": "apply CTF-specific strategies and patterns",
        }
        return descriptions.get(role, "perform security analysis")

    def _get_tool_definitions(self, allowed_tools: List[str]) -> List[Dict[str, Any]]:
        """Get tool definitions for LLM function calling."""
        # This would be populated from the tool registry
        # For now, return basic definitions
        tool_defs = {
            "execute_command": {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Execute a shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Command to execute"},
                            "timeout": {"type": "integer", "description": "Timeout in seconds"},
                            "working_dir": {"type": "string", "description": "Working directory"},
                        },
                        "required": ["command"],
                    },
                },
            },
            "read_file": {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                        },
                        "required": ["path"],
                    },
                },
            },
            "write_file": {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "content": {"type": "string", "description": "File content"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
        }

        return [tool_defs.get(t, {}) for t in allowed_tools if t in tool_defs]

    async def cancel_agent(self, agent_id: str):
        """Cancel a running agent."""
        async with self._lock:
            context = self._active_agents.get(agent_id)
            if context:
                context.cancelled = True

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        async with self._lock:
            context = self._active_agents.get(agent_id)
            return context.agent if context else None

    async def list_active_agents(self) -> List[Dict[str, Any]]:
        """List all active agents."""
        async with self._lock:
            return [ctx.agent.get_summary() for ctx in self._active_agents.values()]

    async def shutdown(self):
        """Shutdown runtime and cancel all agents."""
        async with self._lock:
            for context in self._active_agents.values():
                context.cancelled = True
            self._active_agents.clear()


# Global runtime instance
_runtime: Optional[AgentRuntime] = None


async def get_agent_runtime() -> AgentRuntime:
    """Get or create global agent runtime."""
    global _runtime
    settings = get_settings()

    if _runtime is None:
        _runtime = AgentRuntime(
            max_depth=settings.agent_runtime.max_agent_depth,
            max_active_agents=settings.agent_runtime.max_active_agents,
            default_timeout=settings.agent_runtime.default_timeout,
        )

    return _runtime