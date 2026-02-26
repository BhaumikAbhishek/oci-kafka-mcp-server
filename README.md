# OCI Kafka MCP Server

An AI-native control interface for **OCI Streaming with Apache Kafka**, built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) specification.

This MCP server enables LLM agents (Claude, GPT, etc.) to securely manage Kafka clusters through structured tool execution — with built-in safety guardrails, audit logging, and enterprise-grade security.

## Features

- **14 structured tools** for cluster, topic, consumer, and observability operations
- **Read-only by default** — write tools require explicit `--allow-writes` flag
- **Policy guard** — HIGH risk operations (delete topic, scale cluster) require confirmation
- **Circuit breaker** — prevents cascading failures when Kafka is unavailable
- **Structured audit logging** — every tool execution logged as JSON
- **SASL/SCRAM + mTLS** — enterprise security from day one
- **Private networking** — designed for OCI private endpoints

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install

```bash
git clone <repo-url>
cd oci-kafka-mcp-server
uv sync
```

### Run with local Kafka (development)

```bash
# Start a local Kafka broker
docker compose -f docker/docker-compose.yaml up -d

# Run the MCP server (read-only mode)
uv run oci-kafka-mcp

# Run with write tools enabled
uv run oci-kafka-mcp --allow-writes
```

### Configure for OCI Streaming

Set environment variables for your OCI Kafka cluster:

```bash
export KAFKA_BOOTSTRAP_SERVERS="kafka.us-ashburn-1.oci.oraclecloud.com:9092"
export KAFKA_SECURITY_PROTOCOL="SASL_SSL"
export KAFKA_SASL_MECHANISM="SCRAM-SHA-512"
export KAFKA_SASL_USERNAME="your-username"
export KAFKA_SASL_PASSWORD="your-password"
export KAFKA_SSL_CA_LOCATION="/path/to/ca.pem"

uv run oci-kafka-mcp
```

### Use with Claude Desktop

Add to your Claude Desktop MCP configuration (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "oci-kafka": {
      "command": "uv",
      "args": ["--directory", "/path/to/oci-kafka-mcp-server", "run", "oci-kafka-mcp"],
      "env": {
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092"
      }
    }
  }
}
```

## Available Tools

### Cluster Operations
| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_get_cluster_health` | Broker status, controller, topic count | LOW |
| `oci_kafka_get_cluster_config` | Cluster configuration settings | LOW |

### Topic Operations
| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_list_topics` | List all topics | LOW |
| `oci_kafka_describe_topic` | Topic details, partitions, config | LOW |
| `oci_kafka_create_topic` | Create a new topic | MEDIUM |
| `oci_kafka_update_topic_config` | Update topic config | MEDIUM |
| `oci_kafka_delete_topic` | Delete a topic | HIGH |

### Consumer Operations
| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_list_consumer_groups` | List consumer groups | LOW |
| `oci_kafka_describe_consumer_group` | Consumer group details | LOW |
| `oci_kafka_get_consumer_lag` | Per-partition lag metrics | LOW |

### Observability & Diagnostics
| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_get_partition_skew` | Detect partition imbalance | LOW |
| `oci_kafka_detect_under_replicated_partitions` | ISR health check | LOW |

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=oci_kafka_mcp

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/
```

## License

Apache-2.0
