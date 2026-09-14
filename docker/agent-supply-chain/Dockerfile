# Supply chain agent image
FROM ctf/agent-base:latest AS supply_chain

USER root

# Install supply chain tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go \
    nodejs \
    npm \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install syft
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

# Install grype
RUN curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin

# Install trivy
RUN wget -q https://github.com/aquasecurity/trivy/releases/download/v0.50.0/trivy_0.50.0_Linux-64bit.deb -O /tmp/trivy.deb && \
    dpkg -i /tmp/trivy.deb && \
    rm /tmp/trivy.deb

# Install cosign
RUN wget -q https://github.com/sigstore/cosign/releases/download/v2.2.3/cosign-linux-amd64 -O /usr/local/bin/cosign && \
    chmod +x /usr/local/bin/cosign

# Install in-toto
RUN pip3 install --no-cache-dir --break-system-packages in-toto

# Install sigstore
RUN pip3 install --no-cache-dir --break-system-packages sigstore

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    syft \
    grype \
    trivy \
    pip-audit \
    safety \
    cyclonedx-bom \
    spdx-tools \
    packageurl-python

USER ctf
WORKDIR /workspace

CMD ["bash"]