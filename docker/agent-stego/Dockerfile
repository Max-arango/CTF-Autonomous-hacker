# Stego agent image
FROM ctf/agent-base:latest AS stego

USER root

# Install stego tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    steghide \
    steghide-doc \
    zsteg \
    pngcheck \
    ffmpeg \
    imagemagick \
    exiftool \
    binwalk \
    python3-dev \
    libssl-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    && rm -rf /var/lib/apt/lists/*

# Install stegseek
RUN wget -q https://github.com/RickdeJager/stegseek/releases/download/v0.6/stegseek_0.6-1.deb -O /tmp/stegseek.deb && \
    dpkg -i /tmp/stegseek.deb && \
    rm /tmp/stegseek.deb

# Install stegsolve
RUN wget -q http://www.caesum.com/handbook/Stegsolve.jar -O /opt/stegsolve.jar && \
    echo '#!/bin/bash\njava -jar /opt/stegsolve.jar "$@"' > /usr/local/bin/stegsolve && \
    chmod +x /usr/local/bin/stegsolve

# Install openstego
RUN wget -q https://github.com/syvaidya/openstego/releases/download/openstego-0.8.6/openstego-0.8.6.zip -O /tmp/openstego.zip && \
    unzip -q /tmp/openstego.zip -d /opt/openstego && \
    rm /tmp/openstego.zip && \
    echo '#!/bin/bash\njava -jar /opt/openstego/lib/openstego.jar "$@"' > /usr/local/bin/openstego && \
    chmod +x /usr/local/bin/openstego

# Install Python stego packages
RUN pip3 install --no-cache-dir --break-system-packages \
    stegano \
    lsb \
    pillow \
    numpy \
    opencv-python-headless \
    wave \
    scipy

USER ctf
WORKDIR /workspace

CMD ["bash"]