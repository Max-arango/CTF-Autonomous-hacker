# Programming agent image
FROM ctf/agent-base:latest AS programming

USER root

# Install programming languages and tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    clang \
    llvm \
    make \
    cmake \
    rustc \
    cargo \
    golang-go \
    nodejs \
    npm \
    python3-dev \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    black \
    isort \
    flake8 \
    mypy \
    pytest \
    pytest-asyncio \
    pytest-cov \
    hypothesis \
    requests \
    httpx \
    aiohttp \
    fastapi \
    uvicorn \
    pydantic \
    sqlalchemy \
    redis \
    docker

# Install Rust tools
RUN cargo install cargo-audit cargo-outdated cargo-tree

# Install Go tools
RUN go install golang.org/x/vuln/cmd/govulncheck@latest
RUN go install golang.org/x/tools/cmd/goimports@latest

# Install Node tools
RUN npm install -g eslint prettier typescript ts-node

USER ctf
WORKDIR /workspace

CMD ["bash"]