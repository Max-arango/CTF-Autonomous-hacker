# Autonomous CTF Environment

A Dockerized, modular, autonomous multi-agent CTF environment capable of solving authorized Jeopardy, Machines and Attack/Defense CTF challenges.

## Architecture Overview

The system consists of:

- **Orchestrator**: Central coordination engine for challenge intake, classification, agent scheduling, and result aggregation
- **Specialized Agents**: 20+ domain-specific security agents (Web, Crypto, Pwn, Reverse, Forensics, etc.)
- **Agent Runtime**: Lightweight internal agent runtime with recursive sub-agent delegation
- **Tool Registry**: Managed tool execution with security wrappers
- **Permission Manager**: Privileged service for controlled elevated operations
- **Memory System**: Multi-layer memory (short-term, task, long-term)
- **Evidence Engine**: Independent verification of claims and findings
- **Experiment Engine**: Structured hypothesis testing
- **Artifact Storage**: Standardized artifact management with hashing
- **Observability**: Structured logging, audit trails, and monitoring

## Quick Start

```bash
# Copy environment template
cp .env.example .env

# Build and start
make build
make up

# Add a challenge
ctf challenge add ./challenge.zip

# Start solving
ctf solve
```

## Project Structure

```
autonomous-ctf-environment/
├── configs/           # Configuration files
├── docker/            # Dockerfiles for each component
├── src/               # Source code
│   ├── orchestrator/  # Central orchestration engine
│   ├── agents/        # Agent implementations
│   ├── runtime/       # Agent runtime
│   ├── llm/           # LLM provider abstraction
│   ├── memory/        # Memory system
│   ├── execution/     # Tool execution engine
│   ├── permissions/   # Permission manager
│   ├── artifacts/     # Artifact storage
│   ├── evidence/      # Evidence engine
│   ├── challenges/    # Challenge management
│   ├── attack_defense/# Attack/Defense mode
│   ├── reporting/     # Report generation
│   ├── observability/ # Logging and monitoring
│   └── security/      # Security utilities
├── skills/            # Agent skills (executable)
├── tools/             # Tool registry and wrappers
├── tests/             # Test suites
├── examples/          # Example challenges
├── workspace/         # Runtime workspace
├── artifacts/         # Stored artifacts
├── logs/              # Log files
└── docs/              # Documentation
```

## Configuration

Key configuration files in `configs/`:

- `system.yaml` - System-wide settings
- `agents.yaml` - Agent configurations
- `tools.yaml` - Tool registry
- `permissions.yaml` - Permission policies
- `docker.yaml` - Docker settings

## Security Model

- All agents run as non-root in isolated containers
- Permission Manager is the ONLY privileged component
- No host Docker socket exposure
- Network isolation between components
- Defense-in-depth at every layer

## Development

```bash
# Run tests
make test

# Lint
make lint

# Type check
make typecheck
```

## License

MIT License - For authorized CTF use only.