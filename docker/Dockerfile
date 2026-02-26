FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for confluent-kafka (librdkafka)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc librdkafka-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system .

# Run the MCP server
ENTRYPOINT ["oci-kafka-mcp"]
CMD ["--transport", "stdio"]
