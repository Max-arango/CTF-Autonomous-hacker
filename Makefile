.PHONY: build up down logs test lint typecheck clean

# Build all Docker images
build:
	docker compose build --parallel

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# View logs
logs:
	docker compose logs -f

# Run tests
test:
	docker compose run --rm orchestrator pytest tests/ -v

# Run unit tests only
test-unit:
	docker compose run --rm orchestrator pytest tests/unit/ -v

# Run integration tests only
test-integration:
	docker compose run --rm orchestrator pytest tests/integration/ -v

# Run security tests
test-security:
	docker compose run --rm orchestrator pytest tests/security/ -v

# Lint code
lint:
	docker compose run --rm orchestrator ruff check src/ tests/

# Format code
fmt:
	docker compose run --rm orchestrator ruff format src/ tests/

# Type check
typecheck:
	docker compose run --rm orchestrator mypy src/

# Clean up
clean:
	docker compose down -v
	docker system prune -f

# Install development dependencies
install-dev:
	pip install -e ".[dev]"

# Generate requirements
requirements:
	pip compile pyproject.toml -o requirements.txt

# Build CLI
build-cli:
	docker compose run --rm orchestrator pip install -e .

# Run a toy challenge
toy:
	docker compose run --rm orchestrator python -m src.cli solve examples/challenges/web_basic

# Show status
status:
	docker compose ps

# Tail orchestrator logs
logs-orchestrator:
	docker compose logs -f orchestrator

# Tail permission manager logs
logs-perm:
	docker compose logs -f permission-manager

# Shell into orchestrator
shell:
	docker compose exec orchestrator bash

# Rebuild single service
rebuild-%:
	docker compose build $* && docker compose up -d $*