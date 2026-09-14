"""Agent Delegation Manager"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Awaitable
from enum import Enum

from .agent import Agent, AgentConfig, ResourceBudget, AgentState
from .runtime import AgentRuntime, AgentContext, get_agent_runtime


class DelegationReason(str, Enum):
    SPECIALIZED_EXPERTISE = "specialized_expertise"
    PARALLEL_EXECUTION = "parallel_execution"
    INDEPENDENT_SUBTASK = "independent_subtask"
    RESOURCE_ISOLATION = "resource_isolation"
    FAILURE_RECOVERY = "failure_recovery"


@dataclass
class SubAgentSpec:
    """Specification for a sub-agent to be created."""
    role: str
    name: str
    objective: str
    reason: DelegationReason
    expected_evidence: List[str] = field(default_factory=list)
    termination_condition: str = ""
    required_tools: List[str] = field(default_factory=list)
    required_networks: List[str] = field(default_factory=list)
    resource_budget: Optional[ResourceBudget] = None
    timeout_seconds: Optional[int] = None
    system_prompt: str = ""
    capabilities: List[str] = field(default_factory=list)


class DelegationManager:
    """Manages recursive agent delegation."""

    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime
        self._delegation_history: List[Dict[str, Any]] = []

    async def create_sub_agent(
        self,
        parent_context: AgentContext,
        spec: SubAgentSpec,
    ) -> AgentContext:
        """Create and spawn a sub-agent."""
        parent_agent = parent_context.agent

        # Check depth limit
        if parent_agent.config.depth >= self.runtime.max_depth:
            raise RuntimeError(f"Max agent depth ({self.runtime.max_depth}) exceeded")

        # Check resource budget
        if not parent_agent.config.resource_budget.can_spawn_sub_agent():
            raise RuntimeError("Parent agent resource budget exhausted for sub-agents")

        # Create agent config
        resource_budget = spec.resource_budget or ResourceBudget(
            max_tokens=spec.timeout_seconds * 100 if spec.timeout_seconds else 50000,
            max_time_seconds=spec.timeout_seconds or 300,
            max_sub_agents=2,  # Sub-agents can have fewer sub-agents
            max_commands=50,
        )

        agent = await self.runtime.create_agent(
            role=spec.role,
            name=spec.name,
            objective=spec.objective,
            parent_agent=parent_agent,
            system_prompt=spec.system_prompt,
            capabilities=spec.capabilities,
            allowed_tools=spec.required_tools,
            allowed_networks=spec.required_networks,
            resource_budget=resource_budget,
            timeout_seconds=spec.timeout_seconds,
        )

        # Spawn with parent context
        child_context = await self.runtime.spawn_agent(agent, parent_context)

        # Record delegation
        delegation_record = {
            "parent_id": parent_agent.config.id,
            "child_id": agent.config.id,
            "reason": spec.reason.value,
            "objective": spec.objective,
            "expected_evidence": spec.expected_evidence,
            "termination_condition": spec.termination_condition,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._delegation_history.append(delegation_record)

        # Add to parent
        parent_agent.add_child_agent(agent.config.id)

        # Callback
        if self.runtime.on_sub_agent_spawn:
            await self.runtime.on_sub_agent_spawn(parent_agent, agent)

        return child_context

    async def execute_delegation(
        self,
        parent_context: AgentContext,
        specs: List[SubAgentSpec],
        parallel: bool = True,
    ) -> List[Agent]:
        """Execute multiple delegations."""
        if parallel:
            # Spawn all first
            child_contexts = []
            for spec in specs:
                child_context = await self.create_sub_agent(parent_context, spec)
                child_contexts.append(child_context)

            # Execute all in parallel
            tasks = [self.runtime.execute_agent(ctx) for ctx in child_contexts]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle results
            completed_agents = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Log failure but continue
                    child_contexts[i].agent.transition_to(AgentState.FAILED)
                    child_contexts[i].agent.set_error(str(result))
                else:
                    completed_agents.append(result)

            return completed_agents
        else:
            # Sequential execution
            completed_agents = []
            for spec in specs:
                child_context = await self.create_sub_agent(parent_context, spec)
                try:
                    agent = await self.runtime.execute_agent(child_context)
                    completed_agents.append(agent)
                except Exception as e:
                    child_context.agent.transition_to(AgentState.FAILED)
                    child_context.agent.set_error(str(e))
            return completed_agents

    def get_delegation_history(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get delegation history."""
        if agent_id:
            return [d for d in self._delegation_history if d["parent_id"] == agent_id or d["child_id"] == agent_id]
        return self._delegation_history

    def should_terminate_branch(self, agent: Agent) -> bool:
        """Determine if a delegation branch should be terminated."""
        # Terminate if:
        # 1. Resource budget exhausted
        if agent.config.resource_budget.is_exhausted():
            return True

        # 2. No new findings in last N steps
        recent_findings = agent.findings[-5:] if len(agent.findings) >= 5 else agent.findings
        if len(recent_findings) == 0 and len(agent.findings) > 0:
            return True

        # 3. All hypotheses tested and failed
        failed_hypotheses = [h for h in agent.hypotheses if h.get("status") == "DISPROVEN"]
        total_hypotheses = len(agent.hypotheses)
        if total_hypotheses > 3 and len(failed_hypotheses) / total_hypotheses > 0.8:
            return True

        # 4. Explicit termination condition met
        if agent.config.metadata.get("termination_condition_met"):
            return True

        return False


# Import asyncio at module level
import asyncio