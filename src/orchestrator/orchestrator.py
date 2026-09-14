"""Orchestrator - Central coordination engine"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from .models import Challenge, ChallengeClassification, AttackSurface, SolveResult, ChallengeCategory, ChallengeType
from ..runtime import AgentRuntime, get_agent_runtime, AgentContext
from ..runtime.agent import Agent, AgentConfig, AgentState, ResourceBudget
from ..runtime.delegation import DelegationManager, SubAgentSpec, DelegationReason
from ..llm import get_llm_provider, LLMMessage, MessageRole, LLMConfig
from ..memory import MemoryManager, get_memory_manager
from ..evidence import EvidenceEngine, get_evidence_engine, EvidenceClaim
from ..artifacts import ArtifactManager, get_artifact_manager
from ..challenges import ChallengeManager, get_challenge_manager
from ..config.settings import get_settings
from ..config.loader import get_config_manager
from ..observability import get_logger, log_agent_event, log_audit


class Orchestrator:
    """Central orchestration engine for CTF challenge solving."""

    def __init__(self):
        self.settings = get_settings()
        self.config_manager = get_config_manager()
        self.agents_config = self.config_manager.get("agents", {})

        # Core components
        self.runtime: Optional[AgentRuntime] = None
        self.memory: Optional[MemoryManager] = None
        self.evidence: Optional[EvidenceEngine] = None
        self.artifacts: Optional[ArtifactManager] = None
        self.challenge_manager: Optional[ChallengeManager] = None
        self.llm_provider = None
        self.delegation_manager: Optional[DelegationManager] = None

        # State
        self._active_challenges: Dict[str, Challenge] = {}
        self._challenge_agents: Dict[str, List[str]] = {}  # challenge_id -> agent_ids
        self._solve_results: Dict[str, SolveResult] = {}

    async def initialize(self):
        """Initialize orchestrator and components."""
        self.runtime = await get_agent_runtime()
        self.memory = await get_memory_manager()
        self.evidence = await get_evidence_engine()
        self.artifacts = await get_artifact_manager()
        self.challenge_manager = await get_challenge_manager()
        self.llm_provider = await get_llm_provider()
        self.delegation_manager = DelegationManager(self.runtime)

        # Setup callbacks
        self.runtime.on_agent_start = self._on_agent_start
        self.runtime.on_agent_complete = self._on_agent_complete
        self.runtime.on_agent_error = self._on_agent_error
        self.runtime.on_sub_agent_spawn = self._on_sub_agent_spawn

    async def add_challenge(
        self,
        name: str,
        description: str,
        files: List[str] = None,
        target_info: Dict[str, Any] = None,
        credentials: Dict[str, str] = None,
        constraints: List[str] = None,
        flag_format: str = "flag{.*}",
        challenge_type: ChallengeType = ChallengeType.JEOPARDY,
    ) -> Challenge:
        """Add a new challenge."""
        challenge = Challenge(
            name=name,
            description=description,
            files=files or [],
            target_info=target_info or {},
            credentials=credentials or {},
            constraints=constraints or [],
            flag_format=flag_format,
            challenge_type=challenge_type,
        )

        # Classify challenge
        classification = await self.classify_challenge(challenge)
        challenge.category = classification.categories

        # Store challenge
        self._active_challenges[challenge.id] = challenge
        await self.challenge_manager.store(challenge)

        await log_audit(
            agent_id="orchestrator",
            action="challenge_added",
            target=challenge.id,
            reason=f"Added challenge: {name}",
            result="success",
            risk_level="low",
        )

        return challenge

    async def classify_challenge(self, challenge: Challenge) -> ChallengeClassification:
        """Classify a challenge using LLM."""
        system_prompt = """You are a CTF challenge classifier. Analyze the challenge description and files to determine categories.

Categories: web, crypto, pwn, reverse, forensics, osint, stego, mobile, malware, cloud, network, supply_chain, ad, web3, ai_security, sidechannel, firmware, social, programming, meta

Return JSON with: categories (list), confidence (0-1), reasoning (string), suggested_agents (list), attack_surface (object with services, web_endpoints, open_ports, technologies, potential_vulnerabilities, entry_points)"""

        user_prompt = f"""Challenge: {challenge.name}
Description: {challenge.description}
Files: {challenge.files}
Target Info: {challenge.target_info}
Type: {challenge.challenge_type.value}"""

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system_prompt),
            LLMMessage(role=MessageRole.USER, content=user_prompt),
        ]

        response = await self.llm_provider.complete(messages)

        try:
            import json
            result = json.loads(response.content)
            categories = [ChallengeCategory(c) for c in result.get("categories", [])]
            attack_surface_data = result.get("attack_surface", {})
            attack_surface = AttackSurface(**attack_surface_data)

            return ChallengeClassification(
                challenge_id=challenge.id,
                categories=categories,
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
                suggested_agents=result.get("suggested_agents", []),
                attack_surface=attack_surface,
            )
        except Exception:
            # Fallback classification
            return ChallengeClassification(
                challenge_id=challenge.id,
                categories=[ChallengeCategory.UNKNOWN],
                confidence=0.1,
                reasoning="Classification failed",
                suggested_agents=["programming"],
                attack_surface=AttackSurface(),
            )

    async def solve_challenge(self, challenge_id: str) -> SolveResult:
        """Solve a challenge."""
        challenge = self._active_challenges.get(challenge_id)
        if not challenge:
            challenge = await self.challenge_manager.get(challenge_id)
            if not challenge:
                raise ValueError(f"Challenge {challenge_id} not found")

        start_time = datetime.utcnow()

        # Create orchestrator agent for this challenge
        orchestrator_agent = await self.runtime.create_agent(
            role="orchestrator",
            name=f"Orchestrator-{challenge.name}",
            objective=f"Solve challenge: {challenge.name}",
            system_prompt=self._get_orchestrator_prompt(challenge),
            capabilities=["challenge_triage", "task_decomposition", "agent_scheduling", "result_aggregation"],
            allowed_tools=["challenge_triage", "agent_spawn", "memory_query", "evidence_submit", "experiment_create", "report_generate"],
            resource_budget=ResourceBudget(
                max_tokens=200000,
                max_time_seconds=3600,
                max_sub_agents=16,
                max_commands=100,
            ),
        )

        # Spawn and execute
        context = await self.runtime.spawn_agent(orchestrator_agent)
        self._challenge_agents[challenge_id] = [orchestrator_agent.config.id]

        try:
            completed_agent = await self.runtime.execute_agent(context)
            self._challenge_agents[challenge_id].extend(completed_agent.child_agents)

            # Extract result
            result_data = completed_agent.final_result or {}
            flag = result_data.get("flag")
            method = result_data.get("method", "")
            evidence = result_data.get("evidence", [])

            # Verify flag if found
            flag_verified = False
            if flag:
                verification = await self.evidence.verify_flag(
                    flag=flag,
                    challenge_id=challenge_id,
                    agent_id=completed_agent.config.id,
                    method=method,
                    evidence_artifacts=evidence,
                )
                flag_verified = verification.status.value == "verified"

            solve_result = SolveResult(
                challenge_id=challenge_id,
                success=flag_verified,
                flag=flag if flag_verified else None,
                method=method,
                evidence=evidence,
                agents_used=self._challenge_agents.get(challenge_id, []),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
            )

            self._solve_results[challenge_id] = solve_result

            await log_audit(
                agent_id="orchestrator",
                action="challenge_solved",
                target=challenge_id,
                reason=f"Solved challenge: {challenge.name}",
                result="success" if flag_verified else "partial",
                risk_level="low",
            )

            return solve_result

        except Exception as e:
            solve_result = SolveResult(
                challenge_id=challenge_id,
                success=False,
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                error=str(e),
            )
            self._solve_results[challenge_id] = solve_result

            await log_audit(
                agent_id="orchestrator",
                action="challenge_failed",
                target=challenge_id,
                reason=f"Failed to solve challenge: {challenge.name}",
                result="error",
                risk_level="low",
            )

            raise

    async def _on_agent_start(self, agent: Agent):
        """Callback when agent starts."""
        await log_agent_event(agent.config.id, "agent_started", {"role": agent.config.role})

    async def _on_agent_complete(self, agent: Agent):
        """Callback when agent completes."""
        await log_agent_event(agent.config.id, "agent_completed", {"state": agent.state.value})

    async def _on_agent_error(self, agent: Agent, error: Exception):
        """Callback when agent errors."""
        await log_agent_event(agent.config.id, "agent_error", {"error": str(error)})

    async def _on_sub_agent_spawn(self, parent: Agent, child: Agent):
        """Callback when sub-agent spawned."""
        await log_agent_event(parent.config.id, "sub_agent_spawned", {
            "child_id": child.config.id,
            "child_role": child.config.role,
        })

    def _get_orchestrator_prompt(self, challenge: Challenge) -> str:
        """Get orchestrator system prompt for challenge."""
        categories = ", ".join(c.value for c in challenge.category)
        return f"""You are the CTF Orchestrator responsible for solving: {challenge.name}

Challenge Type: {challenge.challenge_type.value}
Categories: {categories}
Description: {challenge.description}
Flag Format: {challenge.flag_format}

Your responsibilities:
1. Decompose the challenge into subtasks
2. Spawn appropriate specialist agents
3. Coordinate parallel execution
4. Aggregate and validate results
5. Verify flag capture

Available specialist agents: web, crypto, pwn, reverse, forensics, osint, stego, mobile, malware, cloud, network, supply_chain, ad, web3, ai_security, sidechannel, firmware, social, programming, meta

Follow the evidence-driven workflow:
OBSERVE -> HYPOTHESIZE -> EXPERIMENT -> MEASURE -> CONCLUDE -> REPEAT

Never promote untested hypotheses. All findings must be verified by the Evidence Engine."""

    async def get_challenge_status(self, challenge_id: str) -> Dict[str, Any]:
        """Get challenge solving status."""
        challenge = self._active_challenges.get(challenge_id)
        if not challenge:
            challenge = await self.challenge_manager.get(challenge_id)

        agents = self._challenge_agents.get(challenge_id, [])
        agent_statuses = []
        for agent_id in agents:
            agent = await self.runtime.get_agent(agent_id)
            if agent:
                agent_statuses.append(agent.get_summary())

        return {
            "challenge": {
                "id": challenge.id if challenge else challenge_id,
                "name": challenge.name if challenge else "Unknown",
                "categories": [c.value for c in challenge.category] if challenge else [],
            },
            "agents": agent_statuses,
            "result": self._solve_results.get(challenge_id).__dict__ if challenge_id in self._solve_results else None,
        }

    async def list_challenges(self) -> List[Dict[str, Any]]:
        """List all challenges."""
        return [
            {
                "id": c.id,
                "name": c.name,
                "categories": [cat.value for cat in c.category],
                "type": c.challenge_type.value,
            }
            for c in self._active_challenges.values()
        ]

    async def generate_report(self, challenge_id: str) -> Dict[str, Any]:
        """Generate solve report."""
        result = self._solve_results.get(challenge_id)
        challenge = self._active_challenges.get(challenge_id)

        if not result or not challenge:
            return {"error": "Challenge not found or not solved"}

        # Collect all findings from agents
        all_findings = []
        all_evidence = []
        all_commands = []

        for agent_id in self._challenge_agents.get(challenge_id, []):
            agent = await self.runtime.get_agent(agent_id)
            if agent:
                all_findings.extend(agent.findings)
                all_evidence.extend(agent.evidence)
                all_commands.extend(agent.executed_commands)

        return {
            "challenge": {
                "id": challenge.id,
                "name": challenge.name,
                "categories": [c.value for c in challenge.category],
                "type": challenge.challenge_type.value,
            },
            "result": {
                "success": result.success,
                "flag": result.flag,
                "method": result.method,
                "duration_seconds": result.duration_seconds,
            },
            "findings": all_findings,
            "evidence": all_evidence,
            "commands": all_commands,
            "agents_used": self._challenge_agents.get(challenge_id, []),
            "generated_at": datetime.utcnow().isoformat(),
        }


# Global orchestrator
_orchestrator: Optional[Orchestrator] = None


async def get_orchestrator() -> Orchestrator:
    """Get global orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
        await _orchestrator.initialize()
    return _orchestrator