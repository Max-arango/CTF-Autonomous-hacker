"""Security Module - Capability-based authorization and scope enforcement"""
from .capabilities import Capability, CapabilityRegistry, get_capability_registry
from .scope import ChallengeScope, ScopeEngine, get_scope_engine
from .policy import PolicyEngine, PolicyDecision, get_policy_engine
from .authorization import AuthorizationContext, get_authorization_context
from .schemas import ToolSchema, ToolArgumentSchema, get_tool_schema_registry
from .secrets import CredentialRef, SecretManager, get_secret_manager

__all__ = [
    "Capability",
    "CapabilityRegistry",
    "get_capability_registry",
    "ChallengeScope",
    "ScopeEngine",
    "get_scope_engine",
    "PolicyEngine",
    "PolicyDecision",
    "get_policy_engine",
    "AuthorizationContext",
    "get_authorization_context",
    "ToolSchema",
    "ToolArgumentSchema",
    "get_tool_schema_registry",
    "CredentialRef",
    "SecretManager",
    "get_secret_manager",
]