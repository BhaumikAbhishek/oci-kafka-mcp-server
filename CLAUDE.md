# CLAUDE.md — OCI Kafka MCP Server

## Project Overview

This is an MCP (Model Context Protocol) server that enables LLM agents to securely manage OCI Streaming with Apache Kafka clusters. It exposes structured tools for cluster, topic, consumer, and observability operations.

## Architecture

- **Framework:** FastMCP (Python MCP SDK)
- **Kafka Client:** confluent-kafka (supports SASL/SCRAM + mTLS)
- **OCI Client:** oci Python SDK (StreamClient, StreamAdminClient)
- **Transport:** STDIO (primary), HTTP/SSE (future)
- **Deployment:** Helm chart on OKE (Oracle Kubernetes Engine)

## Key Design Decisions

1. **Tool naming:** `oci_kafka_{action}_{resource}` (e.g., `oci_kafka_get_cluster_health`)
2. **Read/write mode:** Server starts in read-only mode by default. Pass `--allow-writes` to enable write tools.
3. **Policy guard:** Tools have risk levels (LOW/MEDIUM/HIGH). HIGH risk tools require explicit confirmation.
4. **Audit logging:** Every tool execution generates a structured JSON audit log entry.
5. **Stateless:** No session state stored. Kafka connections managed via connection pool.
6. **Circuit breaker:** Prevents cascading failures when Kafka is unavailable.

## Directory Structure

- `src/oci_kafka_mcp/server.py` — MCP server entry point
- `src/oci_kafka_mcp/config.py` — Configuration (env vars, CLI args)
- `src/oci_kafka_mcp/tools/` — MCP tool implementations (cluster, topics, consumers, observability)
- `src/oci_kafka_mcp/kafka/` — Kafka client wrappers (admin, consumer, connection pool)
- `src/oci_kafka_mcp/oci/` — OCI SDK wrappers (streaming client)
- `src/oci_kafka_mcp/security/` — Auth (mTLS/SCRAM) and policy guard
- `src/oci_kafka_mcp/audit/` — Structured audit logging
- `tests/` — Unit and integration tests
- `docker/` — Dockerfile and docker-compose for local Kafka
- `helm/` — Helm chart for OKE deployment

## Commands

```bash
# Install dependencies
uv sync

# Run the MCP server (STDIO mode)
uv run oci-kafka-mcp

# Run with write tools enabled
uv run oci-kafka-mcp --allow-writes

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=oci_kafka_mcp

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/

# Start local Kafka (for development)
docker compose -f docker/docker-compose.yaml up -d

# Stop local Kafka
docker compose -f docker/docker-compose.yaml down
```

## Configuration

The server is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | `localhost:9092` |
| `KAFKA_SECURITY_PROTOCOL` | `PLAINTEXT`, `SASL_SSL`, `SSL` | `PLAINTEXT` |
| `KAFKA_SASL_MECHANISM` | `SCRAM-SHA-512`, `SCRAM-SHA-256`, `PLAIN` | — |
| `KAFKA_SASL_USERNAME` | SASL username | — |
| `KAFKA_SASL_PASSWORD` | SASL password | — |
| `KAFKA_SSL_CA_LOCATION` | CA certificate path | — |
| `KAFKA_SSL_CERT_LOCATION` | Client certificate path | — |
| `KAFKA_SSL_KEY_LOCATION` | Client key path | — |
| `OCI_CONFIG_FILE` | OCI config file path | `~/.oci/config` |
| `OCI_PROFILE` | OCI config profile | `DEFAULT` |
| `OCI_COMPARTMENT_ID` | OCI compartment OCID | — |
| `ALLOW_WRITES` | Enable write tools | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Testing

- Unit tests mock the Kafka and OCI clients
- Integration tests require a running Kafka cluster (use docker-compose)
- Run specific test files: `uv run pytest tests/unit/test_cluster_tools.py`

## Reference Implementations

- [confluentinc/mcp-confluent](https://github.com/confluentinc/mcp-confluent) — Modular tool handler pattern
- [tuannvm/kafka-mcp-server](https://github.com/tuannvm/kafka-mcp-server) — SASL/SCRAM + mTLS patterns
- [awslabs/mcp (MSK)](https://github.com/awslabs/mcp) — Read/write mode separation
- [oracle/mcp](https://github.com/oracle/mcp) — OCI auth patterns
