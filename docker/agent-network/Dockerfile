# Network agent image
FROM ctf/agent-base:latest AS network

USER root

# Install network tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    rustscan \
    masscan \
    netcat-openbsd \
    socat \
    tcpdump \
    tshark \
    wireshark-common \
    scapy \
    python3-dev \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

# Install bettercap
RUN wget -q https://github.com/bettercap/bettercap/releases/download/v2.32.0/bettercap_linux_amd64.zip -O /tmp/bettercap.zip && \
    unzip -q /tmp/bettercap.zip -d /usr/local/bin && \
    rm /tmp/bettercap.zip

# Install Python network packages
RUN pip3 install --no-cache-dir --break-system-packages \
    scapy \
    netaddr \
    ipaddress \
    pyshark \
    dpkt \
    pcapy \
    python-nmap \
    nmapthon \
    masscan

USER ctf
WORKDIR /workspace

CMD ["bash"]