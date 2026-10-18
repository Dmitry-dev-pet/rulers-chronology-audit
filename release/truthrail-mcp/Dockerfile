# Metadata-only wrapper around the exact source-reviewed Truthrail MCP image.
# Neither this image nor its source permits a production cutover.
ARG REVIEWED_BASE_IMAGE
FROM ${REVIEWED_BASE_IMAGE}
ENV ALFRED_SHARED_MCP_ENABLED=1 \
    ALFRED_EMBEDDED_ATLAS_REVIEWED=1 \
    ALFRED_PEER_CHAT_MCP_ENABLED=1
LABEL org.opencontainers.image.title="Truthrail shared MCP with canonical Atlas" \
      org.opencontainers.image.source="https://github.com/Dmitry-dev-pet/truthrail-mcp" \
      truthrail.source_revision="85c84dffaff2807d3af0c76f165fa205369903ad" \
      truthrail.atlas_source_revision="cb3c65853628607f2e03f30bc4e1a47063b13cd4" \
      truthrail.release_role="same-service-atlas-peer-chat-candidate"
