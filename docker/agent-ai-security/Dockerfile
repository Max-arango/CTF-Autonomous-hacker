# AI Security agent image
FROM ctf/agent-base:latest AS ai_security

USER root

# Install AI/ML packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch
RUN pip3 install --no-cache-dir --break-system-packages \
    torch \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Install TensorFlow
RUN pip3 install --no-cache-dir --break-system-packages tensorflow-cpu

# Install adversarial libraries
RUN pip3 install --no-cache-dir --break-system-packages \
    foolbox \
    cleverhans \
    advertorch \
    robustness \
    textattack \
    art \
    numpy \
    scikit-learn \
    pandas \
    matplotlib \
    seaborn \
    jupyter \
    transformers \
    datasets \
    accelerate \
    peft \
    bitsandbytes

# Install additional tools
RUN pip3 install --no-cache-dir --break-system-packages \
    garak \
    prompt-injection \
    llm-guard

USER ctf
WORKDIR /workspace

CMD ["bash"]