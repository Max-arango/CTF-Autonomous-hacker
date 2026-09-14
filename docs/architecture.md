# Autonomous CTF Environment - Architecture Documentation

## System Overview

The Autonomous CTF Environment is a Dockerized, modular, multi-agent system for solving authorized CTF challenges. It implements a defense-in-depth security model with isolated execution environments, a privileged permission manager, and evidence-driven validation.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Host System                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Orchestrator    │  │ Permission   │  │   Database   │          │
│  │   (FastAPI)       │  │   Manager    │  │  (PostgreSQL)│          │
│  │   Port: 8000      │  │   Port: 8080 │  │  Port: 5432  │          │
│  └──────┬─────────┘  └──────┬─────────┘  └──────────────┘          │
│         │                   │                                        │
│         ▼                   ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Docker Networks                           │   │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐ ┌────────┐ │   │
│  │  │ Control │ │Workspace │ │ Targets │ │Malware │ │Atk/Def │ │   │
│  │  └─────────┘ └──────────┘ └─────────┘ └────────┘ └────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │                   │                   │                  │
│    ┌────┴────┐        ┌────┴────┐        ┌────┴────┐            │
│    ▼         ▼        ▼         ▼        ▼         ▼            │
│ ┌─────┐ ┌─────┐   ┌─────┐ ┌─────┐   ┌─────┐ ┌─────┐            │
│ │ Web │ │Crypto│   │ Pwn │ │ Rev │   │Foren│ │ ... │ 20 Agents  │
│ └─────┘ └─────┘   └─────┘ └─────┘   └─────┘ └─────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Orchestrator
Central coordination engine responsible for:
- Challenge intake and classification
- Task decomposition and agent scheduling
- Result aggregation and contradiction detection
- Final validation and flag verification

### 2. Agent Runtime
Lightweight internal agent framework with:
- Lifecycle management (CREATED → PLANNING → EXECUTING → VALIDATING → COMPLETED/FAILED)
- Recursive sub-agent delegation (max depth: 4)
- Resource budgets (tokens, time, sub-agents, commands)
- Structured messaging between agents

### 3. Specialist Agents (20+)
Each agent is a specialized container with:
- Domain-specific tools and capabilities
- Custom system prompts and workflows
- Isolated network and filesystem access
- Resource limits appropriate to domain

### 4. Permission Manager (Privileged)
The ONLY component with elevated privileges:
- Package installation
- Restricted mount creation
- Network configuration
- Device permissions
- Controlled privileged operations
- Container lifecycle management

### 5. Evidence Engine
Independent verification system:
- Verifies all agent claims
- Requires reproducibility
- Tracks verification status (UNVERIFIED → VERIFIED/DISPROVEN)
- Flag format validation

### 6. Memory System
Three-layer memory architecture:
- **Short-term**: Current task state (TTL: 1 hour)
- **Task**: Current challenge knowledge (TTL: 7 days)
- **Long-term**: Reusable patterns (TTL: 90 days, high-confidence only)

### 7. Execution Engine
Tool execution with security wrappers:
- Validated tool registry
- Parameter validation
- Timeout enforcement
- Artifact capture
- Audit logging

### 8. Artifact Management
Standardized artifact storage:
- SHA-256 content addressing
- Deduplication
- Relationship tracking
- MIME type detection

## Security Model

### Defense in Depth

1. **Container Isolation**
   - All agents run as non-root (UID 1000)
   - Read-only root filesystem
   - Dropped capabilities (ALL)
   - No new privileges
   - PID, CPU, memory limits
   - No Docker socket access

2. **Network Segmentation**
   - `ctf_control`: Orchestrator, Permission Manager
   - `ctf_workspace`: Shared workspace (all agents)
   - `ctf_targets`: CTF infrastructure (web, pwn, network, ad, cloud)
   - `ctf_malware`: Isolated malware analysis (no internet)
   - `ctf_attack_defense`: Attack/Defense exercises

3. **Privilege Separation**
   - Only Permission Manager runs as root
   - Capability-based access control
   - Default deny policy
   - Audit logging for all privileged operations

4. **Input Validation**
   - Tool wrapper parameter validation
   - Command injection prevention
   - Path traversal protection
   - Tool allowlist enforcement

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Malicious challenge files | Isolated analysis containers, no execution in orchestrator |
| Malicious tool output | Evidence engine verification, no trust |
| LLM hallucination | Evidence-driven workflow, independent verification |
| Container escape | Dropped caps, read-only fs, no docker socket, user namespace |
| Privilege escalation | Permission manager only privileged component |
| Data exfiltration | Network segmentation, no internet for malware |
| Tool misuse | Tool allowlists, parameter validation |

## Data Flow

### Challenge Solving Flow

```
1. Challenge Input
   │
   ▼
2. Challenge Triage & Classification (Orchestrator)
   │
   ▼
3. Attack Surface Identification
   │
   ▼
4. Task Decomposition & Agent Selection
   │
   ▼
5. Parallel Agent Execution (with sub-agent delegation)
   │
   ▼
6. Finding Collection & Evidence Verification
   │
   ▼
7. Contradiction Detection & Resolution
   │
   ▼
8. Exploitation Coordination
   │
   ▼
9. Flag Capture & Verification
   │
   ▼
10. Report Generation
```

### Agent Execution Flow

```
Agent Spawned
     │
     ▼
PLANNING: Generate execution plan via LLM
     │
     ▼
EXECUTING: Execute steps with tools
     │
     ├── Tool Execution → Execution Engine → Permission Manager (if needed)
     │         │
     │         ▼
     │    Artifact Capture & Audit Log
     │         │
     ▼         ▼
WAITING ←←←←←←←←← (async operations)
     │
     ▼
VALIDATING: Submit findings to Evidence Engine
     │
     ▼
COMPLETED/FAILED: Report results
```

## Deployment

### Requirements

- Docker 24+
- Docker Compose 2+
- 8GB+ RAM (16GB recommended for AI agents)
- 20GB+ disk space
- NVIDIA GPU optional (for local LLM)

### Quick Start

```bash
# Clone and configure
git clone <repo>
cd autonomous-ctf-environment
cp .env.example .env
# Edit .env with your Nemotron API key

# Build and start
make build
make up

# Verify
make status
make logs-orchestrator
```

### Adding Challenges

```bash
# Via CLI
ctf challenge add ./challenge.zip

# Via API
curl -X POST http://localhost:8000/challenges \
  -H "Content-Type: application/json" \
  -d '{"name": "My Challenge", "description": "...", "challenge_type": "JEOPARDY"}'
```

### Solving Challenges

```bash
# Via CLI
ctf solve <challenge-id>

# Via API
curl -X POST http://localhost:8000/challenges/<id>/solve
```

## Configuration

Key configuration files in `configs/`:

- `system.yaml`: System-wide settings
- `agents.yaml`: Agent configurations
- `tools.yaml`: Tool registry
- `permissions.yaml`: Permission policies
- `docker.yaml`: Docker settings

Environment variables in `.env`:

```bash
LLM_PROVIDER=nemotron
NEMOTRON_API_KEY=your-key
NEMOTRON_BASE_URL=https://integrate.api.nvidia.com/v1
DATABASE_URL=postgresql+asyncpg://ctf:ctf@db:5432/ctf
REDIS_URL=redis://redis:6379/0
CTF_MODE=JEOPARDY
```

## Extending the System

### Adding New Agents

1. Create Dockerfile in `docker/agent-<name>/`
2. Add system prompt in `skills/ctf-<name>/system_prompt.md`
3. Register in `configs/agents.yaml`
4. Add to `docker-compose.yml` with appropriate profile
5. Define tools in `configs/tools.yaml`

### Adding New Tools

1. Add tool definition to `configs/tools.yaml`
2. Create wrapper in `src/execution/wrappers.py`
3. Register in `src/execution/tools.py`
4. Add to appropriate agent container

### Custom LLM Providers

1. Implement `LLMProvider` interface in `src/llm/`
2. Register in `src/llm/factory.py`
3. Configure in `.env`

## Monitoring & Debugging

### Logs

```bash
# All services
make logs

# Specific service
make logs-orchestrator
make logs-perm
```

### Health Checks

```bash
# Orchestrator
curl http://localhost:8000/health

# Permission Manager
curl http://localhost:8080/health
```

### Metrics

Prometheus metrics available at `:9090/metrics` (when enabled)

## Troubleshooting

### Common Issues

1. **Container build fails**: Check Dockerfile syntax, base image availability
2. **Agent fails to start**: Check resource limits, network connectivity
3. **Permission denied**: Verify permission manager is running, check audit logs
4. **LLM errors**: Verify API key, check rate limits, try different provider

### Debug Mode

```bash
# Enable debug logging
DEBUG=true make up

# Shell into container
make shell
```

## License

MIT License - For authorized CTF use only.