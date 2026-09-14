# Meta agent image
FROM ctf/agent-base:latest AS meta

USER root

# Install meta analysis tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    golang-go \
    nodejs \
    npm \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for meta analysis
RUN pip3 install --no-cache-dir --break-system-packages \
    requests \
    beautifulsoup4 \
    lxml \
    pandas \
    numpy \
    scikit-learn \
    nltk \
    spacy \
    textblob \
    vaderSentiment \
    networkx \
    matplotlib \
    seaborn

# Download spaCy model
RUN python3 -m spacy download en_core_web_sm

USER ctf
WORKDIR /workspace

CMD ["bash"]