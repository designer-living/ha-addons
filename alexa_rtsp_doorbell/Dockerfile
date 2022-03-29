ARG BUILD_FROM
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

# Copy data for add-on
COPY requirements.txt /app/requirements.txt 

# Add Home Assistant wheels repository

ENV WHEELS_LINKS=https://wheels.home-assistant.io/alpine-3.14/${BUILD_ARCH}/

RUN pip3 install -r /app/requirements.txt --find-links ${WHEELS_LINKS}

COPY app /app

WORKDIR "/app"

CMD [ "/run.sh" ]