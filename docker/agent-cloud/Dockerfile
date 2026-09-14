# Cloud agent image
FROM ctf/agent-base:latest AS cloud

USER root

# Install cloud CLIs
RUN apt-get update && apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip" && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/aws /tmp/awscliv2.zip

# Install Azure CLI
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Install Google Cloud CLI
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    apt-get update && apt-get install -y google-cloud-cli && \
    rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl

# Install Helm
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install trivy
RUN wget -q https://github.com/aquasecurity/trivy/releases/download/v0.50.0/trivy_0.50.0_Linux-64bit.deb -O /tmp/trivy.deb && \
    dpkg -i /tmp/trivy.deb && \
    rm /tmp/trivy.deb

# Install syft
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

# Install grype
RUN curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin

# Install kube-hunter
RUN pip3 install --no-cache-dir --break-system-packages kube-hunter

# Install kube-bench
RUN wget -q https://github.com/aquasecurity/kube-bench/releases/download/v0.9.1/kube-bench_0.9.1_linux_amd64.deb -O /tmp/kube-bench.deb && \
    dpkg -i /tmp/kube-bench.deb && \
    rm /tmp/kube-bench.deb

# Install Python cloud packages
RUN pip3 install --no-cache-dir --break-system-packages \
    boto3 \
    azure-mgmt-resource \
    azure-mgmt-compute \
    azure-mgmt-network \
    google-cloud-compute \
    google-cloud-storage \
    kubernetes \
    helm \
    docker \
    trivy \
    syft \
    grype

USER ctf
WORKDIR /workspace

CMD ["bash"]