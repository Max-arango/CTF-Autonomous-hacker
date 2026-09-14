# Crypto agent image
FROM ctf/agent-base:latest AS crypto

USER root

# Install crypto tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libgmp-dev \
    libmpfr-dev \
    libmpc-dev \
    python3-dev \
    sage \
    && rm -rf /var/lib/apt/lists/*

# Install hashcat
RUN apt-get update && apt-get install -y --no-install-recommends \
    hashcat \
    && rm -rf /var/lib/apt/lists/*

# Install john
RUN apt-get update && apt-get install -y --no-install-recommends \
    john \
    && rm -rf /var/lib/apt/lists/*

# Install Python crypto packages
RUN pip3 install --no-cache-dir --break-system-packages \
    sympy \
    gmpy2 \
    pycryptodome \
    cryptography \
    z3-solver \
    rsa \
    ecdsa \
    fastecdsa \
    tinyec \
    factordb-python \
    requests

# Install rsatool
RUN pip3 install --no-cache-dir --break-system-packages rsatool

USER ctf
WORKDIR /workspace

CMD ["bash"]