# OSINT agent image
FROM ctf/agent-base:latest AS osint

USER root

# Install OSINT tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go \
    nodejs \
    npm \
    whois \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Install amass
RUN go install -v github.com/owasp-amass/amass/v4/...@latest

# Install subfinder
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Install dnsx
RUN go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest

# Install httpx
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

# Install nuclei
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# Install shodan CLI
RUN pip3 install --no-cache-dir --break-system-packages shodan

# Install censys
RUN pip3 install --no-cache-dir --break-system-packages censys

# Install theHarvester
RUN pip3 install --no-cache-dir --break-system-packages theharvester

# Install additional Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    requests \
    beautifulsoup4 \
    lxml \
    dnspython \
    python-whois \
    ipwhois \
    shodan \
    censys

USER ctf
WORKDIR /workspace

CMD ["bash"]