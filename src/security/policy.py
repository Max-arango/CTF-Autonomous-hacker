"""Policy Engine - Central authorization decision point"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import logging

from .capabilities import Capability, CapabilityDefinition, get_capability_registry
from .scope import ScopeEngine, get_scope_engine, ChallengeScope

logger = logging.getLogger(__name__)


class PolicyDecision(str, Enum):
    """Possible policy decisions."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    CONDITIONAL = "conditional"  # Allow with conditions


@dataclass
class PolicyContext:
    """Context for a policy decision."""
    agent_id: str
    agent_role: str
    challenge_id: str
    action: str  # What the agent wants to do
    capability: Capability  # Required capability
    parameters: Dict[str, Any] = field(default_factory=dict)
    target: Optional[str] = None  # Target host/IP for network actions
    port: Optional[int] = None
    protocol: str = "tcp"
    path: Optional[str] = None  # Target path for filesystem actions
    operation: Optional[str] = None  # read/write for filesystem
    tool: Optional[str] = None  # Tool being used
    resource_request: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyDecisionResult:
    """Result of a policy evaluation."""
    decision: PolicyDecision
    capability: Capability
    reason: str
    conditions: Dict[str, Any] = field(default_factory=dict)
    required_approvals: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW
    
    @property
    def requires_approval(self) -> bool:
        return self.decision == PolicyDecision.REQUIRE_APPROVAL


class PolicyEngine:
    """Central policy evaluation engine."""
    
    def __init__(self):
        self.capability_registry = get_capability_registry()
        self.scope_engine = get_scope_engine()
        self._policy_overrides: Dict[str, PolicyDecision] = {}  # For emergency overrides
    
    def evaluate(self, context: PolicyContext) -> PolicyDecisionResult:
        """
        Evaluate a policy decision.
        
        Decision flow:
        1. Check emergency overrides
        2. Check capability exists and is allowed for agent role
        3. Check capability-specific constraints (approval, rate limits)
        4. Check scope constraints (network, filesystem, resources, tools)
        5. Return decision
        """
        capability = context.capability
        
        # 1. Emergency override check
        override_key = f"{context.agent_role}:{capability.value}"
        if override_key in self._policy_overrides:
            return PolicyDecisionResult(
                decision=self._policy_overrides[override_key],
                capability=capability,
                reason=f"Emergency override: {override_key}",
                metadata={"override": True}
            )
        
        # 2. Get capability definition
        cap_def = self.capability_registry.get(capability)
        if not cap_def:
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason=f"Unknown capability: {capability.value}"
            )
        
        # 3. Check if agent role is allowed this capability
        if not self._is_agent_allowed(cap_def, context.agent_role):
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason=f"Agent role {context.agent_role} not allowed capability {capability.value}"
            )
        
        # 4. Check if approval required
        if cap_def.requires_approval:
            return PolicyDecisionResult(
                decision=PolicyDecision.REQUIRE_APPROVAL,
                capability=capability,
                reason=f"Capability {capability.value} requires approval (risk: {cap_def.risk_level})",
                required_approvals=["human_operator"],
                metadata={"risk_level": cap_def.risk_level}
            )
        
        # 5. Check rate limits
        rate_limit_result = self._check_rate_limits(cap_def, context)
        if not rate_limit_result[0]:
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason=rate_limit_result[1]
            )
        
        # 6. Validate against scope
        scope_result = self._validate_scope(cap_def, context)
        if not scope_result[0]:
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason=scope_result[1]
            )
        
        # 7. Check resource limits
        resource_result = self._validate_resources(context)
        if not resource_result[0]:
            return PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                capability=capability,
                reason=resource_result[1]
            )
        
        # 8. All checks passed
        conditions = {}
        if scope_result[1] != "Allowed by scope":
            conditions["scope_notes"] = scope_result[1]
        
        return PolicyDecisionResult(
            decision=PolicyDecision.ALLOW,
            capability=capability,
            reason="Policy evaluation passed",
            conditions=conditions,
            metadata={
                "capability_risk": cap_def.risk_level,
                "agent_role": context.agent_role,
                "challenge_id": context.challenge_id,
            }
        )
    
    def _is_agent_allowed(self, cap_def: CapabilityDefinition, agent_role: str) -> bool:
        """Check if agent role is allowed this capability."""
        return "*" in cap_def.allowed_agent_roles or agent_role in cap_def.allowed_agent_roles
    
    def _check_rate_limits(
        self,
        cap_def: CapabilityDefinition,
        context: PolicyContext
    ) -> tuple[bool, str]:
        """Check capability-specific rate limits."""
        # In a real implementation, this would check a persistent counter
        # For now, we just validate the limit exists
        if cap_def.max_uses_per_challenge is not None:
            # Would check actual usage count here
            pass
        return True, "Rate limit check passed"
    
    def _validate_scope(
        self,
        cap_def: CapabilityDefinition,
        context: PolicyContext
    ) -> tuple[bool, str]:
        """Validate action against challenge scope."""
        scope_engine = self.scope_engine
        
        # Network validation
        if context.target:
            allowed, reason = scope_engine.validate_network_access(
                context.challenge_id,
                context.target,
                context.port,
                context.protocol
            )
            if not allowed:
                return False, reason
        
        # Filesystem validation
        if context.path and context.operation:
            allowed, reason = scope_engine.validate_filesystem_access(
                context.challenge_id,
                context.path,
                context.operation
            )
            if not allowed:
                return False, reason
        
        # Tool validation
        if context.tool:
            allowed, reason = scope_engine.validate_tool_access(
                context.challenge_id,
                context.tool
            )
            if not allowed:
                return False, reason
        
        return True, "Allowed by scope"
    
    def _validate_resources(self, context: PolicyContext) -> tuple[bool, str]:
        """Validate resource requests against scope limits."""
        if not context.resource_request:
            return True, "No resource request"
        
        return self.scope_engine.validate_resource_request(
            context.challenge_id,
            cpu_percent=context.resource_request.get("cpu_percent"),
            memory_mb=context.resource_request.get("memory_mb"),
            processes=context.resource_request.get("processes"),
            open_files=context.resource_request.get("open_files"),
            runtime_seconds=context.resource_request.get("runtime_seconds"),
        )
    
    def set_override(self, agent_role: str, capability: Capability, decision: PolicyDecision):
        """Set emergency policy override."""
        self._policy_overrides[f"{agent_role}:{capability.value}"] = decision
        logger.warning(f"Policy override set: {agent_role}:{capability.value} = {decision.value}")
    
    def clear_override(self, agent_role: str, capability: Capability):
        """Clear emergency policy override."""
        key = f"{agent_role}:{capability.value}"
        if key in self._policy_overrides:
            del self._policy_overrides[key]
            logger.info(f"Policy override cleared: {key}")
    
    def get_agent_capabilities(self, agent_role: str) -> List[CapabilityDefinition]:
        """Get all capabilities available to an agent role."""
        return self.capability_registry.get_for_agent(agent_role)
    
    def get_capability_definition(self, capability: Capability) -> Optional[CapabilityDefinition]:
        """Get capability definition."""
        return self.capability_registry.get(capability)


# Global policy engine
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get global policy engine."""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine