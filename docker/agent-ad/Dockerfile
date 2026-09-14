# AD agent image
FROM ctf/agent-base:latest AS ad

USER root

# Install AD tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    libssl-dev \
    libkrb5-dev \
    krb5-user \
    ldap-utils \
    samba-client \
    rpcclient \
    && rm -rf /var/lib/apt/lists/*

# Install impacket
RUN pip3 install --no-cache-dir --break-system-packages impacket

# Install kerbrute
RUN wget -q https://github.com/ropnop/kerbrute/releases/download/v1.0.3/kerbrute_linux_amd64 -O /usr/local/bin/kerbrute && \
    chmod +x /usr/local/bin/kerbrute

# Install netexec (crackmapexec)
RUN pip3 install --no-cache-dir --break-system-packages netexec

# Install bloodhound-python
RUN pip3 install --no-cache-dir --break-system-packages bloodhound

# Install ldapdomaindump
RUN pip3 install --no-cache-dir --break-system-packages ldapdomaindump

# Install adidnsdump
RUN pip3 install --no-cache-dir --break-system-packages adidnsdump

# Install certipy
RUN pip3 install --no-cache-dir --break-system-packages certipy-ad

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    ldap3 \
    python-ldap \
    dnspython \
    kerberos \
    gssapi

USER ctf
WORKDIR /workspace

CMD ["bash"]