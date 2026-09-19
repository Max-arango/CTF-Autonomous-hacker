"""Single-Process Orchestrator - State Machine"""
import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from .db import get_session_factory
from .models import (
    Challenge, Agent, Finding, Hypothesis, Experiment, ToolExecution,
    Observation, Evidence, Artifact, SolveResult, AuditEvent, AgentIdentity,
    ChallengeCategory, ChallengeType, AgentState, AgentRole, HypothesisStatus,
    VerificationStatus
)
from .permissions import get_permission_manager, PermissionRequest
from .resources import ResourceGovernor
from ..llm import get_llm_provider, LLMMessage, MessageRole
from ..runtime import AgentRuntime, get_agent_runtime
from ..runtime.agent import Agent as RuntimeAgent, AgentConfig, ResourceBudget
from ..runtime.delegation import DelegationManager
from ..evidence import EvidenceEngine, get_evidence_engine
from ..artifacts import ArtifactManager, get_artifact_manager
from ..scope.engine import ChallengeScope, ScopeType
from ..observations import (
    ServiceObservation, EndpointObservation, FileTypeObservation,
    StringObservation, EmbeddedArtifactObservation
)
from ..network.authorization import create_network_authorizer
from ..observability import get_logger, log_audit


class OrchestratorState(Enum):
    INTAKE = "intake"
    TRIAGE = "triage"
    SCOPE = "scope"
    DISCOVERY = "discovery"
    HYPOTHESIS = "hypothesis"
    INVESTIGATION = "investigation"
    EXPLOITATION = "exploitation"
    VALIDATION = "validation"
    FLAG_VERIFICATION = "flag_verification"
    REPORT = "report"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class StateTransition:
    from_state: OrchestratorState
    to_state: OrchestratorState
    preconditions: List[Callable[["OrchestratorContext"], Awaitable[bool]]] = field(default_factory=list)
    actions: List[Callable[["OrchestratorContext"], Awaitable[Any]]] = field(default_factory=list)
    on_failure: Optional[OrchestratorState] = None
    timeout_seconds: int = 300


@dataclass
class OrchestratorContext:
    challenge_id: str
    state: OrchestratorState = OrchestratorState.INTAKE
    challenge: Optional[Challenge] = None
    orchestrator_agent_id: Optional[str] = None
    active_agents: List[str] = field(default_factory=list)
    findings_count: int = 0
    hypotheses_count: int = 0
    experiments_count: int = 0
    flag_candidate: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class Orchestrator:
    """Single-process orchestrator with explicit state machine."""
    
    def __init__(self, db_path: str = "ctf.db"):
        self.db_path = db_path
        self.engine, self.session_factory = init_db(db_path)
        self.session = self.session_factory()
        
        # Core components (initialized lazily)
        self._runtime: Optional[AgentRuntime] = None
        self._llm = None
        self._evidence: Optional[EvidenceEngine] = None
        self._artifacts: Optional[ArtifactManager] = None
        self._permission_mgr = get_permission_manager()
        self._governor = ResourceGovernor(self.session, "")
        self._delegation_mgr = None
        self._network_auth = None
        
        # State machine
        self._context: Optional[OrchestratorContext] = None
        self._state_machine = self._build_state_machine()
    
    async def initialize(self):
        """Initialize all components."""
        self._runtime = await get_agent_runtime()
        self._llm = await get_llm_provider()
        self._evidence = await get_evidence_engine()
        self._artifacts = await get_artifact_manager()
        self._delegation_mgr = DelegationManager(self._runtime)
        self._governor = ResourceGovernor(self.session, "")
        
        # Setup callbacks
        self._runtime.on_agent_start = self._on_agent_start
        self._runtime.on_agent_complete = self._on_agent_complete
        self._runtime.on_agent_error = self._on_agent_error
        self._runtime.on_sub_agent_spawn = self._on_sub_agent_spawn
    
    def _build_state_machine(self) -> Dict[OrchestratorState, StateTransition]:
        return {
            OrchestratorState.INTAKE: StateTransition(
                from_state=OrchestratorState.INTAKE,
                to_state=OrchestratorState.TRIAGE,
                actions=[self._action_intake],
            ),
            OrchestratorState.TRIAGE: StateTransition(
                from_state=OrchestratorState.TRIAGE,
                to_state=OrchestratorState.SCOPE,
                preconditions=[self._pre_triage_done],
                actions=[self._action_triage],
            ),
            OrchestratorState.SCOPE: StateTransition(
                from_state=OrchestratorState.SCOPE,
                to_state=OrchestratorState.DISCOVERY,
                preconditions=[self._pre_scope_defined],
                actions=[self._action_scope],
            ),
            OrchestratorState.DISCOVERY: StateTransition(
                from_state=OrchestratorState.DISCOVERY,
                to_state=OrchestratorState.HYPOTHESIS,
                preconditions=[self._pre_discovery_done],
                actions=[self._action_discovery],
                on_failure=OrchestratorState.HYPOTHESIS,  # Continue even if limited discovery
            ),
            OrchestratorState.HYPOTHESIS: StateTransition(
                from_state=OrchestratorState.HYPOTHESIS,
                to_state=OrchestratorState.INVESTIGATION,
                preconditions=[self._pre_hypotheses_exist],
                actions=[self._action_hypothesis],
            ),
            OrchestratorState.INVESTIGATION: StateTransition(
                from_state=OrchestratorState.INVESTIGATION,
                to_state=OrchestratorState.EXPLOITATION,
                preconditions=[self._pre_investigation_done],
                actions=[self._action_investigation],
                on_failure=OrchestratorState.VALIDATION,
            ),
            OrchestratorState.EXPLOITATION: StateTransition(
                from_state=OrchestratorState.EXPLOITATION,
                to_state=OrchestratorState.VALIDATION,
                actions=[self._action_exploitation],
                on_failure=OrchestratorState.VALIDATION,
            ),
            OrchestratorState.VALIDATION: StateTransition(
                from_state=OrchestratorState.VALIDATION,
                to_state=OrchestratorState.FLAG_VERIFICATION,
                preconditions=[self._pre_exploit_validated],
                actions=[self._action_validation],
                on_failure=OrchestratorState.HYPOTHESIS,
            ),
            OrchestratorState.FLAG_VERIFICATION: StateTransition(
                from_state=OrchestratorState.FLAG_VERIFICATION,
                to_state=OrchestratorState.REPORT,
                preconditions=[self._pre_flag_candidate],
                actions=[self._action_flag_verification],
                on_failure=OrchestratorState.HYPOTHESIS,
            ),
            OrchestratorState.REPORT: StateTransition(
                from_state=OrchestratorState.REPORT,
                to_state=OrchestratorState.COMPLETE,
                actions=[self._action_report],
            ),
        }
    
    # --- Public API ---
    
    async def add_challenge(self, **kwargs) -> Challenge:
        """Add a new challenge."""
        challenge = Challenge(**kwargs)
        self.session.add(challenge)
        self.session.commit()
        return challenge
    
    async def solve(self, challenge_id: str) -> SolveResult:
        """Run the full state machine for a challenge."""
        self._context = OrchestratorContext(challenge_id=challenge_id)
        self._governor = ResourceGovernor(self.session, challenge_id)
        self._network_auth = create_network_authorizer(
            self.session.query(Challenge).get(challenge_id).scope if hasattr(Challenge, 'scope') else None
        )
        
        # Load challenge
        challenge = self.session.query(Challenge).get(challenge_id)
        if not challenge:
            raise ValueError(f"Challenge {challenge_id} not found")
        self._context.challenge = challenge
        
        # Run state machine
        while self._context.state not in (OrchestratorState.COMPLETE, OrchestratorState.FAILED):
            await self._run_state()
            
            # Check budgets
            exhausted = self._governor.check_all_budgets()
            if exhausted:
                self._context.error = f"Budgets exhausted: {exhausted}"
                self._context.state = OrchestratorState.FAILED
                break
        
        # Save final result
        return await self._finalize_result()
    
    async def _run_state(self):
        """Execute current state transition."""
        transition = self._state_machine.get(self._context.state)
        if not transition:
            self._context.state = OrchestratorState.FAILED
            return
        
        # Check preconditions
        for pre in transition.preconditions:
            if not await pre(self._context):
                if transition.on_failure:
                    self._context.state = transition.on_failure
                else:
                    self._context.state = OrchestratorState.FAILED
                return
        
        # Execute actions
        for action in transition.actions:
            try:
                await action(self._context)
            except Exception as e:
                self._context.error = f"State {self._context.state} action failed: {e}"
                if transition.on_failure:
                    self._context.state = transition.on_failure
                else:
                    self._context.state = OrchestratorState.FAILED
                return
        
        # Transition
        self._context.state = transition.to_state
        self._context.updated_at = datetime.utcnow()
    
    # --- State Actions ---
    
    async def _action_intake(self, ctx: OrchestratorContext):
        """Initialize challenge, create orchestrator agent."""
        challenge = ctx.challenge
        
        # Create orchestrator agent
        agent = await self._runtime.create_agent(
            role="orchestrator",
            name=f"Orchestrator-{challenge.name}",
            objective=f"Solve challenge: {challenge.name}",
            system_prompt=self._get_orchestrator_prompt(challenge),
            capabilities=["triage", "decomposition", "scheduling", "aggregation"],
            allowed_tools=["triage", "spawn_agent", "memory_query", "evidence_submit", "report_generate"],
            resource_budget=ResourceBudget(max_tokens=200000, max_time_seconds=3600, max_sub_agents=16),
            challenge_id=challenge.id,
        )
        
        # Persist agent
        db_agent = Agent(
            id=agent.config.id,
            challenge_id=challenge.id,
            role=AgentRole.ORCHESTRATOR,
            name=agent.config.name,
            objective=agent.config.objective,
            depth=0,
            state=AgentState.CREATED,
            capabilities=agent.config.capabilities,
            allowed_tools=agent.config.allowed_tools,
            max_tokens=agent.config.resource_budget.max_tokens,
            max_time_seconds=agent.config.resource_budget.max_time_seconds,
            max_sub_agents=agent.config.resource_budget.max_sub_agents,
            max_commands=agent.config.resource_budget.max_commands,
        )
        self.session.add(db_agent)
        self.session.commit()
        
        ctx.orchestrator_agent_id = agent.config.id
        ctx.active_agents.append(agent.config.id)
        
        # Spawn and run triage
        ctx2 = await self._runtime.spawn_agent(agent)
        await self._runtime.execute_agent(ctx2)
        
        # Update from agent result
        if agent.final_result:
            ctx.findings_count = len(agent.findings)
    
    async def _action_triage(self, ctx: OrchestratorContext):
        """Classify challenge, select specialists."""
        challenge = ctx.challenge
        
        # LLM classification
        response = await self._llm.complete([
            LLMMessage(role=MessageRole.SYSTEM, content="""Classify CTF challenge. Return JSON:
categories: list of [web,crypto,pwn,reverse,forensics,osint,stego,mobile,malware,cloud,network,supply_chain,ad,web3,ai_security,sidechannel,firmware,social,programming,meta]
confidence: 0-1
reasoning: string
suggested_agents: list of specialist roles
attack_surface: {services, web_endpoints, open_ports, technologies, potential_vulnerabilities, entry_points}"""),
            LLMMessage(role=MessageRole.USER, content=f"Challenge: {challenge.name}\nDescription: {challenge.description}\nFiles: {challenge.files}\nTarget: {challenge.target_info}")
        ])
        
        try:
            import json
            result = json.loads(response.content)
            categories = [ChallengeCategory(c) for c in result.get("categories", [])]
            challenge.category = categories
            self.session.commit()
            
            # Store suggested agents for discovery phase
            ctx.challenge.metadata["suggested_agents"] = result.get("suggested_agents", [])
            ctx.challenge.metadata["attack_surface"] = result.get("attack_surface", {})
            self.session.commit()
        except Exception:
            challenge.category = [ChallengeCategory.UNKNOWN]
            self.session.commit()
    
    async def _action_scope(self, ctx: OrchestratorContext):
        """Establish challenge scope from target info."""
        challenge = ctx.challenge
        target_info = challenge.target_info or {}
        
        # Extract targets from target_info
        targets = target_info.get("targets", [])
        if isinstance(targets, str):
            targets = [targets]
        
        # Default to exact scope - no auto expansion
        scope = ChallengeScope(challenge_id=challenge.id, allow_subnet_expansion=False)
        for t in targets:
            scope.add_range(ScopeType.TARGET, t)
        
        # Save scope
        challenge.target_scope = [{"network": r.network, "exact": r.exact} for r in scope.target_scope]
        challenge.discovery_scope = [{"network": r.network, "exact": r.exact} for r in scope.discovery_scope]
        challenge.allow_subnet_expansion = scope.allow_subnet_expansion
        self.session.commit()
    
    async def _action_discovery(self, ctx: OrchestratorContext):
        """Spawn specialist agents for parallel discovery."""
        challenge = ctx.challenge
        suggested = challenge.metadata.get("suggested_agents", [])
        
        # Map to actual agent roles
        role_map = {
            "web": AgentRole.WEB, "crypto": AgentRole.CRYPTO, "pwn": AgentRole.PWN,
            "reverse": AgentRole.REVERSE, "forensics": AgentRole.FORENSICS,
            "osint": AgentRole.OSINT, "stego": AgentRole.STEGO,
        }
        
        specialist_roles = [role_map.get(r) for r in suggested if r in role_map]
        if not specialist_roles:
            specialist_roles = [AgentRole.WEB, AgentRole.FORENSICS]  # Default
        
        # Spawn specialists in parallel
        tasks = []
        for role in specialist_roles[:4]:  # Limit parallel
            agent = await self._runtime.create_agent(
                role=role.value,
                name=f"{role.value.title()}-{challenge.name}",
                objective=f"Discover attack surface for {challenge.name}",
                system_prompt=self._get_specialist_prompt(role),
                capabilities=[f"{role.value}_discovery", "enumeration", "fingerprinting"],
                allowed_tools=self._get_tools_for_role(role),
                resource_budget=ResourceBudget(max_tokens=50000, max_time_seconds=600, max_sub_agents=2),
                challenge_id=challenge.id,
            )
            
            db_agent = Agent(
                id=agent.config.id,
                challenge_id=challenge.id,
                parent_id=ctx.orchestrator_agent_id,
                role=role,
                name=agent.config.name,
                objective=agent.config.objective,
                depth=1,
                state=AgentState.CREATED,
                capabilities=agent.config.capabilities,
                allowed_tools=agent.config.allowed_tools,
                max_tokens=agent.config.resource_budget.max_tokens,
                max_time_seconds=agent.config.resource_budget.max_time_seconds,
                max_sub_agents=agent.config.resource_budget.max_sub_agents,
                max_commands=agent.config.resource_budget.max_commands,
            )
            self.session.add(db_agent)
            ctx.active_agents.append(agent.config.id)
            tasks.append(self._runtime.spawn_agent(agent))
        
        self.session.commit()
        
        # Execute all in parallel
        contexts = await asyncio.gather(*tasks)
        for ctx_agent in contexts:
            await self._runtime.execute_agent(ctx_agent)
    
    async def _action_hypothesis(self, ctx: OrchestratorContext):
        """Orchestrator generates hypotheses from discovery results."""
        # Collect all findings from specialists
        all_findings = []
        for agent_id in ctx.active_agents:
            agent = await self._runtime.get_agent(agent_id)
            if agent:
                all_findings.extend(agent.findings)
        
        # LLM generates hypotheses
        response = await self._llm.complete([
            LLMMessage(role=MessageRole.SYSTEM, content="""Generate hypotheses from findings. Return JSON list:
[{"description": "...", "confidence": 0.8, "supporting_evidence": ["finding_id"], "estimated_cost": 10, "expected_information_gain": 5}]"""),
            LLMMessage(role=MessageRole.USER, content=f"Findings: {all_findings}")
        ])
        
        try:
            import json
            hypotheses = json.loads(response.content)
            for h in hypotheses:
                hyp = Hypothesis(
                    challenge_id=ctx.challenge_id,
                    agent_id=ctx.orchestrator_agent_id,
                    description=h["description"],
                    confidence=h.get("confidence", 0.5),
                    status=HypothesisStatus.PROPOSED,
                    supporting_evidence=h.get("supporting_evidence", []),
                    estimated_cost=h.get("estimated_cost", 10),
                    expected_information_gain=h.get("expected_information_gain", 1.0),
                )
                self.session.add(hyp)
            self.session.commit()
            ctx.hypotheses_count = len(hypotheses)
        except Exception:
            pass
    
    async def _action_investigation(self, ctx: OrchestratorContext):
        """Test hypotheses via experiments."""
        hypotheses = self.session.query(Hypothesis).filter_by(
            challenge_id=ctx.challenge_id,
            status=HypothesisStatus.PROPOSED
        ).order_by(Hypothesis.confidence.desc()).limit(5).all()
        
        for hyp in hypotheses:
            # Create experiment
            exp = Experiment(
                challenge_id=ctx.challenge_id,
                agent_id=ctx.orchestrator_agent_id,
                hypothesis_id=hyp.id,
                name=f"Test: {hyp.description[:50]}",
                description=f"Validate hypothesis: {hyp.description}",
                status="running",
            )
            self.session.add(exp)
            self.session.commit()
            
            # LLM plans experiment
            response = await self._llm.complete([
                LLMMessage(role=MessageRole.SYSTEM, content="""Plan experiment to test hypothesis. Return JSON:
tool: tool_name, arguments: {...}, expected_outcome: "..."""),
                LLMMessage(role=MessageRole.USER, content=f"Hypothesis: {hyp.description}")
            ])
            
            try:
                import json
                plan = json.loads(response.content)
                exp.tool_name = plan.get("tool", "python_sandbox")
                exp.arguments = plan.get("arguments", {})
                exp.expected_outcome = plan.get("expected_outcome", "")
                self.session.commit()
                
                # Execute via orchestrator agent
                orch_agent = await self._runtime.get_agent(ctx.orchestrator_agent_id)
                if orch_agent:
                    result = await self._runtime.execute_tool(orch_agent, exp.tool_name, exp.arguments)
                    exp.status = "completed" if result.success else "failed"
                    exp.result = {"success": result.success, "stdout": result.stdout, "stderr": result.stderr}
                    exp.completed_at = datetime.utcnow()
                    
                    # Record tool execution
                    te = ToolExecution(
                        challenge_id=ctx.challenge_id,
                        agent_id=ctx.orchestrator_agent_id,
                        experiment_id=exp.id,
                        tool_name=exp.tool_name,
                        arguments=exp.arguments,
                        success=result.success,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        exit_code=result.exit_code,
                        execution_time=result.execution_time,
                    )
                    self.session.add(te)
                    
                    # Normalize observation
                    await self._normalize_observation(te, result)
                    
                    # Update hypothesis
                    if result.success:
                        hyp.status = HypothesisStatus.SUPPORTED
                        hyp.supporting_evidence.append(te.id)
                    else:
                        hyp.status = HypothesisStatus.REFUTED
                        hyp.contradicting_evidence.append(te.id)
                    hyp.tested_at = datetime.utcnow()
                    
            except Exception as e:
                exp.status = "failed"
                exp.error = str(e)
            
            self.session.commit()
    
    async def _action_exploitation(self, ctx: OrchestratorContext):
        """Attempt exploitation based on supported hypotheses."""
        supported = self.session.query(Hypothesis).filter_by(
            challenge_id=ctx.challenge_id,
            status=HypothesisStatus.SUPPORTED
        ).all()
        
        for hyp in supported:
            # Create exploit experiment
            exp = Experiment(
                challenge_id=ctx.challenge_id,
                agent_id=ctx.orchestrator_agent_id,
                hypothesis_id=hyp.id,
                name=f"Exploit: {hyp.description[:50]}",
                description=f"Exploit based on: {hyp.description}",
                status="running",
            )
            self.session.add(exp)
            self.session.commit()
            
            # LLM crafts exploit
            response = await self._llm.complete([
                LLMMessage(role=MessageRole.SYSTEM, content="""Craft exploit for hypothesis. Return JSON:
tool: tool_name, arguments: {...}, expected_outcome: "flag or shell or data" """),
                LLMMessage(role=MessageRole.USER, content=f"Hypothesis: {hyp.description}\nEvidence: {hyp.supporting_evidence}")
            ])
            
            try:
                import json
                plan = json.loads(response.content)
                exp.tool_name = plan.get("tool", "python_sandbox")
                exp.arguments = plan.get("arguments", {})
                exp.expected_outcome = plan.get("expected_outcome", "flag")
                self.session.commit()
                
                orch_agent = await self._runtime.get_agent(ctx.orchestrator_agent_id)
                if orch_agent:
                    result = await self._runtime.execute_tool(orch_agent, exp.tool_name, exp.arguments)
                    exp.result = {"success": result.success, "stdout": result.stdout}
                    
                    # Check for flag
                    if result.success and "flag{" in result.stdout:
                        ctx.flag_candidate = self._extract_flag(result.stdout)
                        exp.status = "completed"
                        ctx.state = OrchestratorState.FLAG_VERIFICATION
                        return
                    else:
                        exp.status = "completed"
                        
            except Exception as e:
                exp.status = "failed"
                exp.error = str(e)
            
            self.session.commit()
    
    async def _action_validation(self, ctx: OrchestratorContext):
        """Validate exploit results via evidence engine."""
        # Evidence engine validates all findings
        pass  # Done during investigation
    
    async def _action_flag_verification(self, ctx: OrchestratorContext):
        """Verify flag candidate."""
        if not ctx.flag_candidate:
            ctx.state = OrchestratorState.HYPOTHESIS
            return
        
        verification = await self._evidence.verify_flag(
            flag=ctx.flag_candidate,
            challenge_id=ctx.challenge_id,
            agent_id=ctx.orchestrator_agent_id,
            method="exploit",
            evidence_artifacts=[],
        )
        
        if verification.status.value == "verified":
            ctx.challenge.metadata["verified_flag"] = ctx.flag_candidate
        else:
            ctx.flag_candidate = None
            ctx.state = OrchestratorState.HYPOTHESIS
        
        self.session.commit()
    
    async def _action_report(self, ctx: OrchestratorContext):
        """Generate final report."""
        result = SolveResult(
            challenge_id=ctx.challenge_id,
            success=bool(ctx.flag_candidate),
            flag=ctx.flag_candidate,
            method="automated",
            agents_used=ctx.active_agents,
            duration_seconds=(datetime.utcnow() - ctx.started_at).total_seconds(),
            error=ctx.error,
        )
        self.session.add(result)
        self.session.commit()
    
    async def _finalize_result(self) -> SolveResult:
        result = self.session.query(SolveResult).filter_by(challenge_id=self._context.challenge_id).first()
        if not result:
            result = SolveResult(challenge_id=self._context.challenge_id, success=False, error=self._context.error)
            self.session.add(result)
            self.session.commit()
        return result
    
    # --- Preconditions ---
    
    async def _pre_triage_done(self, ctx: OrchestratorContext) -> bool:
        return ctx.findings_count > 0
    
    async def _pre_scope_defined(self, ctx: OrchestratorContext) -> bool:
        return bool(ctx.challenge.target_scope)
    
    async def _pre_discovery_done(self, ctx: OrchestratorContext) -> bool:
        return len(ctx.active_agents) > 1
    
    async def _pre_hypotheses_exist(self, ctx: OrchestratorContext) -> bool:
        return ctx.hypotheses_count > 0
    
    async def _pre_investigation_done(self, ctx: OrchestratorContext) -> bool:
        return True  # Always proceed
    
    async def _pre_exploit_validated(self, ctx: OrchestratorContext) -> bool:
        return True
    
    async def _pre_flag_candidate(self, ctx: OrchestratorContext) -> bool:
        return bool(ctx.flag_candidate)
    
    # --- Helpers ---
    
    def _get_orchestrator_prompt(self, challenge: Challenge) -> str:
        cats = ", ".join(c.value for c in challenge.category)
        return f"""You are the CTF Orchestrator for: {challenge.name}
Categories: {cats}
Flag: {challenge.flag_format}

Responsibilities:
1. Decompose challenge into subtasks
2. Spawn specialist agents
3. Coordinate parallel execution
4. Generate hypotheses from findings
5. Plan experiments to test hypotheses
6. Craft exploits for supported hypotheses
7. Verify flag capture

Workflow: OBSERVE -> HYPOTHESIZE -> EXPERIMENT -> MEASURE -> CONCLUDE -> REPEAT"""
    
    def _get_specialist_prompt(self, role: AgentRole) -> str:
        prompts = {
            AgentRole.WEB: "Web specialist: enumerate endpoints, fingerprint tech, test injections, analyze auth",
            AgentRole.CRYPTO: "Crypto specialist: identify algorithms, find weak params, test math hypotheses",
            AgentRole.PWN: "Pwn specialist: fingerprint binary, check protections, find vulns, build exploits",
            AgentRole.REVERSE: "Reverse specialist: analyze binary, extract logic, identify vulns, decompile",
            AgentRole.FORENSICS: "Forensics specialist: analyze files, parse PCAP, carve artifacts, build timelines",
        }
        return prompts.get(role, "Security specialist: analyze, enumerate, test, document")
    
    def _get_tools_for_role(self, role: AgentRole) -> List[str]:
        tools = {
            AgentRole.WEB: ["nmap", "ffuf", "httpx", "nuclei", "curl", "python_sandbox"],
            AgentRole.CRYPTO: ["openssl", "python_sandbox", "hashcat", "john"],
            AgentRole.PWN: ["gdb", "checksec", "pwntools", "python_sandbox"],
            AgentRole.REVERSE: ["ghidra", "radare2", "strings", "python_sandbox"],
            AgentRole.FORENSICS: ["file", "strings", "binwalk", "volatility3", "python_sandbox"],
            AgentRole.OSINT: ["whois", "dig", "curl", "python_sandbox"],
            AgentRole.STEGO: ["steghide", "zsteg", "exiftool", "binwalk", "python_sandbox"],
        }
        return tools.get(role, ["python_sandbox"])
    
    async def _normalize_observation(self, te: ToolExecution, result):
        """Convert raw tool output to normalized observation."""
        if not result.success or not result.stdout:
            return
        
        tool = te.tool_name
        stdout = result.stdout
        
        obs_data = None
        if tool == "nmap":
            obs_data = ServiceObservation.from_raw(stdout)
        elif tool in ("ffuf", "feroxbuster", "gobuster"):
            obs_data = EndpointObservation.from_raw(stdout)
        elif tool == "file":
            # Would need file path
            pass
        elif tool == "strings":
            obs_data = StringObservation.from_raw(stdout, filename=te.arguments.get("file", ""))
        elif tool == "binwalk":
            obs_data = EmbeddedArtifactObservation.from_raw(stdout)
        
        if obs_data:
            obs = Observation(
                challenge_id=self._context.challenge_id,
                agent_id=te.agent_id,
                tool_execution_id=te.id,
                source_tool=tool,
                observation_type=obs_data.__class__.__name__.replace("Observation", "").lower(),
                normalized_data=obs_data.to_dict(),
            )
            self.session.add(obs)
            self.session.commit()
    
    def _extract_flag(self, text: str) -> Optional[str]:
        import re
        match = re.search(r'flag\{[^}]+\}', text)
        return match.group(0) if match else None
    
    # --- Callbacks ---
    
    async def _on_agent_start(self, agent: RuntimeAgent):
        db_agent = self.session.query(Agent).get(agent.config.id)
        if db_agent:
            db_agent.state = AgentState.EXECUTING
            db_agent.started_at = datetime.utcnow()
            self.session.commit()
    
    async def _on_agent_complete(self, agent: RuntimeAgent):
        db_agent = self.session.query(Agent).get(agent.config.id)
        if db_agent:
            db_agent.state = AgentState.COMPLETED
            db_agent.completed_at = datetime.utcnow()
            db_agent.final_result = agent.final_result
            db_agent.error = agent.error
            self.session.commit()
    
    async def _on_agent_error(self, agent: RuntimeAgent, error: Exception):
        db_agent = self.session.query(Agent).get(agent.config.id)
        if db_agent:
            db_agent.state = AgentState.FAILED
            db_agent.error = str(error)
            db_agent.completed_at = datetime.utcnow()
            self.session.commit()
    
    async def _on_sub_agent_spawn(self, parent: RuntimeAgent, child: RuntimeAgent):
        pass  # Already tracked in active_agents
    
    # --- Query Methods ---
    
    def get_challenge(self, challenge_id: str) -> Optional[Challenge]:
        return self.session.query(Challenge).get(challenge_id)
    
    def list_challenges(self) -> List[Challenge]:
        return self.session.query(Challenge).all()
    
    def get_status(self, challenge_id: str) -> Dict[str, Any]:
        challenge = self.get_challenge(challenge_id)
        if not challenge:
            return {"error": "Not found"}
        
        agents = self.session.query(Agent).filter_by(challenge_id=challenge_id).all()
        result = self.session.query(SolveResult).filter_by(challenge_id=challenge_id).first()
        
        return {
            "challenge": {
                "id": challenge.id,
                "name": challenge.name,
                "categories": [c.value for c in challenge.category],
                "type": challenge.challenge_type.value,
            },
            "state": self._context.state.value if self._context and self._context.challenge_id == challenge_id else "idle",
            "agents": [{"id": a.id, "role": a.role.value, "state": a.state.value} for a in agents],
            "result": {
                "success": result.success if result else False,
                "flag": result.flag if result else None,
            } if result else None,
        }
    
    def generate_report(self, challenge_id: str) -> Dict[str, Any]:
        challenge = self.get_challenge(challenge_id)
        result = self.session.query(SolveResult).filter_by(challenge_id=challenge_id).first()
        
        findings = self.session.query(Finding).filter_by(challenge_id=challenge_id).all()
        evidence = self.session.query(Evidence).filter_by(challenge_id=challenge_id).all()
        experiments = self.session.query(Experiment).filter_by(challenge_id=challenge_id).all()
        tool_execs = self.session.query(ToolExecution).filter_by(challenge_id=challenge_id).all()
        
        return {
            "challenge": {"id": challenge.id, "name": challenge.name, "categories": [c.value for c in challenge.category]},
            "result": {"success": result.success, "flag": result.flag, "method": result.method, "duration": result.duration_seconds} if result else None,
            "findings": [{"type": f.type, "title": f.title, "confidence": f.confidence} for f in findings],
            "evidence": [{"type": e.type, "title": e.title, "status": e.status.value} for e in evidence],
            "experiments": [{"name": e.name, "tool": e.tool_name, "status": e.status} for e in experiments],
            "tool_executions": len(tool_execs),
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    def close(self):
        self.session.close()
        self.engine.dispose()