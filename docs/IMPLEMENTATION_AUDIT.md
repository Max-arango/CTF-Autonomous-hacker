# Implementation Audit Report

## Executive Summary

The repository contains a **scaffold-heavy architecture** with substantial structural code but **minimal functional implementation**. While the directory structure, configurations, Dockerfiles, and type definitions are well-organized, the actual runtime behavior is largely non-functional:

- **Agents don't actually execute tools** - the LLM is asked to produce tool calls but the execution engine only implements generic shell command execution
- **Tool wrappers are stubs** - `_register_builtin_wrappers()` is a pass-through; no real wrappers exist
- **Evidence Engine is incomplete** - hypothesis/exploit verification returns UNVERIFIED with placeholder notes
- **API endpoints return empty placeholders** - findings, artifacts endpoints return hardcoded empty arrays
- **Challenge state is in-memory only** - no database persistence for critical state
- **Permission Manager has Docker socket access** - critical security vulnerability
- **Workspace is shared RW** - no isolation between agents
- **No deterministic triage** - classification relies entirely on LLM
- **No hypothesis engine** - no structured hypothesis management
- **No attack graph** - no structured vulnerability/asset tracking
- **No recursive agent budgeting** - sub-agents can exhaust parent resources
- **Malware analysis runs in normal agent container** - no hostile artifact isolation

---

## Component-by-Component Audit

### 1. Docker Infrastructure

| Component | Claimed | Actual | Status | Security Risk |
|-----------|---------|--------|--------|---------------|
| `docker-compose.yml` | 5 networks, isolated agents | Networks defined but all agents share RW workspace volume | Partial | HIGH - workspace shared RW |
| `permission-manager` | Privileged service for controlled ops | Runs as root WITH Docker socket mount | **Broken** | **CRITICAL** - full host container control |
| Agent containers | Non-root, capability-dropped | Dockerfiles create `ctf` user but compose overrides with RW volumes | Partial | MEDIUM |
| Networks | 5 isolated networks | Defined but not enforced at runtime | Partial | MEDIUM |

### 2. Permission Manager (`src/permissions/manager.py`)

| Capability | Claimed | Actual | Status |
|------------|---------|--------|--------|
| `INSTALL_PACKAGE` | Controlled package installation | Executes arbitrary `apt-get install` via shell | **Insecure** - command injection via package_name |
| `CREATE_RESTRICTED_MOUNT` | Create bind mounts | Returns `not_implemented` | **Stub** |
| `CONFIGURE_ISOLATED_NETWORK` | Network namespace config | Returns `not_implemented` | **Stub** |
| `SET_REQUIRED_DEVICE_PERMISSION` | Device access | Returns `not_implemented` | **Stub** |
| `PERFORM_CONTROLLED_PRIVILEGED_OPERATION` | Specific privileged ops | Returns `not_implemented` | **Stub** |
| `MANAGE_CONTAINER_LIFECYCLE` | Container control | Returns `not_implemented` | **Stub** |
| `READ_AUDIT_LOGS` | Audit log access | Returns in-memory log | Partial |

**Critical Issues:**
- Line 193: `cmd = f"apt-get update && apt-get install -y {package_name}"` - direct shell interpolation, command injection
- Line 84: Docker socket mounted read-only but still allows container lifecycle control
- All agents can request `INSTALL_PACKAGE` (config lines 130-186)
- No scope validation - agents can install packages without challenge context

### 3. Execution Engine (`src/execution/engine.py`)

| Feature | Claimed | Actual | Status |
|---------|---------|--------|--------|
| Tool Registry | Loads from config | Loads but no wrappers registered | Partial |
| Tool Wrappers | Specialized per-tool | `_register_builtin_wrappers()` is `pass` | **Stub** |
| Command Execution | Safe execution | Uses `asyncio.create_subprocess_shell()` with user-controlled strings | **Insecure** |
| Argument Validation | Per-tool schemas | Only checks tool allowlist | **Missing** |
| Scope Enforcement | Network/filesystem | Not implemented | **Missing** |
| Resource Limits | Timeout, CPU, memory | Only timeout implemented | Partial |

**Critical Issues:**
- Lines 267-299: `_build_*_command` methods use `shlex.quote()` but still execute via shell
- Line 327: `create_subprocess_shell()` with formatted command string - injection risk
- No argv-based execution, no seccomp, no resource limits beyond timeout
- Agent's `allowed_tools` checked but not enforced against tool capabilities

### 4. Orchestrator (`src/orchestrator/orchestrator.py`)

| Feature | Claimed | Actual | Status |
|---------|---------|--------|--------|
| Challenge Classification | LLM + deterministic | LLM only, no deterministic triage | **Incomplete** |
| State Machine | INTAKE→TRIAGE→...→COMPLETE | Single `solve_challenge()` call | **Missing** |
| Agent Delegation | Recursive with budgets | Spawns one orchestrator agent, no recursive budgeting | Partial |
| Hypothesis Management | Structured | Agent-level only, no central hypothesis engine | **Missing** |
| Attack Graph | Asset/vuln tracking | Not implemented | **Missing** |
| Flag Validation | Evidence-based | Calls evidence engine but minimal verification | Partial |
| Persistence | Database-backed | In-memory dicts `_active_challenges`, `_solve_results` | **Missing** |

**Critical Issues:**
- `solve_challenge()` creates ONE orchestrator agent and delegates everything to it
- No continuous orchestration loop - fire and forget
- Challenge state in memory only (`_active_challenges`, `_solve_results`)
- `credentials` stored in plaintext in Challenge model

### 5. Agent Runtime (`src/runtime/runtime.py`)

| Feature | Claimed | Actual | Status |
|---------|---------|--------|--------|
| Lifecycle States | 8 states | Implemented | ✓ |
| Resource Budgets | Tokens, time, sub-agents, commands | Tracked but not enforced against parent | Partial |
| Recursive Delegation | Max depth 4, max 32 agents | Depth checked, but sub-agent budget not inherited | **Broken** |
| Plan Generation | LLM-driven | Asks LLM for JSON plan | Works but fragile |
| Step Execution | Tool calls via LLM | LLM generates tool calls, executed via execution engine | Works but fragile |
| Evidence Validation | Per-finding | Calls evidence engine | Works but evidence engine incomplete |

**Critical Issues:**
- Lines 93-98: Sub-agent gets fresh `ResourceBudget`, not child of parent budget
- Line 278: Tools per step from LLM plan, not validated against agent capabilities
- No scope enforcement in tool execution
- `_get_tool_definitions()` returns hardcoded 3 tools only

### 6. Evidence Engine (`src/evidence/engine.py`)

| Claim Type | Verification | Status |
|------------|--------------|--------|
| Observation | Artifact existence | Works |
| Hypothesis | Returns UNVERIFIED | **Stub** |
| Evidence | Artifact existence | Works |
| Exploit | Artifact existence only | **Incomplete** - no behavioral verification |
| Proof/Flag | Format + artifact | Works |

**Missing:**
- No experiment tracking integration
- No behavioral verification (shell obtained, privilege escalation, etc.)
- No reproducibility checking
- Hypothesis verification returns placeholder

### 7. API Endpoints (`src/orchestrator/main.py`)

| Endpoint | Status |
|----------|--------|
| `POST /challenges` | Works |
| `GET /challenges` | Works |
| `GET /challenges/{id}` | Works |
| `POST /challenges/{id}/solve` | Works (but orchestrator incomplete) |
| `GET /challenges/{id}/agents` | Works |
| `GET /challenges/{id}/findings` | **Returns `{"findings": []}`** - **Stub** |
| `GET /challenges/{id}/artifacts` | **Returns `{"artifacts": []}`** - **Stub** |
| `GET /challenges/{id}/report` | Works |
| `POST /agents/{id}/cancel` | Works |
| `GET /agents` | Works |

### 8. Memory System (`src/memory/manager.py`)

| Feature | Status |
|---------|--------|
| 3-layer memory (short/task/long) | Implemented in-memory |
| Indexing by agent/challenge/type/layer/tag | Implemented |
| TTL cleanup | Implemented |
| Promotion between layers | Implemented |
| Finding storage | Implemented |
| Experiment tracking | Implemented |
| Persistence | **Missing** - all in-memory |
| Credential isolation | **Missing** - credentials stored in findings |

### 9. Artifact System (`src/artifacts/manager.py`)

| Feature | Status |
|---------|--------|
| Content-addressed storage (SHA256) | ✓ |
| Deduplication | ✓ |
| Metadata indexing | ✓ |
| Relationships | ✓ |
| File storage | ✓ |
| Persistence | Index saved to JSON, but no DB |
| Large binary handling | Loads entirely into memory |

### 10. Configuration

| Config File | Quality |
|-------------|---------|
| `system.yaml` | Comprehensive |
| `agents.yaml` | Comprehensive (21 agents) |
| `tools.yaml` | Comprehensive (100+ tools) |
| `permissions.yaml` | Good structure, but too permissive |
| `docker.yaml` | Good profiles |

### 11. Tests

| Category | Files | Quality |
|----------|-------|---------|
| Unit | 5 | Test core models, not integration |
| Integration | 2 | Mock-heavy, test orchestrator flow |
| Security | 3 | Test config validation, not runtime enforcement |

---

## Security Risk Assessment

### CRITICAL (Must Fix Immediately)

1. **Docker Socket in Permission Manager** - Full host container escape
2. **Command Injection in Permission Manager** - `apt-get install {package_name}` via shell
3. **Shell Command Execution in Execution Engine** - `create_subprocess_shell()` with formatted strings
4. **Shared RW Workspace** - All agents can overwrite each other's files
5. **Plaintext Credentials** - Stored in Challenge model, accessible via API

### HIGH

6. **No Scope Enforcement** - Agents can scan/attack any target
7. **No Tool Argument Validation** - Arbitrary arguments passed to commands
8. **All Agents Can Install Packages** - Supply chain risk
9. **In-Memory State Only** - No persistence, no audit trail
10. **Sub-Agent Budget Not Inherited** - Recursive resource exhaustion

### MEDIUM

11. **Evidence Engine Incomplete** - Cannot verify exploits/hypotheses
12. **API Placeholders** - Findings/artifacts endpoints non-functional
13. **No Deterministic Triage** - LLM-only classification
14. **No Hypothesis Engine** - No structured reasoning tracking
15. **Malware Analysis in Normal Container** - No hostile isolation

---

## Proposed Corrections (Priority Order)

### P0 - Security Architecture (Week 1)
1. **Remove Docker socket** from Permission Manager
2. **Rewrite Permission Manager** - capability-based, no arbitrary ops
3. **Implement Scope Engine** - validate every network/filesystem action
4. **Secure Command Execution** - argv-based, no shell, seccomp
5. **Isolate Workspaces** - per-agent private directories
6. **Secret Management** - CredentialRef, redaction

### P1 - Core Runtime (Week 2)
7. **Orchestrator State Machine** - continuous, not single-shot
10. **Deterministic Triage** - file magic, MIME, metadata
11. **Hypothesis Engine** - structured with ranking
12. **Evidence Engine Completion** - behavioral verification
13. **Artifact System** - DB-backed, streaming for large files
14. **Resource Governor** - central accounting, child budgets
15. **Recursive Delegation** - proper budget inheritance

### P2 - Specialist Agents MVP (Week 3)
16. **Web Agent** - real wrappers (ffuf, httpx, nuclei, sqlmap)
17. **Crypto Agent** - real wrappers (hashcat, john, openssl, sage)
18. **Pwn Agent** - real wrappers (gdb, pwntools, checksec, ropper)
19. **Reverse Agent** - real wrappers (ghidra, radare2, angr)
20. **Forensics Agent** - real wrappers (volatility, binwalk, foremost)

### P3 - Platform Features (Week 4+)
21. **Remaining Specialists**
22. **Attack/Defense Mode**
23. **Benchmark Suite**
24. **Replay Engine**
25. **Advanced Observability**

---

## File-Level Action Items

### Delete/Replace
- `src/permissions/manager.py` - Complete rewrite (remove Docker socket, shell exec)
- `src/execution/engine.py` - Replace shell execution with argv-based executor
- `src/orchestrator/orchestrator.py` - Implement state machine
- `src/orchestrator/main.py` - Connect placeholder endpoints
- `docker-compose.yml` - Remove Docker socket mount, fix workspace isolation

### Create New
- `src/security/scope.py` - Scope validation engine
- `src/security/capabilities.py` - Capability definitions
- `src/security/policy.py` - Policy decision engine
- `src/security/authorization.py` - Authorization context
- `src/security/secrets.py` - CredentialRef, redaction
- `src/security/schemas.py` - Tool argument schemas
- `src/reasoning/hypotheses.py` - Hypothesis management
- `src/reasoning/ranking.py` - Priority calculation
- `src/reasoning/experiments.py` - Experiment tracking
- `src/reasoning/dead_end.py` - Dead-end detection
- `src/triage/deterministic.py` - File-based classification
- `src/graph/attack_graph.py` - Attack graph model
- `src/execution/wrappers/*.py` - Real tool wrappers
- `src/execution/sandbox.py` - Secure execution context

### Modify
- `docker-compose.yml` - Remove socket, isolate volumes, fix networks
- `configs/permissions.yaml` - Remove INSTALL_PACKAGE from most agents
- `configs/tools.yaml` - Add argument schemas
- `src/runtime/runtime.py` - Budget inheritance, scope passing
- `src/evidence/engine.py` - Complete verification methods
- `src/memory/manager.py` - Add persistence, credential isolation
- `src/artifacts/manager.py` - Add streaming, DB backend
- `src/cli.py` - Implement all commands