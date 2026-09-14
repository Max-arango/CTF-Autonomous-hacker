# Secure Permission Manager image - runs as non-root with minimal privileges
FROM ubuntu:24.04 AS permission-manager

# Build arguments
ARG UID=1000
ARG GID=1000

# Install base packages (NO docker.io, NO docker-compose)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    python3 \
    python3-pip \
    python3-venv \
    iptables \
    iproute2 \
    util-linux \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    fastapi \
    uvicorn[standard] \
    pydantic \
    pydantic-settings \
    httpx \
    structlog \
    rich \
    typer \
    python-dotenv \
    PyYAML \
    psutil \
    cryptography \
    aiofiles \
    python-multipart \
    cryptography

# Create non-root user
RUN groupadd -g ${GID} ctf && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ctf

# Copy source code
COPY src/permissions/ /app/src/permissions/
COPY src/security/ /app/src/security/
COPY configs/permissions.yaml /app/configs/permissions.yaml

# Create directories
RUN mkdir -p /workspace /artifacts /logs && \
    chown -R ctf:ctf /workspace /artifacts /logs

# Permission manager runs as non-root (capabilities granted via capabilities.yaml)
USER ctf
WORKDIR /app

EXPOSE 8080

CMD ["python", "-m", "src.permissions.main"]