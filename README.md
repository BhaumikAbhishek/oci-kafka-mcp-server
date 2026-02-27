# OCI Kafka MCP Server

An AI-native control interface for **OCI Streaming with Apache Kafka**, built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) specification.

This MCP server enables LLM agents (Claude, GPT, etc.) to securely manage Kafka clusters through structured tool execution — with built-in safety guardrails, audit logging, and enterprise-grade security.

## Features

- **18 structured tools** for cluster, topic, consumer, observability, AI diagnostics, and cluster lifecycle operations
- **Read-only by default** — write tools require explicit `--allow-writes` flag
- **Policy guard** — every tool is risk-classified (LOW/MEDIUM/HIGH); destructive operations require confirmation
- **AI diagnostic tools** — orchestrate multiple Kafka operations to produce scaling recommendations and lag root cause analyses
- **Circuit breaker** — prevents cascading failures when Kafka is unavailable
- **Structured audit logging** — every tool execution logged as JSON with timestamp, input hash, and duration
- **SASL/SCRAM-SHA-512 + TLS** — enterprise security from day one
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
export KAFKA_BOOTSTRAP_SERVERS="bootstrap-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com:9092"
export KAFKA_SECURITY_PROTOCOL="SASL_SSL"
export KAFKA_SASL_MECHANISM="SCRAM-SHA-512"
export KAFKA_SASL_USERNAME="your-username"
export KAFKA_SASL_PASSWORD="your-password"
export KAFKA_SSL_CA_LOCATION="/path/to/ca.pem"

uv run oci-kafka-mcp
```

### Use with Claude Desktop

Add to your Claude Desktop MCP configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "oci-kafka": {
      "command": "/path/to/oci-kafka-mcp-server/.venv/bin/oci-kafka-mcp",
      "args": ["--allow-writes"],
      "env": {
        "KAFKA_BOOTSTRAP_SERVERS": "your-bootstrap:9092",
        "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
        "KAFKA_SASL_MECHANISM": "SCRAM-SHA-512",
        "KAFKA_SASL_USERNAME": "your-username",
        "KAFKA_SASL_PASSWORD": "your-password",
        "KAFKA_SSL_CA_LOCATION": "/path/to/ca.pem"
      }
    }
  }
}
```

## Available Tools (18)

### Cluster Operations

| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_get_cluster_health` | Broker status, controller, topic count | LOW |
| `oci_kafka_get_cluster_config` | Cluster configuration settings | LOW |

### Topic Operations

| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_list_topics` | List all topics | LOW |
| `oci_kafka_describe_topic` | Partition details, leaders, replicas, ISR | LOW |
| `oci_kafka_create_topic` | Create a topic with partitions and replication factor | MEDIUM |
| `oci_kafka_update_topic_config` | Update topic configuration (retention, compaction, etc.) | MEDIUM |
| `oci_kafka_delete_topic` | Delete a topic (requires confirmation) | HIGH |

### Consumer Operations

| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_list_consumer_groups` | List all consumer groups | LOW |
| `oci_kafka_describe_consumer_group` | Group state, members, coordinator, assignments | LOW |
| `oci_kafka_get_consumer_lag` | Per-partition lag, committed offsets, end offsets | LOW |
| `oci_kafka_reset_consumer_offset` | Reset offsets to earliest/latest/specific (requires confirmation) | HIGH |
| `oci_kafka_delete_consumer_group` | Delete a consumer group (requires confirmation) | HIGH |

### Observability

| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_get_partition_skew` | Detect partition imbalance across brokers | LOW |
| `oci_kafka_detect_under_replicated_partitions` | Find partitions where ISR < replica count | LOW |

### AI Diagnostics

| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_recommend_scaling` | Orchestrates health, skew, and replication data into scaling recommendations | LOW |
| `oci_kafka_analyze_lag_root_cause` | Correlates consumer state, lag, and topology into root cause analysis | LOW |

### Cluster Lifecycle (OCI Control Plane)

| Tool | Description | Risk |
|------|-------------|------|
| `oci_kafka_create_cluster` | Provision a new Kafka cluster via OCI SDK | HIGH |
| `oci_kafka_scale_cluster` | Scale broker count for an existing cluster | HIGH |

## Safety Model

| Risk Level | Behavior | Examples |
|------------|----------|----------|
| **LOW** | Always allowed | Health checks, list/describe operations |
| **MEDIUM** | Requires `--allow-writes` | Create topic, update config |
| **HIGH** | Requires `--allow-writes` + confirmation | Delete topic, reset offsets, cluster lifecycle |

## Development

```bash
# Run tests (68 tests, all unit — no Kafka broker needed)
uv run pytest

# Run tests with coverage
uv run pytest --cov=oci_kafka_mcp --cov-report=term-missing

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full security architecture document, including threat model, dependency audit, and deployment architecture.

## License

Apache-2.0
