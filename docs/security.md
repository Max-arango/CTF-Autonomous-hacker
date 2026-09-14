# Autonomous CTF Environment - Security Model

## Security Principles

1. **Least Privilege**: Every component runs with minimum required permissions
2. **Default Deny**: All access denied unless explicitly allowed
3. **Defense in Depth**: Multiple layers of security controls
4. **Audit Everything**: All security-relevant operations logged immutably
5. **Verify, Don't Trust**: Independent verification of all claims

## Component Security

### Orchestrator (Non-Root)
- Runs as `ctf:ctf` (UID 1000)
- Read-only root filesystem
- Networks: control, workspace, targets
- No Docker socket access
- Capabilities: ALL dropped

### Agent Containers (Non-Root)
- Runs as `ctf:ctf` (UID 1000)
- Read-only root filesystem
- Networks: Per-agent profile
- No Docker socket access
- Capabilities: ALL dropped (except specific needs like NET_RAW for network agent)
- Resource limits: CPU, memory, PIDs, file descriptors

### Permission Manager (Root - Only Privileged Component)
- Runs as root
- Networks: control only
- Docker socket access (read-only)
- Capabilities: SYS_ADMIN, DAC_OVERRIDE, SYS_RESOURCE
- Seccomp: unconfined (for privileged operations)
- All operations capability-gated

### Database & Redis
- Network: control only
- No external exposure
- Authentication required

## Network Security

### Network Segmentation

| Network | Subnet | Purpose | Access |
|---------|--------|---------|--------|
| ctf_control | 10.100.0.0/24 | Internal control plane | Orchestrator, Permission Manager |
| ctf_workspace | 10.101.0.0/24 | Shared workspace | All agents (read/write) |
| ctf_targets | 10.102.0.0/24 | CTF infrastructure | Web, Pwn, Network, AD, Cloud, Orchestrator |
| ctf_malware | 10.103.0.0/24 | Malware analysis | Malware, Forensics (no internet) |
| ctf_attack_defense | 10.104.0.0/24 | Attack/Defense | AD, Orchestrator |

### Network Policies

- Default deny between networks
- Explicit allow rules per agent role
- Malware network: no internet, no external access
- Targets network: internal only, no host access

## Filesystem Security

### Mount Policies

| Path | Read | Write | Agents |
|------|------|-------|--------|
| /workspace | All | All | All |
| /artifacts | All | All | All |
| /logs | Orchestrator, Meta, PermMgr | All | All |
| /challenge | All | None | All |
| /tmp | All | All | All |

### Artifact Integrity

- SHA-256 content addressing
- Immutable once stored
- Hash verification on retrieval
- Deduplication by content hash

## Capability System

### Defined Capabilities

| Capability | Risk | Allowed Agents | Approval Required |
|------------|------|----------------|-------------------|
| INSTALL_PACKAGE | Medium | Orchestrator, Programming | Yes |
| CREATE_RESTRICTED_MOUNT | High | Orchestrator | Yes |
| CONFIGURE_ISOLATED_NETWORK | High | Orchestrator | Yes |
| SET_REQUIRED_DEVICE_PERMISSION | High | Orchestrator | Yes |
| PERFORM_CONTROLLED_PRIVILEGED_OPERATION | Critical | Orchestrator | Yes |
| MANAGE_CONTAINER_LIFECYCLE | High | Orchestrator | No |
| READ_AUDIT_LOGS | Low | Orchestrator, Meta | No |

### Capability Enforcement

1. Agent requests capability via Permission Client
2. Permission Manager validates:
   - Agent identity (authenticated via network)
   - Capability allowed for agent role
   - Parameters match schema
   - Risk level assessed
3. If approved: execute minimal privileged action
4. Always: audit log entry created

### Blocked Operations

The following are EXPLICITLY NOT ALLOWED:
- Arbitrary root command execution
- Host Docker socket access (except Permission Manager read-only)
- Unrestricted host filesystem mounts
- Package installation of: docker, podman, containerd, kubernetes
- Direct syscall access
- Kernel module loading

## Container Hardening

### Base Image (agent-base)
```dockerfile
USER ctf:ctf
read_only: true
cap_drop: ["ALL"]
security_opt: ["no-new-privileges:true"]
pids_limit: 100
cpus: "1.0"
memory: "2g"
ulimits: 
  nofile: 1024
  nproc: 50
tmpfs:
  - /tmp:rw,noexec,nosuid,size=1g
  - /run:rw,noexec,nosuid,size=100m
```

### Specialized Agents
Additional capabilities only where required:
- **network, web, pwn**: NET_RAW, NET_ADMIN
- **pwn, reverse, malware, firmware**: SYS_PTRACE
- **mobile, firmware, sidechannel**: SYS_ADMIN, /dev/kvm
- **sidechannel**: PERF_EVENTS

## Evidence & Verification

### Verification Requirements

All agent claims must pass through Evidence Engine:
1. **Observation**: Artifact or command output evidence
2. **Hypothesis**: Experimental verification required
3. **Evidence**: Artifact existence + integrity
4. **Exploit**: Demonstrable exploitation + artifacts
5. **Proof**: Flag format + source attribution + reproducibility

### Verification Statuses

- **UNVERIFIED**: No evidence or insufficient evidence
- **PARTIALLY_VERIFIED**: Some evidence supports claim
- **VERIFIED**: Sufficient evidence, reproducible
- **DISPROVEN**: Evidence contradicts claim

## Audit Logging

### Immutable Audit Log

Location: `/logs/audit.log` (append-only, root-owned)

Logged Events:
- Agent spawn/termination
- Tool execution (command, args, result)
- Permission requests (granted/denied)
- Artifact create/read/delete
- Evidence verification results
- Flag capture attempts
- Network connections (targeted)

### Log Format (JSON)

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "agent_id": "agent-web-123",
  "action": "execute_tool",
  "target": "nmap",
  "parameters": {"target": "10.102.0.5", "ports": "80,443"},
  "result": "success",
  "risk_level": "medium",
  "artifacts": ["artifact-456"]
}
```

## Incident Response

### Compromise Indicators

1. Unexpected root processes in agent containers
2. Network connections to unauthorized destinations
3. Audit log gaps or tampering
4. Artifact hash mismatches
5. Permission request anomalies

### Response Procedures

1. **Isolate**: Stop affected containers, disconnect networks
2. **Preserve**: Snapshot containers, export logs/artifacts
3. **Analyze**: Review audit logs, container diffs, network captures
4. **Remediate**: Rebuild containers, rotate credentials, update policies
5. **Verify**: Re-run security tests, validate fixes

## Compliance

### Standards Alignment

- **NIST 800-53**: AC-3, AC-6, AU-2, AU-6, SC-7, SI-3
- **CIS Docker Benchmark**: Container hardening
- **OWASP**: Input validation, output encoding, logging

### Certification Considerations

- No persistent secrets in images
- All credentials via environment/runtime
- Regular base image updates
- Vulnerability scanning in CI/CD