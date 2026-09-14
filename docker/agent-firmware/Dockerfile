# Firmware agent image
FROM ctf/agent-base:latest AS firmware

USER root

# Install firmware tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    binwalk \
    qemu-system-arm \
    qemu-system-mips \
    qemu-system-xtensa \
    squashfs-tools \
    cpio \
    device-tree-compiler \
    u-boot-tools \
    python3-dev \
    libssl-dev \
    lzma \
    lzop \
    && rm -rf /var/lib/apt/lists/*

# Install flashrom
RUN apt-get update && apt-get install -y --no-install-recommends \
    flashrom \
    && rm -rf /var/lib/apt/lists/*

# Install openocd
RUN apt-get update && apt-get install -y --no-install-recommends \
    openocd \
    && rm -rf /var/lib/apt/lists/*

# Install binwalk (latest)
RUN pip3 install --no-cache-dir --break-system-packages binwalk

# Install firmware analysis tools
RUN pip3 install --no-cache-dir --break-system-packages \
    firmware-analysis-toolkit \
    jefferson \
    sasquatch \
    ubireader \
    python-lzo \
    pyuboot

USER ctf
WORKDIR /workspace

CMD ["bash"]