# Historical Atlas read-only MCP image. Only five canonical tools; no secrets or private Archigos.
# Build from reviewed source: docker build -f ops/mcp/Dockerfile -t atlas-mcp:test .
FROM python:3.12-slim-bookworm AS snapshot
WORKDIR /src
COPY . .
RUN python -m scripts.atlas_db validate \
 && python -m scripts.atlas_db build \
 && python -c "import sqlite3; db=sqlite3.connect('dist/atlas.sqlite'); assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'; db.close()"

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ATLAS_SQLITE_PATH=/app/atlas.sqlite \
    ATLAS_MCP_BIND=0.0.0.0 \
    ATLAS_MCP_PORT=8765
RUN python -m pip install --no-cache-dir 'mcp==2.0.0' \
 && groupadd --system --gid 10001 atlas \
 && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent --no-create-home atlas
WORKDIR /app
RUN mkdir /app/scripts
COPY --from=snapshot /src/scripts/atlas_mcp.py /app/scripts/
COPY --from=snapshot /src/scripts/atlas_mcp_http.py /app/scripts/
COPY --from=snapshot /src/scripts/atlas_mcp_query.py /app/scripts/
COPY --from=snapshot /src/scripts/archigos_returnees.py /app/scripts/
COPY --from=snapshot /src/dist/atlas.sqlite /app/atlas.sqlite
RUN chmod 0444 /app/atlas.sqlite
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',8765),timeout=2); s.close()" || exit 1
CMD ["python", "-m", "scripts.atlas_mcp_http"]
