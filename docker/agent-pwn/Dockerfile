# Pwn agent image
FROM ctf/agent-base:latest AS pwn

USER root

# Install pwn tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdb \
    gdbserver \
    build-essential \
    cmake \
    libssl-dev \
    libffi-dev \
    python3-dev \
    qemu-user \
    qemu-user-static \
    binutils \
    strace \
    ltrace \
    patchelf \
    && rm -rf /var/lib/apt/lists/*

# Install pwndbg
RUN git clone https://github.com/pwndbg/pwndbg /opt/pwndbg && \
    cd /opt/pwndbg && \
    ./setup.sh

# Install pwntools
RUN pip3 install --no-cache-dir --break-system-packages pwntools

# Install checksec
RUN pip3 install --no-cache-dir --break-system-packages checksec

# Install ROPgadget
RUN pip3 install --no-cache-dir --break-system-packages ROPgadget

# Install ropper
RUN pip3 install --no-cache-dir --break-system-packages ropper

# Install one_gadget
RUN apt-get update && apt-get install -y --no-install-recommends ruby ruby-dev && \
    gem install one_gadget && \
    rm -rf /var/lib/apt/lists/*

# Install additional tools
RUN pip3 install --no-cache-dir --break-system-packages \
    angr \
    z3-solver \
    unicorn \
    keystone-engine \
    capstone

USER ctf
WORKDIR /workspace

CMD ["bash"]