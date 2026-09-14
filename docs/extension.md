# Autonomous CTF Environment - Extension Guide

## Overview

This guide covers extending the Autonomous CTF Environment with new agents, tools, LLM providers, and capabilities.

## Adding a New Specialist Agent

### 1. Create Agent Dockerfile

```dockerfile
# docker/agent-mycustom/Dockerfile
FROM ctf/agent-base:latest AS mycustom

USER root

# Install custom tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    mycustom-tool \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    mycustom-lib

USER ctf
WORKDIR /workspace
CMD ["bash"]
```

### 2. Create System Prompt

```markdown
# skills/ctf-mycustom/system_prompt.md

# MyCustom Specialist System Prompt

You are a **MyCustom Specialist** in an autonomous CTF environment.

## Core Capabilities
- Capability 1
- Capability 2
- Capability 3

## Methodology
### 1. Phase 1
Details...

## Tool Preferences
| Task | Tools |
|------|-------|
| Task 1 | tool1, tool2 |

## Evidence Requirements
- Requirement 1
- Requirement 2

## Output Format
```json
{
  "type": "observation|hypothesis|evidence|exploit|proof",
  "title": "Finding title",
  "content": "Details",
  "confidence": 0.0-1.0,
  ...
}
```
```

### 3. Register Agent Configuration

```yaml
# configs/agents.yaml
mycustom:
  enabled: true
  model: "nemotron-3-5-lightning-free"
  temperature: 0.3
  max_tokens: 8192
  system_prompt_file: "skills/ctf-mycustom/system_prompt.md"
  capabilities:
    - "capability_1"
    - "capability_2"
  tools:
    - "mycustom-tool"
    - "python"
  resource_limits:
    max_tokens: 50000
    max_time_seconds: 300
    max_sub_agents: 4
```

### 4. Add to Docker Compose

```yaml
# docker-compose.yml
agent-mycustom:
  build:
    context: .
    dockerfile: docker/agent-mycustom/Dockerfile
  container_name: ctf_agent_mycustom
  environment:
    - PYTHONUNBUFFERED=1
    - AGENT_TYPE=mycustom
    - ORCHESTRATOR_URL=http://orchestrator:8000
    - PERMISSION_MANAGER_URL=http://permission-manager:8080
    - WORKSPACE_PATH=/workspace
    - ARTIFACTS_PATH=/artifacts
    - LOGS_PATH=/logs
  volumes:
    - workspace:/workspace:rw
    - artifacts:/artifacts:rw
    - logs:/logs:rw
  networks:
    - ctf_control
    - ctf_workspace
    # Add ctf_targets if needed
  depends_on:
    orchestrator:
      condition: service_healthy
  deploy:
    resources:
      limits:
        cpus: "2.0"
        memory: "4g"
  profiles:
    - agents
```

### 5. Add Networks (if needed)

```yaml
# In agent profile
networks:
  - ctf_control
  - ctf_workspace
  - ctf_targets  # If needs target access
  - ctf_malware  # If malware analysis
```

### 6. Build and Test

```bash
# Build
docker compose build agent-mycustom

# Test
docker compose run --rm agent-mycustom bash -c "mycustom-tool --version"
```

## Adding a New Tool

### 1. Define Tool in Registry

```yaml
# configs/tools.yaml
tools:
  mycategory:
    - name: "mytool"
      category: "mycategory"
      binary: "mytool"
      version_check: "mytool --version"
      requires_root: false
      network_required: false
      container_profile: "base"
      security_risk: "low"
      supported_agents: ["mycustom", "programming"]
```

### 2. Create Tool Wrapper

```python
# src/execution/wrappers.py
class MyToolWrapper(ToolWrapperBase):
    """Wrapper for mytool."""
    
    async def execute(self, arguments: Dict[str, Any], agent_id: str) -> ToolResult:
        # Validate arguments
        if not self.validate_arguments(arguments):
            return ToolResult(
                tool_name=self.tool_name,
                success=False,
                error="Invalid arguments",
            )
        
        # Build command
        arg1 = arguments.get("arg1", "")
        arg2 = arguments.get("arg2", "")
        
        command = f"mytool --arg1 {shlex.quote(arg1)} --arg2 {shlex.quote(arg2)}"
        
        return await self.execution_engine.execute_command(
            command=command,
            agent_id=agent_id,
            timeout=arguments.get("timeout", 60),
        )
```

### 3. Register Wrapper

```python
# In ExecutionEngine._register_builtin_wrappers()
self.registry.register_wrapper("mytool", MyToolWrapper("mytool", self))
```

### 4. Add to Agent's Allowed Tools

```yaml
# configs/agents.yaml
mycustom:
  tools:
    - "mytool"
    - "python"
```

## Adding a New LLM Provider

### 1. Implement Provider Interface

```python
# src/llm/myprovider.py
from .base import LLMProvider, LLMMessage, LLMResponse, LLMConfig, MessageRole
from typing import List, Optional, Dict, Any, AsyncIterator


class MyProvider(LLMProvider):
    """MyProvider LLM provider."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = os.getenv("MYPROVIDER_API_KEY")
        self.base_url = os.getenv("MYPROVIDER_BASE_URL", "https://api.myprovider.com/v1")
    
    async def initialize(self) -> None:
        # Initialize client
        pass
    
    async def close(self) -> None:
        # Close client
        pass
    
    async def complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        # Implement completion
        pass
    
    async def stream_complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[LLMResponse]:
        # Implement streaming
        pass
    
    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        # Implement token counting
        pass
    
    def get_model_name(self) -> str:
        return self.config.model
    
    def get_provider_name(self) -> str:
        return "myprovider"
```

### 2. Register Provider

```python
# src/llm/factory.py
from .myprovider import MyProvider

LLMProviderFactory._providers["myprovider"] = MyProvider
```

### 3. Configure Environment

```bash
# .env
LLM_PROVIDER=myprovider
MYPROVIDER_API_KEY=your-key
MYPROVIDER_BASE_URL=https://api.myprovider.com/v1
MYPROVIDER_MODEL=my-model-name
```

### 4. Update Settings

```python
# src/config/settings.py
class LLMSettings(BaseSettings):
    # ...
    myprovider_api_key: Optional[str] = None
    myprovider_base_url: str = "https://api.myprovider.com/v1"
    myprovider_model: str = "my-model"
```

## Adding a New Challenge Type

### 1. Define Challenge Model

```python
# src/orchestrator/models.py
class ChallengeType(str, Enum):
    JEOPARDY = "jeopardy"
    MACHINE = "machine"
    ATTACK_DEFENSE = "attack_defense"
    MY_CUSTOM_TYPE = "my_custom_type"
```

### 2. Implement Challenge Handler

```python
# src/challenges/handlers/mycustom.py
class MyCustomChallengeHandler:
    """Handler for custom challenge type."""
    
    async def setup(self, challenge: Challenge) -> Dict[str, Any]:
        """Set up challenge environment."""
        pass
    
    async def validate(self, challenge: Challenge, flag: str) -> bool:
        """Validate flag for this challenge type."""
        pass
    
    async def cleanup(self, challenge: Challenge):
        """Clean up challenge resources."""
        pass
```

### 3. Register in Orchestrator

```python
# src/orchestrator/orchestrator.py
from .challenges.handlers.mycustom import MyCustomChallengeHandler

class Orchestrator:
    def __init__(self):
        # ...
        self.challenge_handlers = {
            ChallengeType.JEOPARDY: JeopardyHandler(),
            ChallengeType.MACHINE: MachineHandler(),
            ChallengeType.ATTACK_DEFENSE: AttackDefenseHandler(),
            ChallengeType.MY_CUSTOM_TYPE: MyCustomChallengeHandler(),
        }
```

## Adding Custom Memory Layers

### 1. Define Layer

```python
# src/memory/models.py
class MemoryLayer(str, Enum):
    SHORT_TERM = "short_term"
    TASK = "task"
    LONG_TERM = "long_term"
    TEAM = "team"  # Shared across team members
    ORGANIZATION = "organization"  # Organization-wide knowledge
```

### 2. Extend Memory Manager

```python
# src/memory/manager.py
class MemoryManager:
    def __init__(self):
        # ...
        self._team_memory: Dict[str, MemoryEntry] = {}
        self._org_memory: Dict[str, MemoryEntry] = {}
    
    async def store(self, entry: MemoryEntry) -> str:
        # Handle new layers
        if entry.layer == MemoryLayer.TEAM:
            store = self._team_memory
        elif entry.layer == MemoryLayer.ORGANIZATION:
            store = self._org_memory
        # ...
```

## Adding Custom Artifact Types

### 1. Extend Metadata

```python
# src/artifacts/models.py
@dataclass
class ArtifactMetadata:
    # ...
    custom_type: str = ""  # Custom type identifier
    analysis_results: Dict[str, Any] = field(default_factory=dict)
```

### 2. Add Specialized Storage

```python
# src/artifacts/specialized.py
class BinaryArtifact(Artifact):
    """Specialized artifact for binary files."""
    
    @property
    def architecture(self) -> str:
        return self.metadata.custom.get("architecture", "")
    
    @property
    def protections(self) -> Dict[str, bool]:
        return self.metadata.custom.get("protections", {})
```

## Testing Extensions

### 1. Unit Tests

```python
# tests/unit/test_mycustom.py
import pytest
from src.runtime.agent import AgentConfig
from src.execution.wrappers import MyToolWrapper


@pytest.mark.asyncio
async def test_mycustom_agent_creation():
    config = AgentConfig(role="mycustom", name="Test", objective="Test")
    # Test agent creation and execution
```

### 2. Integration Tests

```python
# tests/integration/test_mycustom.py
@pytest.mark.asyncio
async def test_mycustom_challenge_solving():
    # Test full challenge solving with new agent
```

## Best Practices

1. **Follow Security Model**: New agents inherit base security, only add capabilities when necessary
2. **Document Thoroughly**: System prompts should be comprehensive
3. **Test Isolation**: Verify new agents work in isolated networks
4. **Resource Limits**: Set appropriate CPU/memory limits
5. **Evidence Requirements**: Define clear evidence standards for new finding types
6. **Error Handling**: Implement graceful degradation
7. **Logging**: Use structured logging for all operations

## Example: Complete Agent Addition

See `skills/ctf-web/` and `docker/agent-web/` for a complete example of a specialist agent implementation.