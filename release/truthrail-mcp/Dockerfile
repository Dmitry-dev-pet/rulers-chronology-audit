# Metadata-only wrapper around the exact source-reviewed Truthrail MCP image.
# Neither this image nor its source permits a production cutover.
ARG REVIEWED_BASE_IMAGE
FROM ${REVIEWED_BASE_IMAGE}
ENV ALFRED_SHARED_MCP_ENABLED=1 \
    ALFRED_EMBEDDED_ATLAS_REVIEWED=1 \
    ALFRED_PEER_CHAT_MCP_ENABLED=1
LABEL org.opencontainers.image.title="Truthrail shared MCP with canonical Atlas" \
      org.opencontainers.image.source="https://github.com/Dmitry-dev-pet/truthrail-mcp" \
      truthrail.source_revision="a39fabe803e3b6cf15831e1c8b38b3f4b4622e89" \
      truthrail.atlas_source_revision="cb3c65853628607f2e03f30bc4e1a47063b13cd4" \
      truthrail.release_role="same-service-atlas-peer-chat-candidate"
