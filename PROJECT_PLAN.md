# OCI Kafka MCP Server — Project Plan & Roadmap

> **Project:** OCI Streaming with Apache Kafka — MCP Server
> **Owner:** Abhishek (PM/Architect/Engineer)
> **Created:** 2026-02-25
> **Last Updated:** 2026-02-26
> **Status:** Complete — Sprint 0/1/2/3

---

## 1. Executive Summary

This project builds a Model Context Protocol (MCP) server that enables LLM agents (Claude, GPT, etc.) to securely operate OCI Streaming with Apache Kafka clusters through structured tool execution. The server will be customer-deployed via Helm chart on OKE (Oracle Kubernetes Engine) with private connectivity, supporting mTLS and SASL/SCRAM authentication.

**No dedicated OCI Streaming/Kafka MCP server exists today** — this is a first-mover opportunity.

---

## 2. Competitive Landscape & Open-Source References

| Project | Language | Maturity | What We Leverage |
|---------|----------|----------|------------------|
| [confluentinc/mcp-confluent](https://github.com/confluentinc/mcp-confluent) | TypeScript | High (official) | Modular tool handler pattern, 37 tools reference |
| [tuannvm/kafka-mcp-server](https://github.com/tuannvm/kafka-mcp-server) | Go | High | SASL/SCRAM + mTLS patterns, core Kafka tool set |
| [awslabs/mcp (MSK)](https://github.com/awslabs/mcp) | Python | High (official) | Read/write mode separation, operational recommendations |
| [oracle/mcp](https://github.com/oracle/mcp) | Python | High (official) | OCI auth patterns, SDK usage, distribution model |
| [Joel-hanson/kafka-mcp-server](https://github.com/Joel-hanson/kafka-mcp-server) | Python | Moderate | FastMCP-based architecture reference |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Python | Stable | Core protocol implementation |

---

## 3. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.11+ | Aligns with oracle/mcp, OCI SDK, MCP SDK; most approachable |
| **MCP Framework** | `mcp` (FastMCP) | Official Python SDK, fastest path to working server |
| **Kafka Client** | `confluent-kafka` | Production-grade, supports SASL/SCRAM + mTLS |
| **OCI SDK** | `oci` | Official OCI Python SDK with StreamClient/StreamAdminClient |
| **Package Manager** | `uv` / Poetry | Modern Python dependency management |
| **Container** | Docker | Containerized deployment for OKE |
| **Orchestration** | Helm | Kubernetes deployment on OKE |
| **Testing** | pytest + pytest-asyncio | Standard Python testing |
| **Linting** | ruff | Fast Python linter/formatter |

---

## 4. Project Structure

```
oci-kafka-mcp-server/
├── src/
│   └── oci_kafka_mcp/
│       ├── __init__.py
│       ├── server.py                 # MCP server entry point (FastMCP)
│       ├── config.py                 # Configuration management
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── cluster.py            # Cluster health & config (2 tools)
│       │   ├── cluster_management.py # OCI cluster lifecycle (2 tools)
│       │   ├── topics.py             # Topic CRUD (5 tools)
│       │   ├── consumers.py          # Consumer read + write (5 tools)
│       │   ├── observability.py      # Partition skew & replication (2 tools)
│       │   └── diagnostics.py        # AI diagnostic tools (2 tools)
│       ├── kafka/
│       │   ├── __init__.py
│       │   ├── admin_client.py       # Kafka AdminClient wrapper
│       │   ├── consumer_client.py    # Consumer operations wrapper
│       │   └── connection.py         # Connection pool + circuit breaker
│       ├── oci/
│       │   ├── __init__.py
│       │   └── streaming_client.py   # OCI Streaming API wrapper
│       ├── security/
│       │   ├── __init__.py
│       │   ├── auth.py               # mTLS + SASL/SCRAM auth
│       │   └── policy_guard.py       # Risk classification + confirmation
│       └── audit/
│           ├── __init__.py
│           └── logger.py             # Structured JSON audit logging
├── helm/
│   └── oci-kafka-mcp/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           ├── secret.yaml
│           ├── hpa.yaml
│           ├── pdb.yaml
│           └── networkpolicy.yaml
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Shared test fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_cluster_tools.py
│   │   ├── test_topic_tools.py
│   │   ├── test_consumer_tools.py
│   │   ├── test_observability_tools.py
│   │   ├── test_policy_guard.py
│   │   └── test_audit_logger.py
│   └── integration/
│       ├── __init__.py
│       └── test_kafka_integration.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yaml           # Local Kafka for development
├── docs/
│   ├── getting-started.md
│   ├── tool-reference.md
│   └── deployment-guide.md
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── PROJECT_PLAN.md                    # <-- This file
└── .gitignore
```

---

## 5. MCP Tools — Complete Inventory

### 5.1 Cluster Operations

| Tool | Description | Risk | Confirmation | Sprint |
|------|-------------|------|-------------|--------|
| `oci_kafka_get_cluster_health` | Broker status, version, controller info | LOW | No | 1 |
| `oci_kafka_get_cluster_config` | Retrieve cluster configuration | LOW | No | 1 |
| `oci_kafka_create_cluster` | Create Kafka cluster via OCI API | HIGH | **Mandatory** | 2 |
| `oci_kafka_scale_cluster` | Scale broker count | HIGH | **Mandatory** | 2 |

### 5.2 Topic Operations

| Tool | Description | Risk | Confirmation | Sprint |
|------|-------------|------|-------------|--------|
| `oci_kafka_list_topics` | List all topics | LOW | No | 1 |
| `oci_kafka_describe_topic` | Topic config, partitions, replicas | LOW | No | 1 |
| `oci_kafka_create_topic` | Create topic with partitions/RF | MEDIUM | Optional | 2 |
| `oci_kafka_update_topic_config` | Modify retention, compaction, etc. | MEDIUM | Optional | 2 |
| `oci_kafka_delete_topic` | Delete a topic | HIGH | **Mandatory** | 2 |

### 5.3 Consumer Operations

| Tool | Description | Risk | Confirmation | Sprint |
|------|-------------|------|-------------|--------|
| `oci_kafka_get_consumer_lag` | Lag per partition for a consumer group | LOW | No | 1 |
| `oci_kafka_list_consumer_groups` | List all consumer groups | LOW | No | 1 |
| `oci_kafka_describe_consumer_group` | Detailed consumer group info | LOW | No | 1 |
| `oci_kafka_reset_consumer_offset` | Reset offsets for consumer group | HIGH | **Mandatory** | 2 |
| `oci_kafka_delete_consumer_group` | Delete a consumer group | HIGH | **Mandatory** | 2 |

### 5.4 Observability & Diagnostics

| Tool | Description | Risk | Confirmation | Sprint |
|------|-------------|------|-------------|--------|
| `oci_kafka_get_partition_skew` | Detect partition imbalance | LOW | No | 1 |
| `oci_kafka_detect_under_replicated_partitions` | ISR health check | LOW | No | 1 |
| `oci_kafka_recommend_scaling` | Rule-based scaling recommendation | LOW | No | 3 |
| `oci_kafka_analyze_lag_root_cause` | Multi-tool diagnostic chain | LOW | No | 3 |

**Total: 18 tools** (11 read-only, 2 write MEDIUM, 5 write HIGH)

---

## 6. Architecture Patterns

### 6.1 Key Patterns Adopted

| Pattern | Source | Implementation |
|---------|--------|----------------|
| **Modular tool handlers** | Confluent | Each tool is a decorated FastMCP function with schema |
| **Read/write mode** | AWS MSK | `--allow-writes` flag, default to read-only |
| **Service-prefixed naming** | Azure MCP / Best Practices | `oci_kafka_{action}_{resource}` |
| **OCI auth patterns** | oracle/mcp | Config provider, API key / instance principal |
| **Policy guard** | PRD | Risk classification (LOW/MEDIUM/HIGH), confirmation |
| **Circuit breaker** | Architecture doc | Prevent cascading failures |
| **Audit logging** | Architecture doc | Structured JSON, every tool execution |
| **Stateless design** | Best practices | No session state, connections per-request |

### 6.2 Security Architecture (Phase 1)

```
┌─────────────────────────────────────────────────┐
│ LLM Agent (Claude / GPT / etc.)                │
│                                                 │
│  MCP Client (JSON-RPC over STDIO/HTTPS)        │
└────────────────────┬────────────────────────────┘
                     │ TLS 1.2+
                     ▼
┌─────────────────────────────────────────────────┐
│ MCP Server (Kubernetes Pod)                     │
│                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ FastMCP  │→ │ Policy Guard │→ │ Audit Log │ │
│  │ Protocol │  │ (Risk Check) │  │ (JSON)    │ │
│  └──────────┘  └──────────────┘  └───────────┘ │
│       │                                         │
│  ┌────▼─────────────────────────────────┐       │
│  │ Kafka Client (confluent-kafka)       │       │
│  │  - SASL/SCRAM-SHA-512               │       │
│  │  - mTLS certificates                │       │
│  │  - Connection pool                  │       │
│  │  - Circuit breaker                  │       │
│  └────┬─────────────────────────────────┘       │
│       │                                         │
│  ┌────▼─────────────────────────────────┐       │
│  │ OCI SDK (oci.streaming)              │       │
│  │  - StreamAdminClient                │       │
│  │  - Cluster lifecycle operations     │       │
│  └──────────────────────────────────────┘       │
└────────────────────┬────────────────────────────┘
                     │ mTLS / SASL-SCRAM
                     ▼
┌─────────────────────────────────────────────────┐
│ OCI Managed Kafka Cluster (Private Endpoint)    │
│  - Brokers                                      │
│  - Admin APIs                                   │
│  - ZooKeeper / KRaft                            │
└─────────────────────────────────────────────────┘
```

---

## 7. Sprint Plan & Progress Tracker

### Sprint 0: Foundation & Setup (Week 1–2)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 0.1 | Initialize Python project (pyproject.toml, deps) | ✅ Done | Python 3.13, all deps installed |
| 0.2 | Create directory structure | ✅ Done | Full src/tests/docker/helm layout |
| 0.3 | Create CLAUDE.md context file | ✅ Done | Comprehensive AI context doc |
| 0.4 | Set up Docker Compose (local Kafka) | ✅ Done | KRaft mode, no ZooKeeper |
| 0.5 | Set up .gitignore | ✅ Done | |
| 0.6 | Study reference implementations | ✅ Done | Researched 6+ existing MCP servers |
| 0.7 | Provision OCI Streaming test cluster | ⬜ Not Started | Manual step by Abhishek |

### Sprint 1: Core Server + Read-Only Tools (Week 3–4)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | MCP server skeleton (FastMCP, server.py) | ✅ Done | CLI with --allow-writes flag |
| 1.2 | Configuration management (config.py) | ✅ Done | Pydantic Settings, env vars |
| 1.3 | Kafka connection layer (mTLS + SASL/SCRAM) | ✅ Done | AdminClient + ConsumerClient + CircuitBreaker |
| 1.4 | Audit logger (structured JSON) | ✅ Done | Context manager pattern |
| 1.5 | Tool: `oci_kafka_get_cluster_health` | ✅ Done | |
| 1.6 | Tool: `oci_kafka_get_cluster_config` | ✅ Done | |
| 1.7 | Tool: `oci_kafka_list_topics` | ✅ Done | |
| 1.8 | Tool: `oci_kafka_describe_topic` | ✅ Done | |
| 1.9 | Tool: `oci_kafka_get_consumer_lag` | ✅ Done | |
| 1.10 | Tool: `oci_kafka_list_consumer_groups` | ✅ Done | |
| 1.11 | Tool: `oci_kafka_describe_consumer_group` | ✅ Done | |
| 1.12 | Tool: `oci_kafka_get_partition_skew` | ✅ Done | |
| 1.13 | Tool: `oci_kafka_detect_under_replicated_partitions` | ✅ Done | |
| 1.14 | Unit tests for all read tools | ✅ Done | 41 tests, all passing |
| 1.15 | End-to-end test with local Kafka | ✅ Done | Podman + apache/kafka:3.9.0, all tools verified |

### Sprint 2: Write Tools + Policy Guard (Week 5–6)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Policy guard engine (risk classification) | ✅ Done | LOW/MEDIUM/HIGH + confirmation |
| 2.2 | Read/write mode flag (`--allow-writes`) | ✅ Done | CLI arg + env var |
| 2.3 | Tool: `oci_kafka_create_topic` | ✅ Done | MEDIUM risk |
| 2.4 | Tool: `oci_kafka_update_topic_config` | ✅ Done | MEDIUM risk |
| 2.5 | Tool: `oci_kafka_delete_topic` | ✅ Done | HIGH risk, confirmation required |
| 2.6 | Tool: `oci_kafka_reset_consumer_offset` | ✅ Done | HIGH risk, earliest/latest/specific strategies |
| 2.7 | Tool: `oci_kafka_delete_consumer_group` | ✅ Done | HIGH risk, replaces pause/resume |
| 2.8 | Tool: `oci_kafka_create_cluster` (OCI API) | ✅ Done | OCI SDK with graceful fallback |
| 2.9 | Tool: `oci_kafka_scale_cluster` (OCI API) | ✅ Done | OCI SDK with graceful fallback |
| 2.10 | Integration tests against OCI Streaming | ✅ Done | Live OCI cluster verified via Claude Desktop |
| 2.11 | Unit tests for write tools + policy guard | ✅ Done | 57 tests (16 new for Sprint 2) |

### Sprint 3: AI Diagnostics + Helm + Polish (Week 7–8)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Tool: `oci_kafka_recommend_scaling` | ✅ Done | Orchestrates 3 Kafka ops, severity-ranked recommendations |
| 3.2 | Tool: `oci_kafka_analyze_lag_root_cause` | ✅ Done | Orchestrates 4 Kafka ops, ranked root causes |
| 3.3 | Dockerfile | ✅ Done | python:3.11-slim, uv-based |
| 3.4 | Helm chart (all templates) | ⬜ Not Started | |
| 3.5 | End-to-end testing on OKE | ⬜ Not Started | |
| 3.6 | Performance testing (100 sessions, <2s P95) | ⬜ Not Started | |
| 3.7 | Documentation: ARCHITECTURE.md | ✅ Done | SEC ARC review document (649 lines) |
| 3.8 | Documentation: DEMO_RUNBOOK.md | ✅ Done | 7-act demo script, 18-tool inventory |
| 3.9 | Documentation: DEMO_SETUP_GUIDE.md | ✅ Done | End-to-end OCI setup guide |
| 3.10 | README.md | ✅ Done | Updated with 18 tools, all sections |
| 3.11 | Unit tests for diagnostic tools | ✅ Done | 68 tests total (11 new for Sprint 3) |
| 3.12 | GitHub Actions CI/CD | ✅ Done | Tests + ruff + mypy + coverage |

---

## 8. Phase 2 Roadmap (Weeks 9–16)

| Feature | Description | Dependencies |
|---------|-------------|-------------|
| Public connectivity | API Gateway + WAF integration | OCI Kafka public endpoints |
| OCI Monitoring integration | Metrics adapter for broker CPU, disk, network | OCI Monitoring APIs |
| Partition skew auto-detection | Proactive alerting via MCP resources | Phase 1 observability tools |
| Policy-based guardrails | Time windows, environment restrictions, rate limits | Phase 1 policy guard |
| RBAC within MCP | Role-based tool access control | Phase 1 security layer |
| Cross-cluster intelligence | Multi-cluster comparison and anomaly detection | Phase 1 tools + multi-cluster config |

---

## 9. Phase 3 Roadmap (Weeks 17+)

| Feature | Description | Dependencies |
|---------|-------------|-------------|
| Managed MCP service | OCI-native, no Helm deployment | OCI service infrastructure |
| IAM integration | Resource principals, OCI policy enforcement | OCI IAM support for Kafka |
| OCI Audit integration | Immutable execution records | OCI Audit APIs |
| OCI Generative AI integration | Native LLM integration | OCI GenAI service |
| Multi-tenant architecture | Cluster metadata registry, tenant isolation | Managed service infrastructure |
| Autonomous Kafka scaling | AI-driven auto-scaling based on metrics | Phase 2 monitoring + diagnostics |

---

## 10. KPIs & Success Metrics

### Adoption
- % of Kafka clusters with MCP deployed
- AI-invoked operations per cluster per week
- Enterprise accounts adopting MCP

### Operational
- MTTR reduction: target **50%**
- Manual CLI usage reduction: target **40%**
- Incident escalation reduction: target **30%**

### Performance
- Tool success rate: **> 99%**
- Average execution latency: **< 2 seconds** (P95)
- Concurrent MCP sessions: **100 per deployment**

---

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AI executes destructive commands | Medium | High | Policy guard + mandatory confirmation for HIGH risk |
| Credential leakage | Low | Critical | Kubernetes secret encryption, no credential logging |
| Broker overload from MCP | Low | High | Rate limiting, circuit breaker |
| Long-running scale operations | High | Medium | Async operation model, tracking IDs |
| OCI Streaming API changes | Low | Medium | Adapter pattern, version pinning |
| MCP specification changes | Low | Medium | Use official SDK, follow spec updates |

---

## 12. Development Environment Setup

### Prerequisites
- Python 3.11+
- Java 17+ and Kafka via Homebrew (for local Kafka — no Docker required)
- `pip` or `uv` package manager
- Access to OCI tenancy (for integration testing)
- `kubectl` + `helm` (for Kubernetes deployment)

### Local Kafka Setup (Homebrew — No Docker)

```bash
# Install Java and Kafka via Homebrew
brew install openjdk@17
brew install kafka

# One-time: generate cluster ID and format storage
KAFKA_CLUSTER_ID="$(kafka-storage random-uuid)"
kafka-storage format --standalone \
  -t "$KAFKA_CLUSTER_ID" \
  -c /opt/homebrew/etc/kafka/server.properties

# Start Kafka (runs on localhost:9092, KRaft mode)
kafka-server-start /opt/homebrew/etc/kafka/server.properties

# Verify (in another terminal)
kafka-topics --create --topic mcp-test --partitions 3 --bootstrap-server localhost:9092

# Stop when done
kafka-server-stop
```

Alternative: If Podman is available, use `podman-compose -f docker/docker-compose.yaml up -d`.

### Quick Start

```bash
# Clone the repo
cd /path/to/oci-kafka-mcp-server

# Create venv and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the MCP server (STDIO mode)
.venv/bin/oci-kafka-mcp

# Run tests (no Kafka broker needed — tests use mocks)
.venv/bin/pytest

# Run tests with coverage
.venv/bin/pytest --cov=oci_kafka_mcp
```

---

## 13. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-02-25 | Initial project plan created | Abhishek + Claude |
| 2026-02-25 | Sprint 0 + 1 complete: 14 tools, 41 tests | Abhishek + Claude |
| 2026-02-25 | Sprint 2 complete: write tools, cluster lifecycle (57 tests) | Abhishek + Claude |
| 2026-02-26 | Sprint 3 complete: AI diagnostics, docs, CI/CD (68 tests) | Abhishek + Claude |
