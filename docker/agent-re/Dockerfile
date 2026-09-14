# Reverse engineering agent image
FROM ctf/agent-base:latest AS reverse

USER root

# Install reverse engineering tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdb \
    lldb \
    build-essential \
    cmake \
    python3-dev \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install radare2
RUN apt-get update && apt-get install -y --no-install-recommends \
    radare2 \
    && rm -rf /var/lib/apt/lists/*

# Install Cutter
RUN apt-get update && apt-get install -y --no-install-recommends \
    qtbase5-dev \
    qttools5-dev \
    qttools5-dev-tools \
    && git clone https://github.com/rizinorg/cutter /opt/cutter && \
    cd /opt/cutter && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release && \
    make -j$(nproc) && \
    make install && \
    rm -rf /var/lib/apt/lists/*

# Install Ghidra
RUN wget -q https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_11.1.2_build/ghidra_11.1.2_PUBLIC_20240709.zip -O /tmp/ghidra.zip && \
    unzip -q /tmp/ghidra.zip -d /opt/ && \
    mv /opt/ghidra_* /opt/ghidra && \
    rm /tmp/ghidra.zip && \
    ln -s /opt/ghidra/ghidraRun /usr/local/bin/ghidra

# Install angr
RUN pip3 install --no-cache-dir --break-system-packages angr

# Install z3
RUN pip3 install --no-cache-dir --break-system-packages z3-solver

# Install additional Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    unicorn \
    keystone-engine \
    capstone \
    pwntools \
    claripy \
    cle

USER ctf
WORKDIR /workspace

CMD ["bash"]