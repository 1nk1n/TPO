FROM jenkins/jenkins:lts-jdk21

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv \
       qemu-system-arm ipmitool \
       chromium chromium-driver \
       curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/lab7/requirements.txt

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
       -r /opt/lab7/requirements.txt

ENV PATH="/opt/venv/bin:${PATH}"
ENV HEADLESS=1

USER jenkins

RUN jenkins-plugin-cli --jenkins-update-center-download-url https://mirror.netone.nl/jenkins/plugins --plugins \
    workflow-aggregator \
    junit
