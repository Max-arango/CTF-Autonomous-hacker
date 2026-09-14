# Autonomous CTF Environment - Debugging Guide

## Common Issues and Solutions

### 1. Orchestrator Won't Start

**Symptoms**: Container exits immediately, health check fails

**Diagnosis**:
```bash
# Check logs
docker compose logs orchestrator

# Common causes:
# - Missing environment variables
# - Database not ready
# - Permission manager not ready
# - Configuration errors
```

**Solutions**:
- Verify `.env` file exists and has required values
- Check database health: `docker compose exec db pg_isready -U ctf`
- Check permission manager: `curl http://permission-manager:8080/health`
- Verify config files in `configs/` directory

### 2. Agent Containers Fail to Start

**Symptoms**: Agent containers exit or stay in Created state

**Diagnosis**:
```bash
# Check specific agent logs
docker compose logs agent-web

# Check resource constraints
docker compose ps
docker stats
```

**Solutions**:
- Increase memory/CPU limits in `docker-compose.yml`
- Verify base image built successfully: `docker images | grep agent-base`
- Check for missing dependencies in Dockerfile
- Verify network connectivity

### 3. Permission Manager Errors

**Symptoms**: Agents can't install packages, mount volumes, etc.

**Diagnosis**:
```bash
# Check permission manager logs
docker compose logs permission-manager

# Check audit logs
curl http://localhost:8080/permissions/audit/log
```

**Solutions**:
- Verify permission manager has Docker socket access
- Check capability configuration in `configs/permissions.yaml`
- Ensure agent ID matches allowed agents list
- Check request parameters match schema

### 4. LLM Connection Failures

**Symptoms**: Agents timeout, return errors, or produce no output

**Diagnosis**:
```bash
# Test Nemotron API
curl -H "Authorization: Bearer $NEMOTRON_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"nemotron-3-5-lightning-free","messages":[{"role":"user","content":"Hello"}]}' \
  https://integrate.api.nvidia.com/v1/chat/completions

# Test Ollama
curl http://localhost:11434/api/tags
```

**Solutions**:
- Verify API key is correct and has quota
- Check network connectivity from orchestrator container
- Try different provider: `LLM_PROVIDER=ollama`
- Increase timeout in `configs/system.yaml`

### 5. Tool Execution Failures

**Symptoms**: Tools return errors, timeout, or permission denied

**Diagnosis**:
```bash
# Test tool in agent container
docker compose run --rm agent-web which nmap
docker compose run --rm agent-web nmap --version

# Check execution engine logs
docker compose logs orchestrator | grep -i "tool\|command"
```

**Solutions**:
- Verify tool installed in agent image
- Check tool allowlist in agent config
- Increase timeout for slow tools
- Verify network access for network tools

### 6. Memory/Resource Exhaustion

**Symptoms**: OOM kills, slow performance, agent timeouts

**Diagnosis**:
```bash
# Check resource usage
docker stats

# Check container limits
docker inspect ctf_agent_web | grep -A 10 "Resources"
```

**Solutions**:
- Increase memory limits in `docker-compose.yml`
- Reduce `max_active_agents` in `configs/system.yaml`
- Adjust `default_memory_limit` per agent profile
- Enable swap if needed

### 7. Network Connectivity Issues

**Symptoms**: Agents can't reach targets, DNS failures

**Diagnosis**:
```bash
# Test network from agent
docker compose run --rm agent-web ping -c 3 10.102.0.5
docker compose run --rm agent-web nslookup target

# Check network configuration
docker network ls
docker network inspect ctf_targets
```

**Solutions**:
- Verify agent on correct networks
- Check target services are running
- Check firewall/iptables rules
- Verify DNS configuration

### 8. Artifact/Database Issues

**Symptoms**: Artifacts not found, database errors, index corruption

**Diagnosis**:
```bash
# Check artifact storage
ls -la artifacts/

# Check database
docker compose exec db psql -U ctf -d ctf -c "\dt"

# Check Redis
docker compose exec redis redis-cli ping
```

**Solutions**:
- Rebuild artifact index: delete `artifacts/index.json`
- Restart artifact manager
- Check disk space
- Verify PostgreSQL/Redis health

## Debugging Techniques

### 1. Interactive Debugging

```bash
# Shell into running container
docker compose exec orchestrator bash
docker compose exec agent-web bash

# Run commands manually
docker compose run --rm agent-web nmap -sS 10.102.0.5
docker compose run --rm agent-crypto python3 -c "import hashlib; print(hashlib.sha256(b'test').hexdigest())"
```

### 2. Log Analysis

```bash
# Follow logs in real-time
docker compose logs -f orchestrator

# Filter logs
docker compose logs orchestrator 2>&1 | grep -i error
docker compose logs orchestrator 2>&1 | grep -i "agent-web"

# Structured log parsing
docker compose logs orchestrator | jq '. | select(.level=="error")'
```

### 3. Database Inspection

```bash
# Query challenges
docker compose exec db psql -U ctf -d ctf -c "SELECT * FROM challenges;"

# Query agents
docker compose exec db psql -U ctf -d ctf -c "SELECT * FROM agents;"

# Query findings
docker compose exec db psql -U ctf -d ctf -c "SELECT * FROM findings;"
```

### 4. Manual API Testing

```bash
# Create challenge
curl -X POST http://localhost:8000/challenges \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "description": "Test challenge"}'

# List challenges
curl http://localhost:8000/challenges

# Solve challenge
curl -X POST http://localhost:8000/challenges/<id>/solve

# Get report
curl http://localhost:8000/challenges/<id>/report
```

### 5. Permission Manager Debugging

```bash
# Test permission request
curl -X POST http://localhost:8080/permissions/request \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "orchestrator",
    "capability": "INSTALL_PACKAGE",
    "reason": "Test install",
    "parameters": {"package_name": "curl", "package_manager": "apt"},
    "risk": "medium"
  }'

# Check audit log
curl http://localhost:8080/permissions/audit/log
```

## Performance Debugging

### 1. Profiling Agent Execution

```python
# Add to agent code for profiling
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# ... agent execution ...

profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(20)
```

### 2. LLM Token Usage

```bash
# Monitor token usage in logs
docker compose logs orchestrator | grep -i "token"

# Check LLM provider metrics
# (if provider supports it)
```

### 3. Database Query Performance

```bash
# Enable query logging
docker compose exec db psql -U ctf -d ctf -c "SET log_statement = 'all';"

# Analyze slow queries
docker compose exec db psql -U ctf -d ctf -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

## Advanced Debugging

### 1. Container Inspection

```bash
# Inspect container configuration
docker inspect ctf_agent_web

# Check processes
docker top ctf_agent_web

# Check mounts
docker inspect ctf_agent_web | jq '.[0].Mounts'
```

### 2. Network Debugging

```bash
# Capture traffic
docker compose exec agent-web tcpdump -i any -w capture.pcap

# Analyze with tshark
tshark -r capture.pcap
```

### 3. Memory Analysis

```bash
# Get memory dump
docker compose exec agent-web gcore <pid>

# Analyze with volatility
python3 -m volatility3 -f core.<pid> linux.pslist
```

## Getting Help

### Log Collection for Support

```bash
# Collect all logs
mkdir -p debug-logs
docker compose logs --no-color > debug-logs/all.log 2>&1
docker compose logs orchestrator --no-color > debug-logs/orchestrator.log 2>&1
docker compose logs permission-manager --no-color > debug-logs/perm.log 2>&1

# Collect configs
cp -r configs debug-logs/
cp .env debug-logs/.env.redacted  # Remove secrets!

# Collect system info
docker version > debug-logs/docker-version.txt
docker compose version > debug-logs/compose-version.txt
docker system df > debug-logs/docker-df.txt
```

### Reporting Issues

Include:
1. Error messages and logs
2. Steps to reproduce
3. Environment details (OS, Docker version, hardware)
4. Configuration files (redacted)
5. Expected vs actual behavior