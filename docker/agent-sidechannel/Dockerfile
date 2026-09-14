# Side-channel agent image
FROM ctf/agent-base:latest AS sidechannel

USER root

# Install side-channel tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    linux-tools-common \
    linux-tools-generic \
    linux-cloud-tools-generic \
    perf \
    gdb \
    python3-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ChipWhisperer
RUN pip3 install --no-cache-dir --break-system-packages \
    chipwhisperer \
    chipwhisperer-analyzer \
    chipwhisperer-common \
    chipwhisperer-hardware \
    chipwhisperer-software

# Install fault injection tools
RUN pip3 install --no-cache-dir --break-system-packages \
    faultinject \
    lascar \
    sca

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    numpy \
    scipy \
    pandas \
    matplotlib \
    statsmodels \
    scikit-learn

USER ctf
WORKDIR /workspace

CMD ["bash"]