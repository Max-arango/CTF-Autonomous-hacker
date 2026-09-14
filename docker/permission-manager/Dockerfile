# Permission Manager image - runs as root for privileged operations
FROM ubuntu:24.04 AS permission-manager

# Build arguments
ARG UID=1000
ARG GID=1000

# Install base packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    python3 \
    python3-pip \
    python3-venv \
    docker.io \
    docker-compose \
    iptables \
    iproute2 \
    util-linux \
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
    docker \
    psutil \
    cryptography \
    aiofiles \
    python-multipart

# Create user
RUN groupadd -g ${GID} ctf && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ctf

# Copy source code
COPY src/permissions/ /app/src/permissions/
COPY configs/permissions.yaml /app/configs/permissions.yaml

# Create directories
RUN mkdir -p /workspace /artifacts /logs && \
    chown -R ctf:ctf /workspace /artifacts /logs

# Permission manager runs as root for privileged operations
USER root
WORKDIR /app

EXPOSE 8080

CMD ["python", "-m", "src.permissions.main"]