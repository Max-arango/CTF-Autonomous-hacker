"""Resource Governor - Local budget tracking"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session

from .models import ResourceBudget as ResourceBudgetModel, ToolCost


@dataclass
class BudgetSnapshot:
    tokens_used: int
    time_used_seconds: float
    sub_agents_created: int
    commands_executed: int
    llm_calls: int
    
    # Limits
    max_tokens: int
    max_time_seconds: int
    max_sub_agents: int
    max_commands: int
    max_llm_calls: int
    
    @property
    def usage_ratio(self) -> float:
        ratios = [
            self.tokens_used / self.max_tokens if self.max_tokens else 0,
            self.time_used_seconds / self.max_time_seconds if self.max_time_seconds else 0,
            self.sub_agents_created / self.max_sub_agents if self.max_sub_agents else 0,
            self.commands_executed / self.max_commands if self.max_commands else 0,
            self.llm_calls / self.max_llm_calls if self.max_llm_calls else 0,
        ]
        return max(ratios)
    
    @property
    def exhausted(self) -> bool:
        return (
            self.tokens_used >= self.max_tokens or
            self.time_used_seconds >= self.max_time_seconds or
            self.sub_agents_created >= self.max_sub_agents or
            self.commands_executed >= self.max_commands or
            self.llm_calls >= self.max_llm_calls
        )
    
    def can_spawn_sub_agent(self) -> bool:
        return self.sub_agents_created < self.max_sub_agents
    
    def can_execute_command(self) -> bool:
        return self.commands_executed < self.max_commands
    
    def can_use_tokens(self, estimated: int) -> bool:
        return self.tokens_used + estimated <= self.max_tokens
    
    def can_make_llm_call(self) -> bool:
        return self.llm_calls < self.max_llm_calls


class ResourceGovernor:
    """Centralized resource accounting with cascading budgets."""
    
    # Tool cost model (tunable)
    DEFAULT_COSTS = {
        "file": 1, "strings": 1, "checksec": 2, "curl": 2, "nmap": 5,
        "ffuf": 10, "nuclei": 10, "sqlmap": 20, "gdb": 5, "ghidra": 20,
        "radare2": 10, "angr": 50, "binwalk": 5, "volatility3": 30,
        "hashcat": 20, "john": 20, "python_sandbox": 2,
        "execute_python_sandbox": 2,
    }
    
    def __init__(self, session: Session, challenge_id: str):
        self.session = session
        self.challenge_id = challenge_id
        self._budgets: Dict[str, BudgetSnapshot] = {}
        self._load_budgets()
    
    def _load_budgets(self):
        budgets = self.session.query(ResourceBudgetModel).filter_by(
            challenge_id=self.challenge_id
        ).all()
        for b in budgets:
            self._budgets[b.agent_id or "challenge"] = BudgetSnapshot(
                tokens_used=b.tokens_used,
                time_used_seconds=b.time_used_seconds,
                sub_agents_created=b.sub_agents_created,
                commands_executed=b.commands_executed,
                llm_calls=b.llm_calls,
                max_tokens=b.max_tokens,
                max_time_seconds=b.max_time_seconds,
                max_sub_agents=b.max_sub_agents,
                max_commands=b.max_commands,
                max_llm_calls=b.max_llm_calls,
            )
    
    def get_budget(self, agent_id: str) -> BudgetSnapshot:
        if agent_id not in self._budgets:
            # Inherit from challenge budget
            parent = self._budgets.get("challenge", BudgetSnapshot(
                tokens_used=0, time_used_seconds=0, sub_agents_created=0,
                commands_executed=0, llm_calls=0,
                max_tokens=100000, max_time_seconds=300, max_sub_agents=4,
                max_commands=100, max_llm_calls=100,
            ))
            self._budgets[agent_id] = BudgetSnapshot(
                tokens_used=0, time_used_seconds=0, sub_agents_created=0,
                commands_executed=0, llm_calls=0,
                max_tokens=parent.max_tokens, max_time_seconds=parent.max_time_seconds,
                max_sub_agents=parent.max_sub_agents, max_commands=parent.max_commands,
                max_llm_calls=parent.max_llm_calls,
            )
        return self._budgets[agent_id]
    
    def record_tokens(self, agent_id: str, tokens: int):
        budget = self.get_budget(agent_id)
        budget.tokens_used += tokens
        self._persist(agent_id, budget)
    
    def record_time(self, agent_id: str, seconds: float):
        budget = self.get_budget(agent_id)
        budget.time_used_seconds += seconds
        self._persist(agent_id, budget)
    
    def record_sub_agent(self, agent_id: str):
        budget = self.get_budget(agent_id)
        budget.sub_agents_created += 1
        self._persist(agent_id, budget)
    
    def record_command(self, agent_id: str, tool_name: str = ""):
        budget = self.get_budget(agent_id)
        budget.commands_executed += 1
        cost = self.DEFAULT_COSTS.get(tool_name, 1)
        budget.tokens_used += cost  # token proxy for tool cost
        self._persist(agent_id, budget)
    
    def record_llm_call(self, agent_id: str, tokens: int = 0):
        budget = self.get_budget(agent_id)
        budget.llm_calls += 1
        budget.tokens_used += tokens
        self._persist(agent_id, budget)
    
    def _persist(self, agent_id: str, budget: BudgetSnapshot):
        model = self.session.query(ResourceBudgetModel).filter_by(
            challenge_id=self.challenge_id,
            agent_id=None if agent_id == "challenge" else agent_id
        ).first()
        
        if not model:
            model = ResourceBudgetModel(
                challenge_id=self.challenge_id,
                agent_id=None if agent_id == "challenge" else agent_id,
            )
            self.session.add(model)
        
        model.tokens_used = budget.tokens_used
        model.time_used_seconds = budget.time_used_seconds
        model.sub_agents_created = budget.sub_agents_created
        model.commands_executed = budget.commands_executed
        model.llm_calls = budget.llm_calls
        model.updated_at = datetime.utcnow()
        self.session.commit()
    
    def get_tool_cost(self, tool_name: str) -> int:
        return self.DEFAULT_COSTS.get(tool_name, 1)
    
    def check_all_budgets(self) -> List[str]:
        """Return list of exhausted budget agent_ids."""
        return [aid for aid, b in self._budgets.items() if b.exhausted]