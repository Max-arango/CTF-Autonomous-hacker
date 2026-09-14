#!/bin/bash
# Autonomous CTF Environment - Setup Script

set -e

echo "=========================================="
echo "Autonomous CTF Environment Setup"
echo "=========================================="

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "ERROR: Docker Compose not found. Please install Docker Compose v2."
    exit 1
fi

DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "Docker version: $DOCKER_VERSION"

COMPOSE_VERSION=$(docker compose version --short)
echo "Docker Compose version: $COMPOSE_VERSION"

# Check Docker daemon
if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon not running. Please start Docker."
    exit 1
fi

echo "Prerequisites OK!"

# Create directory structure
echo "Creating directories..."
mkdir -p workspace artifacts logs examples/challenges
mkdir -p configs skills/ctf-orchestrator skills/ctf-web skills/ctf-crypto skills/ctf-pwn skills/ctf-re skills/ctf-forensics
mkdir -p src/orchestrator src/agents src/runtime src/llm src/memory src/execution src/permissions src/artifacts src/evidence src/challenges src/attack_defense src/reporting src/observability src/security
mkdir -p tools/registry tools/wrappers tools/installers
mkdir -p tests/unit tests/integration tests/security tests/agents tests/tools tests/docker
mkdir -p docs

# Check for .env
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Edit .env and add your NEMOTRON_API_KEY"
    echo "Get your API key from: https://build.nvidia.com/nvidia/nemotron-3-5-lightning-free"
    echo ""
fi

# Check for API key
if grep -q "your-nemotron-api-key" .env 2>/dev/null; then
    echo "WARNING: NEMOTRON_API_KEY not set in .env"
    echo "The system will not work without a valid API key."
    echo ""
fi

# Build images
echo ""
echo "Building Docker images..."
echo "This may take 10-30 minutes on first run..."
echo ""

make build

# Start services
echo ""
echo "Starting services..."
make up

# Wait for health checks
echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "Checking service health..."

if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✓ Orchestrator: Healthy"
else
    echo "✗ Orchestrator: Not healthy (check logs with 'make logs-orchestrator')"
fi

if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo "✓ Permission Manager: Healthy"
else
    echo "✗ Permission Manager: Not healthy (check logs with 'make logs-perm')"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your NEMOTRON_API_KEY if not done"
echo "2. Add a challenge: ctf challenge add ./examples/challenges/web_basic"
echo "3. Solve it: ctf solve <challenge-id>"
echo "4. View report: ctf report <challenge-id>"
echo ""
echo "Useful commands:"
echo "  make logs          - View all logs"
echo "  make logs-orchestrator - View orchestrator logs"
echo "  make status        - Check service status"
echo "  make test          - Run tests"
echo "  make shell         - Shell into orchestrator"
echo ""
echo "Documentation: docs/"
echo ""