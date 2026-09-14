# Web3 agent image
FROM ctf/agent-base:latest AS web3

USER root

# Install Web3 tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go \
    nodejs \
    npm \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Foundry
RUN curl -L https://foundry.paradigm.xyz | bash && \
    /root/.foundry/bin/foundryup

# Add foundry to PATH
ENV PATH="/root/.foundry/bin:${PATH}"

# Install solc
RUN wget -q https://github.com/ethereum/solidity/releases/download/v0.8.26/solc-static-linux -O /usr/local/bin/solc && \
    chmod +x /usr/local/bin/solc

# Install slither
RUN pip3 install --no-cache-dir --break-system-packages slither-analyzer

# Install mythril
RUN pip3 install --no-cache-dir --break-system-packages mythril

# Install echidna
RUN wget -q https://github.com/crytic/echidna/releases/download/v2.2.0/echidna-2.2.0-linux.tar.gz -O /tmp/echidna.tar.gz && \
    tar -xzf /tmp/echidna.tar.gz -C /tmp && \
    mv /tmp/echidna /opt/echidna && \
    rm /tmp/echidna.tar.gz && \
    ln -s /opt/echidna/echidna /usr/local/bin/echidna

# Install crytic
RUN pip3 install --no-cache-dir --break-system-packages crytic

# Install hardhat
RUN npm install -g hardhat

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    web3 \
    eth-abi \
    eth-utils \
    eth-typing \
    eth-account \
    eth-hash \
    eth-keys \
    eth-rlp \
    rlp \
    vyper \
    brownie

USER ctf
WORKDIR /workspace

CMD ["bash"]