FROM ghcr.io/astral-sh/uv:0.12.10 AS uv
FROM python:3.12-slim-bookworm
LABEL io.modelcontextprotocol.server.name="io.github.farbodghasemlu/darkweb-mcp" org.opencontainers.image.source="https://github.com/farbodghasemlu/darkweb-mcp"
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_CACHE=1 UV_COMPILE_BYTECODE=0 PATH=/app/.venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends tor obfs4proxy snowflake-client ca-certificates libseccomp2 && rm -rf /var/lib/apt/lists/* && useradd -u 10001 -M -s /usr/sbin/nologin onion
WORKDIR /app
COPY pyproject.toml uv.lock engines.yaml LICENSE ./
COPY blocklists ./blocklists
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python && chown -R onion:onion /app
USER 10001:10001
ENTRYPOINT ["onion-search-mcp"]
CMD ["--bundled-tor"]
