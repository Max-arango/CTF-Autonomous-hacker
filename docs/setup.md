# Autonomous CTF Environment - Setup Guide

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04+, Debian 12+, Arch, Fedora)
- **Docker**: 24.0+ with Compose v2
- **RAM**: 8GB minimum, 16GB+ recommended
- **Disk**: 20GB+ free space
- **CPU**: 4+ cores recommended

### For Local LLM (Optional)

- **Ollama**: For running local models
- **GPU**: NVIDIA GPU with CUDA for acceleration
- **VRAM**: 8GB+ for 7B models, 16GB+ for larger

## Installation

### 1. Install Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

### 2. Clone Repository

```bash
git clone https://github.com/your-org/autonomous-ctf-environment.git
cd autonomous-ctf-environment
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required: Nemotron API Key (get from NVIDIA)
NEMOTRON_API_KEY=your-api-key-here

# Optional: Local Ollama (if not using Nemotron)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://host.docker.internal:11434

# Optional: Custom paths
# WORKSPACE_PATH=/custom/workspace
# ARTIFACTS_PATH=/custom/artifacts
# LOGS_PATH=/custom/logs
```

### 4. Build Images

```bash
# Build all images (takes 10-30 minutes first time)
make build

# Or build specific images
make build-ormstrator
make build-agent-web
```

### 5. Start Services

```bash
# Start core services (DB, Redis, Orchestrator, Permission Manager)
make up

# Start with agent profiles (optional)
docker compose --profile agents up -d

# Check status
make status
```

### 6. Verify Installation

```bash
# Check orchestrator health
curl http://localhost:8000/health

# Check permission manager
curl http://localhost:8080/health

# View logs
make logs-orchestrator
```

## Usage

### CLI Interface

```bash
# Install CLI
pip install -e .

# Or run via Docker
docker compose run --rm orchestrator ctf --help
```

### Adding Challenges

```bash
# From directory
ctf challenge add ./my-challenge

# From archive
ctf challenge add ./challenge.zip

# With metadata
ctf challenge add ./challenge --name "My Challenge" --type MACHINE
```

### Solving Challenges

```bash
# List challenges
ctf challenge list

# Inspect challenge
ctf challenge inspect <challenge-id>

# Solve
ctf solve <challenge-id>

# View results
ctf report <challenge-id>
```

### Monitoring

```bash
# View active agents
ctf agents

# View findings
ctf findings <challenge-id>

# View artifacts
ctf artifacts

# View logs
ctf logs
```

## Development

### Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests
make test-integration

# Security tests
make test-security
```

### Code Quality

```bash
# Lint
make lint

# Format
make fmt

# Type check
make typecheck
```

### Adding New Agents

1. Create Dockerfile:
```bash
mkdir -p docker/agent-mycustom
# Edit docker/agent-mycustom/Dockerfile
```

2. Create skill:
```bash
mkdir -p skills/ctf-mycustom
# Edit skills/ctf-mycustom/system_prompt.md
```

3. Register in configs:
```yaml
# configs/agents.yaml
mycustom:
  enabled: true
  model: nemotron-3-5-lightning-free
  # ...
```

4. Add to docker-compose.yml with appropriate profile

5. Rebuild:
```bash
make build-agent-mycustom
```

## Troubleshooting

### Common Issues

#### Build Failures

```bash
# Clean and rebuild
make clean
make build

# Check specific build
docker compose build agent-web --no-cache
```

#### Container Start Failures

```bash
# Check logs
docker compose logs agent-web

# Check resources
docker system df
docker system prune -f
```

#### Permission Errors

```bash
# Check permission manager logs
make logs-perm

# Verify audit logs
curl http://localhost:8080/permissions/audit/log
```

#### LLM Connection Issues

```bash
# Test Nemotron API
curl -H "Authorization: Bearer $NEMOTRON_API_KEY" \
  https://integrate.api.nvidia.com/v1/models

# Test Ollama
curl http://localhost:11434/api/tags
```

#### Database Issues

```bash
# Reset database
docker compose down -v
make up
```

### Debug Mode

```bash
# Enable debug logging
DEBUG=true LOG_LEVEL=DEBUG make up

# Shell into orchestrator
make shell

# Manual agent execution
docker compose run --rm agent-web bash
```

## Performance Tuning

### Resource Allocation

Adjust in `configs/docker.yaml`:

```yaml
agent_profiles:
  web:
    cpus: "2.0"
    memory: "4g"
  crypto:
    cpus: "4.0"
    memory: "8g"
  ai_security:
    cpus: "4.0"
    memory: "16g"
```

### Parallel Execution

Configure in `configs/system.yaml`:

```yaml
orchestrator:
  max_parallel_agents: 8
agent_runtime:
  max_active_agents: 32
```

### LLM Optimization

- Use streaming for long responses
- Adjust temperature per agent type
- Cache frequent queries
- Use smaller models for simple tasks

## Maintenance

### Updates

```bash
# Pull latest images
docker compose pull

# Rebuild with latest base images
make build

# Update dependencies
docker compose run --rm orchestrator pip install --upgrade -e ".[dev]"
```

### Backup

```bash
# Backup database
docker compose exec db pg_dump -U ctf ctf > backup.sql

# Backup artifacts
tar -czf artifacts-backup.tar.gz artifacts/

# Backup configs
tar -czf config-backup.tar.gz configs/
```

### Cleanup

```bash
# Remove stopped containers
docker compose down

# Remove all data
docker compose down -v

# Clean Docker system
docker system prune -af
```

## Support

### Getting Help

- Check logs: `make logs`
- Run diagnostics: `ctf status`
- Review documentation: `docs/`
- Submit issues: GitHub Issues

### Log Locations

- Application: `logs/ctf.log`
- Audit: `logs/audit.log`
- Docker: `docker compose logs <service>`