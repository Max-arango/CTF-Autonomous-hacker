# Forensics agent image
FROM ctf/agent-base:latest AS forensics

USER root

# Install forensics tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    sleuthkit \
    autopsy \
    binwalk \
    foremost \
    scalpel \
    exiftool \
    yara \
    bulk-extractor \
    plaso-tools \
    afflib-tools \
    libewf-tools \
    python3-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install volatility3
RUN pip3 install --no-cache-dir --break-system-packages volatility3

# Install additional Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    pytsk3 \
    dfvfs \
    dfwinreg \
    python-registry \
    oletools \
    pefile \
    capstone \
    lief

# Install scalpel config
RUN mkdir -p /etc/scalpel && \
    echo "# Scalpel configuration" > /etc/scalpel/scalpel.conf

USER ctf
WORKDIR /workspace

CMD ["bash"]