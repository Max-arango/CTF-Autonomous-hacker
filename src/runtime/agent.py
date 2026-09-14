"""Agent definition and state management"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field


class AgentState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ResourceBudget:
    max_tokens: int = 100000
    max_time_seconds: int = 300
    max_sub_agents: int = 4
    max_commands: int = 100
    max_memory_mb: int = 2048
    max_cpu_percent: float = 100.0

    # Tracking
    tokens_used: int = 0
    time_used_seconds: float = 0.0
    sub_agents_created: int = 0
    commands_executed: int = 0

    def can_spawn_sub_agent(self) -> bool:
        return self.sub_agents_created < self.max_sub_agents

    def can_execute_command(self) -> bool:
        return self.commands_executed < self.max_commands

    def can_use_tokens(self, estimated_tokens: int) -> bool:
        return self.tokens_used + estimated_tokens <= self.max_tokens

    def record_tokens(self, tokens: int):
        self.tokens_used += tokens

    def record_time(self, seconds: float):
        self.time_used_seconds += seconds

    def record_sub_agent(self):
        self.sub_agents_created += 1

    def record_command(self):
        self.commands_executed += 1

    def is_exhausted(self) -> bool:
        return (
            self.tokens_used >= self.max_tokens
            or self.time_used_seconds >= self.max_time_seconds
            or self.sub_agents_created >= self.max_sub_agents
            or self.commands_executed >= self.max_commands
        )

    def get_usage_ratio(self) -> float:
        ratios = [
            self.tokens_used / self.max_tokens if self.max_tokens > 0 else 0,
            self.time_used_seconds / self.max_time_seconds if self.max_time_seconds > 0 else 0,
            self.sub_agents_created / self.max_sub_agents if self.max_sub_agents > 0 else 0,
            self.commands_executed / self.max_commands if self.max_commands > 0 else 0,
        ]
        return max(ratios)


class AgentConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str
    name: str
    description: str = ""
    parent_id: Optional[str] = None
    depth: int = 0
    objective: str = ""
    scope: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    allowed_files: List[str] = Field(default_factory=list)
    allowed_networks: List[str] = Field(default_factory=list)
    resource_budget: ResourceBudget = Field(default_factory=ResourceBudget)
    timeout_seconds: int = 300
    token_budget: int = 100000
    system_prompt: str = ""
    capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Agent(BaseModel):
    """Agent with full lifecycle management."""

    config: AgentConfig
    state: AgentState = AgentState.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Execution tracking
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)  # Evidence IDs
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    child_agents: List[str] = Field(default_factory=list)  # Child agent IDs
    executed_commands: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts_created: List[str] = Field(default_factory=list)

    # Results
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def transition_to(self, new_state: AgentState) -> bool:
        """Transition to a new state with validation."""
        valid_transitions = {
            AgentState.CREATED: [AgentState.PLANNING, AgentState.FAILED, AgentState.CANCELLED],
            AgentState.PLANNING: [AgentState.EXECUTING, AgentState.FAILED, AgentState.CANCELLED],
            AgentState.EXECUTING: [AgentState.WAITING, AgentState.VALIDATING, AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED],
            AgentState.WAITING: [AgentState.EXECUTING, AgentState.VALIDATING, AgentState.FAILED, AgentState.CANCELLED],
            AgentState.VALIDATING: [AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED],
            AgentState.COMPLETED: [],
            AgentState.FAILED: [],
            AgentState.CANCELLED: [],
        }

        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
            self.updated_at = datetime.utcnow()

            if new_state == AgentState.EXECUTING and self.started_at is None:
                self.started_at = datetime.utcnow()
            elif new_state in (AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED):
                self.completed_at = datetime.utcnow()

            return True
        return False

    def add_finding(self, finding: Dict[str, Any]):
        """Add a finding."""
        finding["timestamp"] = datetime.utcnow().isoformat()
        finding["agent_id"] = self.config.id
        self.findings.append(finding)
        self.updated_at = datetime.utcnow()

    def add_hypothesis(self, hypothesis: Dict[str, Any]):
        """Add a hypothesis."""
        hypothesis["timestamp"] = datetime.utcnow().isoformat()
        hypothesis["agent_id"] = self.config.id
        self.hypotheses.append(hypothesis)
        self.updated_at = datetime.utcnow()

    def add_evidence(self, evidence_id: str):
        """Add evidence reference."""
        if evidence_id not in self.evidence:
            self.evidence.append(evidence_id)
            self.updated_at = datetime.utcnow()

    def add_child_agent(self, child_id: str):
        """Add child agent reference."""
        if child_id not in self.child_agents:
            self.child_agents.append(child_id)
            self.config.resource_budget.record_sub_agent()
            self.updated_at = datetime.utcnow()

    def record_command(self, command: Dict[str, Any]):
        """Record an executed command."""
        command["timestamp"] = datetime.utcnow().isoformat()
        command["agent_id"] = self.config.id
        self.executed_commands.append(command)
        self.config.resource_budget.record_command()
        self.updated_at = datetime.utcnow()

    def add_artifact(self, artifact_id: str):
        """Add artifact reference."""
        if artifact_id not in self.artifacts_created:
            self.artifacts_created.append(artifact_id)
            self.updated_at = datetime.utcnow()

    def set_result(self, result: Dict[str, Any]):
        """Set final result."""
        self.final_result = result
        self.updated_at = datetime.utcnow()

    def set_error(self, error: str):
        """Set error."""
        self.error = error
        self.updated_at = datetime.utcnow()

    def get_summary(self) -> Dict[str, Any]:
        """Get agent summary."""
        return {
            "id": self.config.id,
            "role": self.config.role,
            "name": self.config.name,
            "state": self.state.value,
            "depth": self.config.depth,
            "objective": self.config.objective,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "findings_count": len(self.findings),
            "hypotheses_count": len(self.hypotheses),
            "evidence_count": len(self.evidence),
            "child_agents_count": len(self.child_agents),
            "commands_executed": len(self.executed_commands),
            "artifacts_created": len(self.artifacts_created),
            "resource_usage": {
                "tokens_used": self.config.resource_budget.tokens_used,
                "time_used_seconds": self.config.resource_budget.time_used_seconds,
                "sub_agents_created": self.config.resource_budget.sub_agents_created,
                "commands_executed": self.config.resource_budget.commands_executed,
                "usage_ratio": self.config.resource_budget.get_usage_ratio(),
            },
            "has_result": self.final_result is not None,
            "has_error": self.error is not None,
        }