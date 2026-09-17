# Autonomous CTF Solver

**Local-first, security-hardened autonomous CTF solving platform.** Runs on your machine with pluggable LLM backends (Ollama, OpenRouter, NVIDIA NIM, Anthropic, OpenAI, vLLM).

## Features

- **Local-first**: SQLite database, local artifact storage, no external dependencies required
- **Pluggable LLMs**: Ollama (local), OpenRouter, NVIDIA NIM, Anthropic, OpenAI, vLLM, custom OpenAI-compatible endpoints
- **Security-hardened**: Minimal capabilities, no shell access, explicit scope enforcement, python sandbox execution
- **Autonomous**: State-machine orchestrator (INTAKE → TRIAGE → SCOPE → DISCOVERY → HYPOTHESIS → INVESTIGATION → EXPLOITATION → VALIDATION → FLAG_VERIFICATION → REPORT)
- **Specialist agents**: Web, Crypto, Pwn, Reverse, Forensics, OSINT, Stego, Mobile, Malware, Cloud, Network, Supply Chain, AD, Web3, AI Security, Sidechannel, Firmware, Social, Programming, Meta
- **Observation normalization**: Structured parsers for nmap, ffuf, file, strings, binwalk
- **Full audit trail**: SQLite-backed audit logs, evidence chain, reproducible investigations

## Quick Start

### 1. Install Dependencies
```bash
# Ubuntu/Debian
sudo apt-get install python3-sqlalchemy python3-httpx python3-typer python3-yaml python3-aiofiles python3-docker

# Arch Linux
sudo pacman -S python-sqlalchemy python-httpx python-typer python-yaml python-aiofiles python-docker

# Or via pip (if available)
pip install sqlalchemy httpx typer pyyaml aiofiles docker
```

### 2. Install the Package
```bash
cd autonomous-ctf-environment
pip install -e .
```

### 3. Configure LLM Provider
```bash
cp .env.example .env
# Edit .env with your preferred provider (see LLM Providers below)
```

### 4. Initialize Database
```bash
ctf init
```

### 5. Start Solving
```bash
# Add a challenge
ctf challenge add "web-basic" --desc "Hidden flag in HTML comment" --cat web --target 10.10.10.100

# Solve autonomously
ctf solve <challenge-id>

# Monitor progress
ctf status <challenge-id>
ctf report <challenge-id> -o report.html
ctf replay <challenge-id>
```

## LLM Providers

The agent's "brain" is completely pluggable. Configure in `.env`:

### Ollama (Local, Default)
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=nemotron-3-5-lightning-free
```
```bash
# Install model
ollama pull nemotron-3-5-lightning-free
ollama serve
```

### OpenRouter (Cloud, 300+ models)
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
# Or: openai/gpt-4o, meta-llama/llama-3.1-405b, etc.
```

### NVIDIA NIM (Cloud)
```bash
LLM_PROVIDER=nim
NIM_API_KEY=nvapi-xxxxx
NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NIM_MODEL=meta/llama-3.1-405b-instruct
```

### Anthropic (Cloud)
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### OpenAI (Cloud)
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o
```

### vLLM (Self-hosted)
```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=meta-llama/Meta-Llama-3.1-405B-Instruct
```

### Custom OpenAI-Compatible
```bash
LLM_PROVIDER=custom
CUSTOM_BASE_URL=http://your-endpoint/v1
CUSTOM_API_KEY=your-key
CUSTOM_MODEL=your-model-name
```

## CLI Reference

```bash
# Challenge Management
ctf challenge add "name" --desc "..." --cat web,crypto --target 10.10.10.100
ctf challenge list
ctf challenge inspect <id>
ctf challenge delete <id>

# Solving
ctf solve <id> [--timeout 3600] [--parallel 4]

# Monitoring
ctf status <id>
ctf report <id> [-o report.html]
ctf replay <id> [--step 5]

# Debugging
ctf agents <id>
ctf findings <id> [--type observation]
ctf hypotheses <id> [--status proposed]
ctf experiments <id>
ctf evidence <id>
ctf artifacts <id>
ctf logs <id> [-n 50]

# Benchmarks & Security
ctf benchmark [--suite web|crypto|pwn|reverse|forensics|all] [--parallel 2]
ctf security-audit [-o audit.json]

# Utilities
ctf init                    # Initialize database
ctf version                 # Show version
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LOCAL MACHINE                          │
├─────────────────────────────────────────────────────────────┤
│  ctf CLI (typer)                                            │
│       │                                                     │
│       ▼                                                     │
│  Orchestrator (single process, async state machine)         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ INTAKE → TRIAGE → SCOPE → DISCOVERY → HYPOTHESIS     │  │
│  │ → INVESTIGATION → EXPLOITATION → VALIDATION          │  │
│  │ → FLAG_VERIFICATION → REPORT → COMPLETE              │  │
│  └───────────────────────────────────────────────────────┘  │
│       │                    │                    │           │
│       ▼                    ▼                    ▼           │
│  SQLite DB            LLM Provider           Python Sandbox  │
│  (ctf.db)             (Ollama/OpenRouter/    (resource-      │
│                       Anthropic/etc.)       limited)         │
│                                                              │
│  Docker SDK (on-demand specialist containers)              │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules (`src/core/`)
| Module | Purpose |
|--------|---------|
| `db.py` | SQLAlchemy + SQLite (WAL mode, optimized pragmas) |
| `models.py` | 18 tables: Challenge, Agent, Finding, Hypothesis, Experiment, ToolExecution, Observation, Evidence, Artifact, SolveResult, AuditEvent, AgentIdentity, ResourceBudget, ToolCost |
| `permissions.py` | In-process PermissionManager (READ_AUDIT_LOGS only) |
| `resources.py` | ResourceGovernor with cascading budgets + tool cost model |
| `orchestrator.py` | Single-process state machine (11 states) |

### Security Model (Stage 1 Hardened)
- **No shell access**: Only `execute_python_sandbox` with resource limits
- **Minimal capabilities**: Only `READ_AUDIT_LOGS` exposed to agents
- **Explicit scope**: `ChallengeScope` with TARGET/DISCOVERY/LATERAL/CONTROL (no auto subnet expansion)
- **Network authorization**: DNS resolution → IP validation → scope check (blocks localhost, link-local, metadata 169.254.169.254)
- **Agent identity**: Explicit `AgentIdentity` with signed identity (no `agent_id.split()`)
- **Success semantics**: `not_implemented` never returns `success=true`

### Observation Normalization
| Tool | Parser | Output |
|------|--------|--------|
| nmap | `ServiceObservation` | ports, services, versions, OS fingerprint |
| ffuf/feroxbuster/gobuster | `EndpointObservation` | endpoints, status codes, response sizes |
| file | `FileTypeObservation` | MIME type, extension, confidence |
| strings | `StringObservation` | strings + secret/URL/IP/flag detection |
| binwalk | `EmbeddedArtifactObservation` | embedded files, filesystems, signatures |

## Development

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check src/

# Type check
mypy src/

# Format
ruff format src/
```

## Project Structure

```
autonomous-ctf-environment/
├── .env.example           # LLM provider configuration template
├── configs/
│   ├── permissions.yaml   # Minimal capabilities (READ_AUDIT_LOGS only)
│   └── system.yaml        # System settings
├── src/
│   ├── cli.py             # Typer CLI entry point
│   ├── core/              # Core engine (db, models, perms, resources, orchestrator)
│   ├── llm/               # LLM providers (ollama, openrouter, nim, anthropic, openai, vllm, custom)
│   ├── runtime/           # Agent runtime + identity
│   ├── execution/         # Python sandbox + tool registry
│   ├── observations/      # Normalized parsers (nmap, ffuf, file, strings, binwalk)
│   ├── network/           # DNS + scope authorization
│   ├── scope/             # ChallengeScope engine
│   ├── evidence/          # Evidence engine
│   ├── artifacts/         # Artifact storage
│   ├── challenges/        # Challenge management
│   ├── memory/            # Vector memory (optional)
│   ├── observability/     # Structured logging + audit
│   └── config/            # Settings + YAML loader
├── docker/                # Specialist agent Dockerfiles
├── examples/              # Example challenges
├── tests/                 # Unit + security tests
├── pyproject.toml         # Package config
└── ctf.db                 # SQLite database (created on init)
```

## Security & Authorization

This platform executes offensive security tooling **only inside explicitly authorized CTF/challenge scopes**. 

- All network access validated against `ChallengeScope`
- No host Docker socket access
- No arbitrary shell commands
- No privilege escalation paths
- Audit trail for every action

**Use only for authorized CTF challenges, educational purposes, and security research.**

## License

MIT License - For authorized CTF use only.