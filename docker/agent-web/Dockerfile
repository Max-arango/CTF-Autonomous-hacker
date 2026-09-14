# Web agent image
FROM ctf/agent-base:latest AS web

USER root

# Install web-specific tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install ffuf
RUN go install github.com/ffuf/ffuf/v2@latest

# Install feroxbuster
RUN cargo install feroxbuster --locked

# Install gobuster
RUN go install github.com/OJ/gobuster/v3@latest

# Install httpx
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

# Install nuclei
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# Install katana
RUN go install -v github.com/projectdiscovery/katana/cmd/katana@latest

# Install hakrawler
RUN go install -v github.com/hakluke/hakrawler@latest

# Install sqlmap
RUN pip3 install --no-cache-dir --break-system-packages sqlmap

# Install mitmproxy
RUN pip3 install --no-cache-dir --break-system-packages mitmproxy

# Install dirsearch
RUN pip3 install --no-cache-dir --break-system-packages dirsearch

# Install additional Python packages for web
RUN pip3 install --no-cache-dir --break-system-packages \
    requests \
    beautifulsoup4 \
    lxml \
    aiohttp \
    playwright \
    mitmproxy \
    flask \
    fastapi \
    uvicorn

# Install playwright browsers
RUN playwright install chromium

USER ctf
WORKDIR /workspace

CMD ["bash"]