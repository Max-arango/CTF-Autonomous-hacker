# Base agent image - minimal, secure, non-root
FROM ubuntu:24.04 AS base

# Build arguments
ARG UID=1000
ARG GID=1000
ARG PYTHON_VERSION=3.12

# Install base system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    gnupg \
    lsb-release \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install base tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    jq \
    yq \
    ripgrep \
    fd-find \
    file \
    binutils \
    xxd \
    tar \
    unzip \
    p7zip-full \
    openssl \
    ssh \
    rsync \
    tmux \
    zsh \
    bash \
    vim \
    less \
    tree \
    htop \
    net-tools \
    iproute2 \
    dnsutils \
    whois \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g ${GID} ctf && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ctf && \
    echo "ctf ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ctf && \
    chmod 440 /etc/sudoers.d/ctf

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
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
    asyncpg \
    redis \
    psutil \
    cryptography \
    aiofiles

# Create workspace directories
RUN mkdir -p /workspace /artifacts /logs /challenge /tmp/ctf && \
    chown -R ctf:ctf /workspace /artifacts /logs /challenge /tmp/ctf

# Set up environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/ctf/.local/bin:${PATH}" \
    HOME="/home/ctf"

# Switch to non-root user
USER ctf
WORKDIR /workspace

# Default command
CMD ["bash"]