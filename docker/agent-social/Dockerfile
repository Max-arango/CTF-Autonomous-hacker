# Social engineering agent image
FROM ctf/agent-base:latest AS social

USER root

# Install social engineering tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go \
    nodejs \
    npm \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install googler
RUN pip3 install --no-cache-dir --break-system-packages googler

# Install sherlock
RUN pip3 install --no-cache-dir --break-system-packages sherlock-project

# Install social-analyzer
RUN npm install -g social-analyzer

# Install theharvester
RUN pip3 install --no-cache-dir --break-system-packages theharvester

# Install linkedin scraper
RUN pip3 install --no-cache-dir --break-system-packages linkedin-api

# Install metasploit framework (limited)
RUN curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > /tmp/msfinstall && \
    chmod 755 /tmp/msfinstall && \
    /tmp/msfinstall && \
    rm /tmp/msfinstall

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    requests \
    beautifulsoup4 \
    lxml \
    selenium \
    undetected-chromedriver \
    pysimplegui

USER ctf
WORKDIR /workspace

CMD ["bash"]