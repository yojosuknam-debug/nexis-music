FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends icecast2 gettext-base \
    && rm -rf /var/lib/apt/lists/*
COPY icecast.xml.tmpl /etc/icecast2/icecast.xml.tmpl
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /tmp/icecast && chown icecast2 /tmp/icecast
USER icecast2
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
