# Orchestrator image
FROM ctf/agent-base:latest AS orchestrator

USER root

# Install orchestrator-specific packages
RUN pip3 install --no-cache-dir --break-system-packages \
    fastapi \
    uvicorn[standard] \
    sqlalchemy \
    alembic \
    asyncpg \
    redis \
    pydantic \
    pydantic-settings \
    httpx \
    openai \
    tenacity \
    structlog \
    rich \
    typer \
    python-dotenv \
    PyYAML \
    docker \
    psutil \
    cryptography \
    aiofiles \
    python-multipart \
    prometheus-client \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp

# Copy source code
COPY src/ /app/src/
COPY configs/ /app/configs/
COPY skills/ /app/skills/

# Install the package
RUN pip3 install --no-cache-dir --break-system-packages -e /app

# Create directories
RUN mkdir -p /workspace /artifacts /logs /challenge && \
    chown -R ctf:ctf /workspace /artifacts /logs /challenge

USER ctf
WORKDIR /app

EXPOSE 8000

CMD ["python", "-m", "src.orchestrator.main"]