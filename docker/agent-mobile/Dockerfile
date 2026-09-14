# Mobile agent image
FROM ctf/agent-base:latest AS mobile

USER root

# Install Android SDK tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    android-sdk-platform-tools \
    aapt \
    apktool \
    && rm -rf /var/lib/apt/lists/*

# Install jadx
RUN wget -q https://github.com/skylot/jadx/releases/download/v1.5.1/jadx-1.5.1.zip -O /tmp/jadx.zip && \
    unzip -q /tmp/jadx.zip -d /opt/jadx && \
    rm /tmp/jadx.zip && \
    ln -s /opt/jadx/bin/jadx /usr/local/bin/jadx && \
    ln -s /opt/jadx/bin/jadx-gui /usr/local/bin/jadx-gui

# Install apksigner
RUN apt-get update && apt-get install -y --no-install-recommends \
    apksigner \
    zipalign \
    && rm -rf /var/lib/apt/lists/*

# Install frida
RUN pip3 install --no-cache-dir --break-system-packages frida-tools objection

# Install additional Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    androguard \
    quark-engine \
    mobsf \
    drozer \
    frida \
    objection

# Install dex2jar
RUN wget -q https://github.com/pxb1988/dex2jar/releases/download/2.1/dex2jar-2.1.zip -O /tmp/dex2jar.zip && \
    unzip -q /tmp/dex2jar.zip -d /opt/dex2jar && \
    rm /tmp/dex2jar.zip && \
    chmod +x /opt/dex2jar/*.sh && \
    ln -s /opt/dex2jar/d2j-dex2jar.sh /usr/local/bin/dex2jar

# Install enjarify
RUN pip3 install --no-cache-dir --break-system-packages enjarify

USER ctf
WORKDIR /workspace

CMD ["bash"]