"""Orchestrator - Central coordination engine with state machine and security integration"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from enum import Enum
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
from ..triage import DeterministicTriage, get_deterministic_triage
from ..security import (
    get_policy_engine,
    get_scope_engine,
    get_authorization_context,
    get_capability_registry,
    ChallengeScope,
    NetworkRule,
    FilesystemRule,
    NetworkPolicy,
)
from ..observability import get_logger, log_agent_event, log_audit


class OrchestratorState(str, Enum):
    """Orchestrator state machine states."""
    INTAKE = "intake"
    TRIAGE = "triage"
    DISCOVERY = "discovery"
    HYPOTHESIS = "hypothesis"
    INVESTIGATION = "investigation"
    EXPLOITATION = "exploitation"
    VALIDATION = "validation"
    FLAG_VERIFICATION = "flag_verification"
    REPORT = "report"
    COMPLETE = "complete"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class Orchestrator:
    """Central orchestration engine for CTF challenge solving with state machine."""

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
        self.triage: Optional[DeterministicTriage] = None
        self.policy_engine = get_policy_engine()
        self.scope_engine = get_scope_engine()
        self.auth_manager = get_authorization_context()
        self.capability_registry = get_capability_registry()

        # State machine
        self._state = OrchestratorState.INTAKE
        self._current_challenge_id: Optional[str] = None
        self._state_data: Dict[str, Any] = {}

        # State
        self._active_challenges: Dict[str, Challenge] = {}
        self._challenge_agents: Dict[str, List[str]] = {}
        self._solve_results: Dict[str, SolveResult] = {}
        self._attack_graph: Dict[str, Any] = {}  # challenge_id -> graph

    async def initialize(self):
        """Initialize orchestrator and components."""
        self.runtime = await get_agent_runtime()
        self.memory = await get_memory_manager()
        self.evidence = await get_evidence_engine()
        self.artifacts = await get_artifact_manager()
        self.challenge_manager = await get_challenge_manager()
        self.llm_provider = await get_llm_provider()
        self.delegation_manager = DelegationManager(self.runtime)
        self.triage = get_deterministic_triage()

        # Setup callbacks
        self.runtime.on_agent_start = self._on_agent_start
        self.runtime.on_agent_complete = self._on_agent_complete
        self.runtime.on_agent_error = self._on_agent_error
        self.runtime.on_sub_agent_spawn = self._on_sub_agent_spawn

    def _transition_state(self, new_state: OrchestratorState):
        """Transition orchestrator state."""
        old_state = self._state
        self._state = new_state
        self._state_data["last_transition"] = datetime.utcnow().isoformat()
        self._state_data["previous_state"] = old_state.value
        
        logger = get_logger("orchestrator")
        logger.info("state_transition", 
            orchestrator_state=new_state.value,
            previous_state=old_state.value,
            challenge_id=self._current_challenge_id)

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
        """Add a new challenge with scope initialization."""
        self._transition_state(OrchestratorState.INTAKE)
        
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

        # Store challenge
        self._active_challenges[challenge.id] = challenge
        await self.challenge_manager.store(challenge)

        # Initialize scope
        await self._initialize_scope(challenge)

        # Log audit
        await log_audit(
            agent_id="orchestrator",
            action="challenge_added",
            target=challenge.id,
            reason=f"Added challenge: {name}",
            result="success",
            risk_level="low",
        )

        return challenge

    async def _initialize_scope(self, challenge: Challenge):
        """Initialize challenge scope based on type and target info."""
        target_ip = challenge.target_info.get("ip") or challenge.target_info.get("host")
        
        if challenge.challenge_type == ChallengeType.JEOPARDY:
            scope = ChallengeScope.create_for_jeopardy(challenge.id, target_ip)
        elif challenge.challenge_type == ChallengeType.MACHINES:
            target_cidr = challenge.target_info.get("cidr", "10.10.10.0/24")
            scope = ChallengeScope.create_for_machines(challenge.id, target_cidr)
        elif challenge.challenge_type == ChallengeType.ATTACK_DEFENSE:
            team_network = challenge.target_info.get("team_network", "10.10.10.0/24")
            scope = ChallengeScope.create_for_attack_defense(challenge.id, team_network)
        else:
            scope = ChallengeScope.create_for_jeopardy(challenge.id, target_ip)
        
        # Add agent-specific workspace paths
        for agent_role in ["web", "crypto", "pwn", "reverse", "forensics", "osint", "stego", "mobile", "malware", "cloud", "network", "supply_chain", "ad", "web3", "ai_security", "sidechannel", "firmware", "social", "programming", "meta", "orchestrator"]:
            scope.allowed_paths.append(FilesystemRule(
                path=f"/workspace/{challenge.id}/{agent_role}",
                read=True,
                write=True,
                description=f"Workspace for {agent_role} agent"
            ))
        
        # Register scope
        self.scope_engine.register_scope(scope)
        
        # Add allowed tools per agent role
        self._configure_scope_tools(scope, challenge)

    def _configure_scope_tools(self, scope: ChallengeScope, challenge: Challenge):
        """Configure allowed tools based on challenge categories."""
        tool_map = {
            ChallengeCategory.WEB: ["nmap", "curl", "ffuf", "httpx", "nuclei", "sqlmap", "knock"],
            ChallengeCategory.CRYPTO: ["hashcat", "john", "openssl", "python"],
            ChallengeCategory.PWN: ["gdb", "pwntools", "checksec", "ROPgadget", "ropper", "python"],
            ChallengeCategory.REVERSE: ["ghidra", "radare2", "angr", "gdb", "python"],
            ChallengeCategory.FORENSICS: ["volatility", "binwalk", "exiftool", "yara", "foremost", "python"],
            ChallengeCategory.OSINT: ["nmap", "curl", "httpx", "python"],
            ChallengeCategory.STEGO: ["steghide", "zsteg", "binwalk", "exiftool", "python"],
            ChallengeCategory.MOBILE: ["apktool", "jadx", "frida", "python"],
            ChallengeCategory.MALWARE: ["yara", "binwalk", "ghidra", "radare2", "volatility", "python"],
            ChallengeCategory.CLOUD: ["awscli", "kubectl", "trivy", "python"],
            ChallengeCategory.NETWORK: ["nmap", "rustscan", "masscan", "tshark", "python"],
            ChallengeCategory.AD: ["impacket", "kerbrute", "netexec", "python"],
            ChallengeCategory.WEB3: ["foundry", "slither", "mythril", "python"],
            ChallengeCategory.AI_SECURITY: ["python"],
            ChallengeCategory.SIDECHANNEL: ["python"],
            ChallengeCategory.FIRMWARE: ["binwalk", "ghidra", "radare2", "python"],
            ChallengeCategory.SOCIAL: ["python"],
            ChallengeCategory.PROGRAMMING: ["python", "bash", "gcc", "rustc"],
            ChallengeCategory.META: ["python", "curl"],
        }
        
        allowed_tools = set()
        for cat in challenge.category:
            allowed_tools.update(tool_map.get(cat, []))
        
        # Always allow basic tools
        allowed_tools.update(["python", "bash", "curl", "git", "jq", "file", "strings"])
        
        scope.allowed_tools = list(allowed_tools)

    async def classify_challenge(self, challenge: Challenge) -> ChallengeClassification:
        """Classify a challenge using deterministic + LLM triage."""
        self._transition_state(OrchestratorState.TRIAGE)
        
        # Run deterministic triage first
        deterministic_result = await self.triage.classify(challenge)
        
        # Combine with LLM classification
        system_prompt = """You are a CTF challenge classifier. Analyze the challenge description and files to determine categories.

Categories: web, crypto, pwn, reverse, forensics, osint, stego, mobile, malware, cloud, network, supply_chain, ad, web3, ai_security, sidechannel, firmware, social, programming, meta

Return JSON with: categories (list), confidence (0-1), reasoning (string), suggested_agents (list), attack_surface (object with services, web_endpoints, open_ports, technologies, potential_vulnerabilities, entry_points)"""

        user_prompt = f"""Challenge: {challenge.name}
Description: {challenge.description}
Files: {challenge.files}
Target Info: {challenge.target_info}
Type: {challenge.challenge_type.value}

Deterministic analysis suggests: {deterministic_result.categories}"""

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
            # Fallback to deterministic
            return ChallengeClassification(
                challenge_id=challenge.id,
                categories=deterministic_result.categories,
                confidence=deterministic_result.confidence,
                reasoning=f"LLM classification failed, using deterministic: {deterministic_result.reasoning}",
                suggested_agents=deterministic_result.suggested_agents,
                attack_surface=deterministic_result.attack_surface,
            )

    async def solve_challenge(self, challenge_id: str) -> SolveResult:
        """Solve a challenge using the state machine."""
        challenge = self._active_challenges.get(challenge_id)
        if not challenge:
            challenge = await self.challenge_manager.get(challenge_id)
            if not challenge:
                raise ValueError(f"Challenge {challenge_id} not found")

        self._current_challenge_id = challenge_id
        start_time = datetime.utcnow()

        # Create authorization context for orchestrator
        orchestrator_auth = self.auth_manager.create_context(
            agent_id=f"orchestrator-{challenge_id}",
            agent_role="orchestrator",
            challenge_id=challenge_id,
            custom_budget={
                "token_budget": 200000,
                "time_budget_seconds": 3600,
                "sub_agent_budget": 16,
                "command_budget": 100,
            }
        )

        # Register scope for this challenge in authorization manager
        scope = self.scope_engine.get_scope(challenge_id)
        if scope:
            orchestrator_auth.scope = scope

        # Run state machine
        try:
            result = await self._run_state_machine(challenge, orchestrator_auth)
            return result
        except Exception as e:
            self._transition_state(OrchestratorState.FAILED)
            raise
        finally:
            self._current_challenge_id = None

    async def _run_state_machine(self, challenge: Challenge, orchestrator_auth) -> SolveResult:
        """Run the orchestrator state machine."""
        start_time = datetime.utcnow()
        
        # DISCOVERY phase
        self._transition_state(OrchestratorState.DISCOVERY)
        await self._run_discovery_phase(challenge)
        
        # HYPOTHESIS phase
        self._transition_state(OrchestratorState.HYPOTHESIS)
        await self._run_hypothesis_phase(challenge)
        
        # INVESTIGATION phase
        self._transition_state(OrchestratorState.INVESTIGATION)
        await self._run_investigation_phase(challenge)
        
        # EXPLOITATION phase
        self._transition_state(OrchestratorState.EXPLOITATION)
        flag = await self._run_exploitation_phase(challenge)
        
        # VALIDATION phase
        self._transition_state(OrchestratorState.VALIDATION)
        evidence = await self._run_validation_phase(challenge, flag)
        
        # FLAG_VERIFICATION phase
        self._transition_state(OrchestratorState.FLAG_VERIFICATION)
        flag_verified = False
        if flag:
            flag_verified = await self._verify_flag(challenge, flag, evidence)
        
        # REPORT phase
        self._transition_state(OrchestratorState.REPORT)
        await self._generate_report(challenge)
        
        self._transition_state(OrchestratorState.COMPLETE)
        
        solve_result = SolveResult(
            challenge_id=challenge.id,
            success=flag_verified,
            flag=flag if flag_verified else None,
            method="State machine orchestration",
            evidence=evidence,
            agents_used=self._challenge_agents.get(challenge.id, []),
            duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
        )
        
        self._solve_results[challenge.id] = solve_result
        
        await log_audit(
            agent_id="orchestrator",
            action="challenge_solved",
            target=challenge.id,
            reason=f"Solved challenge: {challenge.name}",
            result="success" if flag_verified else "partial",
            risk_level="low",
        )
        
        return solve_result

    async def _run_discovery_phase(self, challenge: Challenge):
        """Run discovery phase - spawn recon agents."""
        self._transition_state(OrchestratorState.DISCOVERY)
        
        # Spawn appropriate recon agents based on challenge category
        recon_agents = []
        for cat in challenge.category:
            if cat == ChallengeCategory.WEB:
                recon_agents.append(("web", "Web Recon", "Perform web reconnaissance"))
            elif cat == ChallengeCategory.NETWORK:
                recon_agents.append(("network", "Network Recon", "Perform network reconnaissance"))
            elif cat == ChallengeCategory.OSINT:
                recon_agents.append(("osint", "OSINT Recon", "Perform OSINT gathering"))
        
        # Spawn and run recon agents
        for role, name, objective in recon_agents:
            agent = await self.runtime.create_agent(
                role=role,
                name=f"{name}-{challenge.name}",
                objective=objective,
                parent_agent=None,
                allowed_tools=self._get_allowed_tools_for_role(role),
                resource_budget=ResourceBudget(max_time_seconds=300, max_sub_agents=2),
            )
            context = await self.runtime.spawn_agent(agent)
            self._challenge_agents.setdefault(challenge.id, []).append(agent.config.id)
            await self.runtime.execute_agent(context)

    async def _run_hypothesis_phase(self, challenge: Challenge):
        """Run hypothesis generation phase."""
        self._transition_state(OrchestratorState.HYPOTHESIS)
        
        # Analyze findings from discovery
        # Generate hypotheses using LLM
        # This would integrate with a hypothesis engine
        pass

    async def _run_investigation_phase(self, challenge: Challenge):
        """Run investigation phase - test hypotheses."""
        self._transition_state(OrchestratorState.INVESTIGATION)
        
        # Spawn specialist agents to test hypotheses
        pass

    async def _run_exploitation_phase(self, challenge: Challenge) -> Optional[str]:
        """Run exploitation phase - attempt to exploit vulnerabilities."""
        self._transition_state(OrchestratorState.EXPLOITATION)
        
        # Spawn exploitation agents
        # Return flag if found
        return None

    async def _run_validation_phase(self, challenge: Challenge, flag: Optional[str]) -> List[str]:
        """Run validation phase - verify findings."""
        self._transition_state(OrchestratorState.VALIDATION)
        
        # Verify evidence
        return []

    async def _verify_flag(self, challenge: Challenge, flag: str, evidence: List[str]) -> bool:
        """Verify captured flag."""
        self._transition_state(OrchestratorState.FLAG_VERIFICATION)
        
        verification = await self.evidence.verify_flag(
            flag=flag,
            challenge_id=challenge.id,
            agent_id="orchestrator",
            method="State machine exploitation",
            evidence_artifacts=evidence,
        )
        
        return verification.status.value == "verified"

    async def _generate_report(self, challenge: Challenge):
        """Generate final report."""
        self._transition_state(OrchestratorState.REPORT)
        
        # Generate report
        await self.generate_report(challenge.id)

    def _get_allowed_tools_for_role(self, role: str) -> List[str]:
        """Get allowed tools for agent role."""
        tool_map = {
            "web": ["nmap", "curl", "ffuf", "httpx", "nuclei", "sqlmap", "knock", "python"],
            "crypto": ["hashcat", "john", "openssl", "python"],
            "pwn": ["gdb", "pwntools", "checksec", "ROPgadget", "ropper", "python"],
            "reverse": ["ghidra", "radare2", "angr", "gdb", "python"],
            "forensics": ["volatility", "binwalk", "exiftool", "yara", "foremost", "python"],
            "osint": ["nmap", "curl", "httpx", "python"],
            "stego": ["steghide", "zsteg", "binwalk", "exiftool", "python"],
            "mobile": ["apktool", "jadx", "frida", "python"],
            "malware": ["yara", "binwalk", "ghidra", "radare2", "volatility", "python"],
            "cloud": ["awscli", "kubectl", "trivy", "python"],
            "network": ["nmap", "rustscan", "masscan", "tshark", "python"],
            "ad": ["impacket", "kerbrute", "netexec", "python"],
            "web3": ["foundry", "slither", "mythril", "python"],
            "ai_security": ["python"],
            "sidechannel": ["python"],
            "firmware": ["binwalk", "ghidra", "radare2", "python"],
            "social": ["python"],
            "programming": ["python", "bash", "gcc", "rustc"],
            "meta": ["python", "curl"],
            "orchestrator": ["python", "curl"],
        }
        return tool_map.get(role, ["python"])

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
            "orchestrator_state": self._state.value,
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