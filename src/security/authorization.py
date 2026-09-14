"""Authorization Context - Runtime authorization for agent actions"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import uuid

from .capabilities import Capability, get_capability_registry
from .scope import ChallengeScope, get_scope_engine
from .policy import PolicyEngine, PolicyContext, PolicyDecisionResult, get_policy_engine


@dataclass
class AuthorizationContext:
    """
    Runtime authorization context for an agent.
    Contains all capabilities, scope, and budget information.
    """
    agent_id: str
    agent_role: str
    challenge_id: str
    parent_agent_id: Optional[str] = None
    depth: int = 0
    
    # Capabilities granted to this agent
    granted_capabilities: Set[Capability] = field(default_factory=set)
    
    # Scope for this challenge
    scope: Optional[ChallengeScope] = None
    
    # Resource budget (inherited from parent or root)
    token_budget: int = 100000
    tokens_used: int = 0
    time_budget_seconds: int = 3600
    time_used_seconds: float = 0.0
    sub_agent_budget: int = 4
    sub_agents_created: int = 0
    command_budget: int = 100
    commands_executed: int = 0
    
    # Network allowances (derived from scope)
    allowed_networks: List[str] = field(default_factory=list)
    allowed_ports: List[int] = field(default_factory=list)
    
    # Filesystem allowances (derived from scope)
    allowed_read_paths: List[str] = field(default_factory=list)
    allowed_write_paths: List[str] = field(default_factory=list)
    
    # Tool allowances (derived from scope + capabilities)
    allowed_tools: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_spawn_sub_agent(self) -> bool:
        """Check if agent can spawn a sub-agent."""
        return self.sub_agents_created < self.sub_agent_budget
    
    def can_execute_command(self) -> bool:
        """Check if agent can execute a command."""
        return self.commands_executed < self.command_budget
    
    def can_use_tokens(self, estimated_tokens: int) -> bool:
        """Check if agent has token budget."""
        return self.tokens_used + estimated_tokens <= self.token_budget
    
    def record_tokens(self, tokens: int):
        """Record token usage."""
        self.tokens_used += tokens
    
    def record_time(self, seconds: float):
        """Record time usage."""
        self.time_used_seconds += seconds
    
    def record_sub_agent(self):
        """Record sub-agent creation."""
        self.sub_agents_created += 1
    
    def record_command(self):
        """Record command execution."""
        self.commands_executed += 1
    
    def get_usage_ratio(self) -> float:
        """Get overall resource usage ratio (0-1)."""
        ratios = [
            self.tokens_used / self.token_budget if self.token_budget > 0 else 0,
            self.time_used_seconds / self.time_budget_seconds if self.time_budget_seconds > 0 else 0,
            self.sub_agents_created / self.sub_agent_budget if self.sub_agent_budget > 0 else 0,
            self.commands_executed / self.command_budget if self.command_budget > 0 else 0,
        ]
        return max(ratios) if ratios else 0.0
    
    def is_exhausted(self) -> bool:
        """Check if any resource budget is exhausted."""
        return (
            self.tokens_used >= self.token_budget
            or self.time_used_seconds >= self.time_budget_seconds
            or self.sub_agents_created >= self.sub_agent_budget
            or self.commands_executed >= self.command_budget
        )
    
    def has_capability(self, capability: Capability) -> bool:
        """Check if agent has a capability."""
        return capability in self.granted_capabilities
    
    def get_budget_summary(self) -> Dict[str, Any]:
        """Get budget usage summary."""
        return {
            "tokens": {"used": self.tokens_used, "budget": self.token_budget, "ratio": self.tokens_used / self.token_budget if self.token_budget > 0 else 0},
            "time": {"used": self.time_used_seconds, "budget": self.time_budget_seconds, "ratio": self.time_used_seconds / self.time_budget_seconds if self.time_budget_seconds > 0 else 0},
            "sub_agents": {"used": self.sub_agents_created, "budget": self.sub_agent_budget, "ratio": self.sub_agents_created / self.sub_agent_budget if self.sub_agent_budget > 0 else 0},
            "commands": {"used": self.commands_executed, "budget": self.command_budget, "ratio": self.commands_executed / self.command_budget if self.command_budget > 0 else 0},
            "overall_ratio": self.get_usage_ratio(),
            "exhausted": self.is_exhausted(),
        }


class AuthorizationManager:
    """Manages authorization contexts for agents."""
    
    def __init__(self):
        self._contexts: Dict[str, AuthorizationContext] = {}
        self.capability_registry = get_capability_registry()
        self.policy_engine = get_policy_engine()
        self.scope_engine = get_scope_engine()
    
    def create_context(
        self,
        agent_id: str,
        agent_role: str,
        challenge_id: str,
        parent_context: Optional[AuthorizationContext] = None,
        depth: int = 0,
        custom_budget: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationContext:
        """Create authorization context for an agent."""
        
        # Get challenge scope
        scope = self.scope_engine.get_scope(challenge_id)
        
        # Determine capabilities for this agent role
        capabilities = set()
        for cap_def in self.capability_registry.get_for_agent(agent_role):
            capabilities.add(cap_def.capability)
        
        # If parent context, inherit and reduce budget
        if parent_context:
            token_budget = min(
                custom_budget.get("token_budget", 50000) if custom_budget else 50000,
                parent_context.token_budget - parent_context.tokens_used
            )
            time_budget = min(
                custom_budget.get("time_budget_seconds", 1800) if custom_budget else 1800,
                int(parent_context.time_budget_seconds - parent_context.time_used_seconds)
            )
            sub_agent_budget = min(
                custom_budget.get("sub_agent_budget", 2) if custom_budget else 2,
                parent_context.sub_agent_budget - parent_context.sub_agents_created
            )
            command_budget = min(
                custom_budget.get("command_budget", 50) if custom_budget else 50,
                parent_context.command_budget - parent_context.commands_executed
            )
        else:
            token_budget = custom_budget.get("token_budget", 100000) if custom_budget else 100000
            time_budget = custom_budget.get("time_budget_seconds", 3600) if custom_budget else 3600
            sub_agent_budget = custom_budget.get("sub_agent_budget", 4) if custom_budget else 4
            command_budget = custom_budget.get("command_budget", 100) if custom_budget else 100
        
        # Create context
        context = AuthorizationContext(
            agent_id=agent_id,
            agent_role=agent_role,
            challenge_id=challenge_id,
            parent_agent_id=parent_context.agent_id if parent_context else None,
            depth=depth,
            granted_capabilities=capabilities,
            scope=scope,
            token_budget=token_budget,
            time_budget_seconds=time_budget,
            sub_agent_budget=sub_agent_budget,
            command_budget=command_budget,
        )
        
        # Populate derived allowances from scope
        if scope:
            context.allowed_networks = [r.cidr for r in scope.allowed_networks]
            context.allowed_ports = scope.allowed_ports
            context.allowed_read_paths = [r.path for r in scope.allowed_paths if r.read]
            context.allowed_write_paths = [r.path for r in scope.allowed_paths if r.write]
            context.allowed_tools = scope.allowed_tools
            context.blocked_tools = scope.blocked_tools
        
        # Store context
        self._contexts[agent_id] = context
        
        return context
    
    def get_context(self, agent_id: str) -> Optional[AuthorizationContext]:
        """Get authorization context for agent."""
        return self._contexts.get(agent_id)
    
    def remove_context(self, agent_id: str):
        """Remove authorization context."""
        self._contexts.pop(agent_id, None)
    
    def authorize_action(
        self,
        agent_id: str,
        action: str,
        capability: Capability,
        **kwargs
    ) -> PolicyDecisionResult:
        """
        Authorize an action for an agent.
        
        This is the main entry point for authorization checks.
        """
        context = self.get_context(agent_id)
        if not context:
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason=f"No authorization context for agent {agent_id}"
            )
        
        # Check if agent has the capability
        if capability not in context.granted_capabilities:
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason=f"Agent {agent_id} not granted capability {capability.value}"
            )
        
        # Check resource budgets
        if capability == Capability.AGENT_SPAWN and not context.can_spawn_sub_agent():
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason="Sub-agent budget exhausted"
            )
        
        if capability in (Capability.EXEC_COMMAND, Capability.EXEC_PYTHON_SCRIPT, Capability.EXEC_BASH_SCRIPT):
            if not context.can_execute_command():
                return PolicyDecisionResult(
                    decision=PolicyDecision.DENY,
                    capability=capability,
                    reason="Command budget exhausted"
                )
        
        # Build policy context
        policy_context = PolicyContext(
            agent_id=agent_id,
            agent_role=context.agent_role,
            challenge_id=context.challenge_id,
            action=action,
            capability=capability,
            target=kwargs.get("target"),
            port=kwargs.get("port"),
            protocol=kwargs.get("protocol", "tcp"),
            path=kwargs.get("path"),
            operation=kwargs.get("operation"),
            tool=kwargs.get("tool"),
            resource_request=kwargs.get("resource_request", {}),
            metadata=kwargs.get("metadata", {}),
        )
        
        # Evaluate policy
        return self.policy_engine.evaluate(policy_context)
    
    def get_agent_budget(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get budget summary for agent."""
        context = self.get_context(agent_id)
        if not context:
            return None
        return context.get_budget_summary()


# Global authorization manager
_authorization_manager: Optional[AuthorizationManager] = None


def get_authorization_context() -> AuthorizationManager:
    """Get global authorization manager."""
    global _authorization_manager
    if _authorization_manager is None:
        _authorization_manager = AuthorizationManager()
    return _authorization_manager