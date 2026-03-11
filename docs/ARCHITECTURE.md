# OCI Kafka MCP Server — Security Architecture Document

> **Document Type:** Security Architecture Review (SEC ARC)
> **Service:** OCI Streaming with Apache Kafka — MCP Server
> **Version:** 0.1.0
> **Author:** Abhishek (PM/Architect/Engineer)
> **Date:** 2026-02-26
> **Classification:** Internal — OCI Engineering

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Architecture](#3-architecture)
4. [Data Flow](#4-data-flow)
5. [Authentication and Authorization](#5-authentication-and-authorization)
6. [Network Security](#6-network-security)
7. [Third-Party Dependencies](#7-third-party-dependencies)
8. [Security Controls](#8-security-controls)
9. [Threat Model](#9-threat-model)
10. [Audit and Compliance](#10-audit-and-compliance)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Open Source Attribution](#12-open-source-attribution)

---

## 1. Executive Summary

The OCI Kafka MCP Server is a customer-deployed component that provides an AI-native control plane for OCI Streaming with Apache Kafka clusters. It implements the open-source **Model Context Protocol (MCP)** specification to enable LLM agents (Claude, GPT, etc.) to execute structured operations against Kafka clusters.

The server is a **stateless Python process** that translates MCP tool calls into Kafka Admin API operations over authenticated, encrypted connections. It does not store data, does not accept inbound network connections (STDIO transport), and operates with the principle of least privilege.

**Key Security Properties:**
- Read-only by default; write operations require explicit opt-in
- All destructive operations require confirmation
- Every tool execution is audit-logged as structured JSON
- All Kafka connections use SASL/SCRAM-SHA-512 + TLS 1.2+
- Circuit breaker prevents cascading failures
- No secrets stored in code; all credentials via environment variables

---

## 2. System Overview

### 2.1 What It Does

The MCP server exposes 20 structured tools that perform Kafka cluster administration operations:

| Category | Tools | Risk Level |
|----------|-------|------------|
| **Cluster Read** | get_cluster_health, get_cluster_config | LOW |
| **Topic Read** | list_topics, describe_topic | LOW |
| **Topic Write** | create_topic, update_topic_config | MEDIUM |
| **Topic Delete** | delete_topic | HIGH |
| **Consumer Read** | list_consumer_groups, describe_consumer_group, get_consumer_lag | LOW |
| **Consumer Write** | reset_consumer_offset, delete_consumer_group | HIGH |
| **Observability** | get_partition_skew, detect_under_replicated_partitions | LOW |
| **AI Diagnostics** | recommend_scaling, analyze_lag_root_cause | LOW |
| **OCI Metadata** | get_oci_cluster_info, list_oci_clusters | LOW |
| **Cluster Lifecycle** | create_cluster, scale_cluster | HIGH |

### 2.2 What It Does NOT Do

- Does not produce or consume Kafka messages (data plane)
- Does not store any state, credentials, or session data
- Does not expose any network listeners (STDIO-only transport)
- Does not have access to message payloads or customer data
- Does not modify Kafka ACLs or security configurations
- Does not manage OCI IAM policies or users

---

## 3. Architecture

### 3.1 Component Architecture

```
+-------------------+         STDIO (JSON-RPC)        +---------------------+
|                   | <------------------------------> |                     |
|   MCP Client      |   stdin/stdout (no network)     |  OCI Kafka MCP      |
|   (Claude Desktop |                                  |  Server             |
|    or other)      |                                  |                     |
+-------------------+                                  +----------+----------+
                                                                  |
                                                    +-------------+-------------+
                                                    |             |             |
                                               +----+----+  +----+----+  +----+----+
                                               | Policy  |  | Circuit |  | Audit   |
                                               | Guard   |  | Breaker |  | Logger  |
                                               +---------+  +---------+  +---------+
                                                    |
                                          +---------+---------+
                                          |                   |
                                    +-----+------+     +-----+------+
                                    | Kafka      |     | OCI SDK    |
                                    | AdminClient|     | (Optional) |
                                    +-----+------+     +-----+------+
                                          |                   |
                                   SASL_SSL/TLS          HTTPS/TLS
                                          |                   |
                                    +-----+------+     +-----+------+
                                    | OCI Kafka  |     | OCI Control|
                                    | Brokers    |     | Plane API  |
                                    +------------+     +------------+
```

### 3.2 Module Structure

```
src/oci_kafka_mcp/
├── server.py                 # Entry point, CLI, tool registration
├── config.py                 # Configuration from environment variables
├── tools/                    # MCP tool implementations
│   ├── cluster.py            # Cluster health and config (2 tools)
│   ├── cluster_management.py # OCI API: create/scale cluster (2 tools)
│   ├── topics.py             # Topic CRUD (5 tools)
│   ├── consumers.py          # Consumer group operations (5 tools)
│   ├── observability.py      # Partition skew, replication health (2 tools)
│   ├── diagnostics.py        # AI-powered scaling and lag analysis (2 tools)
│   └── oci_metadata.py       # OCI control plane metadata (2 tools)
├── kafka/                    # Kafka protocol layer
│   ├── admin_client.py       # confluent-kafka AdminClient wrapper
│   ├── consumer_client.py    # Consumer group operations wrapper
│   └── connection.py         # Circuit breaker state machine
├── security/                 # Security controls
│   ├── policy_guard.py       # Risk classification and write protection
│   └── auth.py               # SASL/SSL configuration validation
├── audit/
│   └── logger.py             # Structured JSON audit logging
└── oci/
    └── streaming_client.py   # OCI SDK wrapper (cluster lifecycle)
```

### 3.3 Key Design Principles

1. **Stateless** — No persistent state, sessions, or caches. Each tool call is independent.
2. **No inbound network** — STDIO transport only. The server never opens a listening socket.
3. **Fail-safe defaults** — Read-only mode by default. All destructive operations gated.
4. **Defense in depth** — Policy guard + circuit breaker + audit logging on every operation.
5. **Secrets externalized** — All credentials passed via environment variables, never in code.

---

## 4. Data Flow

### 4.1 Tool Execution Flow

```
MCP Client (LLM Agent)
  │
  │  JSON-RPC request via STDIO
  ▼
Server (server.py)
  │
  │  Route to registered tool function
  ▼
Policy Guard (policy_guard.py)
  │
  ├─ Is this a write tool AND writes disabled? → DENY
  ├─ Is this HIGH risk? → REQUIRE CONFIRMATION
  └─ Pass
  │
  ▼
Circuit Breaker (connection.py)
  │
  ├─ Circuit OPEN? → FAST FAIL (prevent cascading)
  └─ Circuit CLOSED or HALF_OPEN? → Allow
  │
  ▼
Audit Logger START (logger.py)
  │
  ▼
Kafka AdminClient (admin_client.py / consumer_client.py)
  │
  │  Kafka protocol over SASL_SSL + TLS 1.2+
  ▼
OCI Kafka Brokers (private endpoint)
  │
  │  Response
  ▼
Audit Logger END → emit structured JSON log
  │
  ▼
JSON response returned via STDIO
```

### 4.2 Data Classification

| Data Type | Classification | Storage | Encryption |
|-----------|---------------|---------|------------|
| Kafka cluster metadata (broker list, topic names, partition info) | Internal | In-memory only (not persisted) | TLS in transit |
| Consumer group offsets | Internal | In-memory only | TLS in transit |
| SASL credentials | Secret | Environment variables only | Not at rest (env var) |
| TLS certificates | Secret | Filesystem (PEM files) | N/A |
| Audit log entries | Internal | STDERR output stream | Depends on log sink |
| Kafka message payloads | N/A | **Never accessed** | N/A |

### 4.3 What Data the Server Can Access

- Kafka cluster metadata: broker list, IDs, controller info
- Topic names, partition counts, replication details, configuration
- Consumer group IDs, member assignments, committed offsets, lag
- Broker configuration settings (non-sensitive keys/values)

### 4.4 What Data the Server CANNOT Access

- Kafka message payloads (the server never calls produce/consume)
- OCI IAM policies, user credentials, or identity tokens
- Other OCI service resources outside the Kafka cluster
- Data in other Kafka clusters not configured in the connection

---

## 5. Authentication and Authorization

### 5.1 Kafka Authentication

The server authenticates to OCI Kafka brokers using **SASL/SCRAM-SHA-512** over TLS:

```
Protocol:     SASL_SSL
Mechanism:    SCRAM-SHA-512
TLS Version:  1.2+ (enforced by OCI Kafka service)
CA Cert:      Publicly-trusted CA (certifi bundle or system CA)
```

**Configuration validation** (`auth.py`) enforces:
- SASL protocols require: mechanism, username, password
- SSL protocols require: CA certificate location
- mTLS requires: both client certificate and key (mutual dependency)

Invalid configurations are rejected at startup with descriptive error messages.

### 5.2 OCI API Authentication (Cluster Lifecycle Tools)

The `create_cluster` and `scale_cluster` tools use the **OCI Python SDK** which authenticates via:
- OCI API key authentication (`~/.oci/config`)
- Instance principal (when running on OCI compute)
- Resource principal (when running on OKE)

These tools are gated behind `--allow-writes` AND require HIGH risk confirmation.

### 5.3 MCP Client Authentication

The MCP protocol (STDIO transport) does not include its own authentication layer. Security relies on:
- **Process-level isolation** — The MCP server runs as a child process of the MCP client
- **OS-level access control** — Only the parent process can communicate via STDIO
- **No network exposure** — No listening sockets; no remote access possible

### 5.4 Credential Management

| Credential | How Provided | Where Stored |
|-----------|-------------|-------------|
| SASL username | `KAFKA_SASL_USERNAME` env var | Process environment |
| SASL password | `KAFKA_SASL_PASSWORD` env var | Process environment |
| CA certificate | `KAFKA_SSL_CA_LOCATION` filesystem path | PEM file on disk |
| Client cert (mTLS) | `KAFKA_SSL_CERT_LOCATION` filesystem path | PEM file on disk |
| Client key (mTLS) | `KAFKA_SSL_KEY_LOCATION` filesystem path | PEM file on disk |
| OCI API key | `~/.oci/config` | OCI config file |

**Security controls:**
- No credentials are hardcoded in source code
- `.env.oci` (containing credentials) is listed in `.gitignore`
- The `.env.oci.example` template contains placeholder values only
- Credentials are never logged (audit logger hashes inputs with SHA-256)

---

## 6. Network Security

### 6.1 Network Architecture

```
+-----------------+     STDIO      +------------------+     SSH Tunnel     +------------------+
| MCP Client      | <-----------> | OCI Kafka MCP    | <===============> | OCI Compute      |
| (Local process) |  (no network) | Server (Local)   |  (Encrypted)     | (Bastion)        |
+-----------------+               +------------------+                   +--------+---------+
                                                                                  |
                                                                          Private VCN
                                                                                  |
                                                                         +--------+---------+
                                                                         | OCI Kafka        |
                                                                         | Brokers          |
                                                                         | (Private only)   |
                                                                         +------------------+
```

### 6.2 Connection Security

| Connection | Protocol | Encryption | Authentication |
|-----------|----------|------------|----------------|
| MCP Client ↔ MCP Server | STDIO (pipes) | N/A (local process) | Process isolation |
| MCP Server ↔ SSH Bastion | SSH | AES-256 (SSH) | Public key |
| SSH Bastion ↔ Kafka Brokers | Kafka protocol | TLS 1.2+ | SASL/SCRAM-SHA-512 |
| MCP Server ↔ OCI API | HTTPS | TLS 1.2+ | OCI API key signing |

### 6.3 Network Exposure

The MCP server has **zero network exposure**:
- No listening sockets (STDIO transport only)
- No HTTP/HTTPS endpoints
- No WebSocket listeners
- Cannot be reached from any network

The only outbound connections are:
1. Kafka protocol to OCI Kafka brokers (port 9092, via SSH tunnel or direct VCN)
2. HTTPS to OCI API endpoints (for cluster lifecycle tools)

### 6.4 Private Endpoint Connectivity

OCI Streaming with Apache Kafka clusters are deployed with **private-only** endpoints:
- Brokers are accessible only within the OCI VCN
- No public IP addresses assigned to brokers
- DNS resolution via OCI private DNS zones
- Access from outside OCI requires SSH tunneling through a bastion host

---

## 7. Third-Party Dependencies

### 7.1 Runtime Dependencies

| Package | Version | License | Publisher | Purpose | Security Notes |
|---------|---------|---------|-----------|---------|----------------|
| **mcp** | >=1.0.0 | MIT | Anthropic (Model Context Protocol) | MCP server framework (FastMCP), JSON-RPC, STDIO transport | Open standard protocol; no data collection; client-side only |
| **confluent-kafka** | >=2.6.0 | Apache 2.0 | Confluent Inc. | Python wrapper for librdkafka; Kafka Admin API client | Industry-standard Kafka client; wraps librdkafka (BSD 2-Clause); used by AWS, Azure, and major Kafka deployments |
| **librdkafka** (transitive) | (bundled) | BSD 2-Clause | Magnus Edenhill / Confluent | C library for Kafka protocol | Fully permissive license; no network telemetry; FIPS-capable TLS via OpenSSL |
| **oci** | >=2.130.0 | UPL 1.0 + Apache 2.0 | Oracle Corporation | Official OCI Python SDK | Oracle's own SDK; used for cluster lifecycle (create/scale) |
| **pydantic** | >=2.0.0 | MIT | Samuel Colvin | Data validation and settings management | Pure Python; no network access; widely used in OCI services |
| **pydantic-settings** | >=2.0.0 | MIT | Samuel Colvin | Environment variable loading | Extension of pydantic for config management |
| **certifi** (transitive) | (bundled) | MPL 2.0 | Kenneth Reitz | Mozilla CA certificate bundle | Provides trusted root CAs for TLS verification |

### 7.2 Development Dependencies (NOT shipped)

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| pytest | >=8.0.0 | MIT | Unit testing framework |
| pytest-asyncio | >=0.24.0 | Apache 2.0 | Async test support |
| pytest-cov | >=5.0.0 | MIT | Code coverage |
| ruff | >=0.8.0 | MIT | Python linter and formatter |
| mypy | >=1.11.0 | MIT | Static type checker |

### 7.3 Dependency Risk Assessment

| Dependency | Risk | Mitigation |
|-----------|------|------------|
| **confluent-kafka** — Published by Confluent (competitor) | **Low.** BSD/Apache license; no proprietary lock-in; uses standard Kafka protocol. | Can be replaced with `aiokafka` (Apache 2.0) or `kafka-python-ng` (Apache 2.0) if required by OSRB. See Section 7.4. |
| **librdkafka** — C native code with potential memory safety issues | **Low.** Mature library (10+ years), extensive fuzzing, used in production by thousands of organizations. | Pin to known-good version; monitor CVE database. |
| **mcp** — Relatively new protocol/SDK | **Low.** MIT license; maintained by Anthropic; client-side only with no network telemetry. | Monitor for breaking changes; pin to stable versions. |
| **Supply chain attack on any dependency** | **Medium.** Standard risk for any Python project. | Use `uv.lock` for reproducible builds; verify package checksums; consider vendoring critical dependencies. |

### 7.4 Alternative Kafka Clients (If Required by OSRB)

If the Open Source Review Board requires removing the Confluent dependency:

| Alternative | License | Trade-offs |
|-------------|---------|------------|
| **aiokafka** | Apache 2.0 | Pure Python, async-native, no Confluent branding. Less mature admin API. |
| **kafka-python-ng** | Apache 2.0 | Pure Python, active community fork. Slower than librdkafka. |
| **Direct Kafka protocol** | N/A | Maximum control, zero external dependency. Significant engineering effort. |

The server's Kafka layer is isolated in `kafka/admin_client.py` and `kafka/consumer_client.py`. Replacing the client library requires changes to these two files only — no changes to tools, policy guard, or audit logging.

---

## 8. Security Controls

### 8.1 Read/Write Mode Separation

The server starts in **read-only mode** by default:

```python
# Default: read-only
.venv/bin/oci-kafka-mcp

# Explicit opt-in for write operations
.venv/bin/oci-kafka-mcp --allow-writes
```

When read-only:
- All read tools (health, list, describe, observe) work normally
- All write tools return: `"Write tool 'X' is disabled. Start the server with --allow-writes to enable write operations."`

### 8.2 Risk Classification (Policy Guard)

Every tool is classified into a risk level:

| Risk Level | Behavior | Examples |
|-----------|----------|---------|
| **LOW** | Execute immediately | get_cluster_health, list_topics, get_consumer_lag |
| **MEDIUM** | Require `--allow-writes` | create_topic, update_topic_config |
| **HIGH** | Require `--allow-writes` AND return confirmation prompt before execution | delete_topic, reset_consumer_offset, delete_consumer_group, create_cluster, scale_cluster |

The policy guard is implemented as a pure-function check that runs **before** any Kafka API call. It cannot be bypassed by the MCP client.

### 8.3 Circuit Breaker

Prevents cascading failures when Kafka is unavailable:

| State | Behavior | Transition |
|-------|----------|------------|
| **CLOSED** | All requests pass through | → OPEN after 5 consecutive failures |
| **OPEN** | All requests fast-fail with error | → HALF_OPEN after 30 second cooldown |
| **HALF_OPEN** | One test request allowed | → CLOSED on success, → OPEN on failure |

Parameters: `failure_threshold=5`, `cooldown_seconds=30`

### 8.4 Audit Logging

Every tool execution generates a structured JSON audit entry:

```json
{
  "audit": true,
  "timestamp": "2026-02-26T22:30:15.123456+00:00",
  "toolName": "oci_kafka_create_topic",
  "inputHash": "a3f2b1c4e5d67890",
  "resultStatus": "success",
  "executionTimeMs": 245.67
}
```

**Audit properties:**
- Emitted on STDERR as structured JSON (compatible with OCI Logging, Fluentd, CloudWatch)
- Input parameters are **hashed** (SHA-256, first 16 chars) — not logged in plaintext
- Timing measured with monotonic clock for accuracy
- Error messages captured on failure
- Every tool call is logged regardless of success/failure
- Logging cannot be disabled by the MCP client

### 8.5 Input Validation

- **Pydantic models** validate all configuration at startup
- **Auth validation** checks SASL/SSL configuration consistency before any connection
- **Tool parameters** validated by FastMCP's type system (Python type hints enforced by MCP SDK)
- **No raw SQL, shell commands, or eval** — all operations use typed Kafka API calls

### 8.6 Secret Protection

- Credentials passed exclusively via environment variables
- `.env.oci` (containing secrets) is in `.gitignore` — never committed
- Audit logger hashes input parameters — secrets in tool params are never logged in plaintext
- No debug mode that dumps credentials
- No credential caching or persistence

---

## 9. Threat Model

### 9.1 Trust Boundaries

```
+-----------------------------------------------+
|  Trust Zone 1: User's Machine                  |
|                                                 |
|  +------------------+   +-------------------+   |
|  | MCP Client       |   | OCI Kafka MCP     |   |
|  | (Claude Desktop) |<->| Server            |   |
|  +------------------+   +-------------------+   |
|                              |                   |
+------------------------------+-------------------+
                               | SSH Tunnel (encrypted)
+------------------------------+-------------------+
|  Trust Zone 2: OCI VCN (Private)                 |
|                                                   |
|  +------------------+   +--------------------+    |
|  | Compute Bastion  |   | OCI Kafka Brokers  |    |
|  | (SSH endpoint)   |-->| (Private endpoint) |    |
|  +------------------+   +--------------------+    |
|                                                   |
+---------------------------------------------------+
```

### 9.2 Threats and Mitigations

| # | Threat | Severity | Mitigation |
|---|--------|----------|------------|
| T1 | **Malicious MCP client sends destructive tool calls** | High | Policy guard blocks writes by default; HIGH risk ops require confirmation; audit log captures all actions |
| T2 | **Credential leakage via audit logs** | Medium | Input params are SHA-256 hashed, not logged in plaintext; no debug dump mode |
| T3 | **Man-in-the-middle on Kafka connection** | High | TLS 1.2+ enforced; CA certificate verification required; SASL/SCRAM challenge-response prevents replay |
| T4 | **SSH tunnel compromise** | Medium | SSH uses public key authentication; tunnel is encrypted; Kafka adds SASL/TLS as second layer |
| T5 | **Credential theft from environment variables** | Medium | Standard OS process isolation; environment not logged; `.env.oci` in .gitignore |
| T6 | **Denial of service via rapid tool calls** | Low | Circuit breaker prevents cascading failures; Kafka AdminClient has built-in timeouts (10 seconds) |
| T7 | **Supply chain attack via compromised dependency** | Medium | Pin dependency versions in `uv.lock`; use `uv sync` for reproducible installs; monitor CVE databases |
| T8 | **Privilege escalation via OCI SDK** | Low | OCI API calls use the configured API key's IAM permissions; no privilege escalation possible beyond the key's policy |
| T9 | **Data exfiltration via Kafka metadata** | Low | Server only accesses metadata (topic names, offsets); never reads message payloads; no outbound network besides Kafka and OCI API |
| T10 | **LLM prompt injection to bypass safety** | Medium | Policy guard is code-level enforcement (not prompt-based); cannot be overridden by LLM instructions; the server executes tool calls, not arbitrary instructions |

### 9.3 OWASP Considerations

| OWASP Category | Applicability | Status |
|---------------|---------------|--------|
| Injection | No SQL, no shell exec, no eval | **Not applicable** |
| Broken Authentication | SASL/SCRAM + TLS enforced | **Mitigated** |
| Sensitive Data Exposure | Credentials in env vars, hashed in logs | **Mitigated** |
| XXE | No XML processing | **Not applicable** |
| Broken Access Control | Policy guard + read/write separation | **Mitigated** |
| Security Misconfiguration | Auth validation at startup | **Mitigated** |
| XSS | No web interface | **Not applicable** |
| Insecure Deserialization | JSON only (standard lib), no pickle/yaml | **Not applicable** |
| Insufficient Logging | Every tool call audit-logged | **Mitigated** |
| SSRF | No URL/HTTP input accepted from clients | **Not applicable** |

---

## 10. Audit and Compliance

### 10.1 Audit Trail

The audit logger produces a complete trail of every operation:

- **What** was executed (tool name)
- **When** it was executed (ISO 8601 UTC timestamp)
- **What inputs** were provided (SHA-256 hash for traceability without exposure)
- **How long** it took (millisecond-precision execution time)
- **What happened** (success, error, or confirmation_required)
- **Error details** if the operation failed

### 10.2 Log Format Compatibility

Audit logs are emitted as structured JSON on STDERR, compatible with:
- OCI Logging Service (via Fluentd/Unified Monitoring Agent)
- Splunk
- Elastic/OpenSearch
- CloudWatch Logs
- Any JSON-capable log aggregator

### 10.3 Non-Repudiation

Since the MCP server runs as a subprocess of the MCP client (Claude Desktop), the tool execution chain is:
1. User sends natural language prompt to LLM
2. LLM decides which tool to call (visible in Claude Desktop UI)
3. MCP server executes the tool and logs the audit entry
4. Result returned to LLM and displayed to user

The user can see every tool call in the Claude Desktop interface before and after execution.

---

## 11. Deployment Architecture

### 11.1 Phase 1: Customer-Deployed (Current)

```
Customer's Machine
├── Claude Desktop (MCP client)
└── OCI Kafka MCP Server (child process)
    └── Connects to OCI Kafka via SSH tunnel
```

- Customer installs and runs the server locally
- Customer provides their own Kafka credentials
- Customer controls read/write mode

### 11.2 Phase 2: Helm Chart on OKE (Planned)

```
OKE Cluster (Customer's VCN)
├── OCI Kafka MCP Server Pod
│   ├── STDIO sidecar (MCP transport)
│   ├── Direct VCN connectivity to Kafka (no SSH tunnel needed)
│   └── OCI Instance Principal for authentication
└── Kubernetes Secrets (SASL credentials, TLS certs)
```

- Deployed via Helm chart into customer's OKE cluster
- Direct private networking within VCN (no SSH tunnel)
- Credentials managed via Kubernetes Secrets and OCI Vault
- Network policies restrict egress to Kafka brokers only

### 11.3 Multi-Cluster Support (Future Roadmap)

The current architecture follows a **single-cluster model**: one MCP server instance connects to one Kafka cluster via `KAFKA_BOOTSTRAP_SERVERS`. All Kafka protocol tools (health, topics, consumers, observability, diagnostics) operate against that single cluster. The OCI control plane tools (`get_oci_cluster_info`, `list_oci_clusters`) already support multi-cluster by accepting any cluster/compartment OCID as a parameter.

**Current workaround:** Run multiple MCP server instances, each configured with a different cluster's bootstrap URL and credentials.

**Planned approaches for native multi-cluster support:**

1. **Dynamic connection switching** — Accept a `cluster_id` parameter on Kafka protocol tools; create per-request `KafkaAdminClient` connections with a connection pool and per-cluster circuit breakers.
2. **OCI-native bootstrap discovery** — Use the OCI control plane to resolve a cluster OCID to its bootstrap URL, then connect dynamically. This aligns with the sidecar deployment model where the server runs alongside OCI Streaming.
3. **Cross-cluster comparison** — A new tool that compares health, topic sets, and consumer lag across multiple clusters in a single response.

### 11.4 Phase 3: OCI-Managed Service (Future)

- Fully managed by OCI Streaming team
- Multi-tenant architecture with resource isolation
- OCI IAM integration for authentication
- OCI Audit Service integration for compliance

---

## 12. Open Source Attribution

### 12.1 Licenses Used

| License | Packages | Commercial Use | Copyleft |
|---------|----------|---------------|----------|
| **Apache 2.0** | confluent-kafka, oci, pytest-asyncio | Yes | No |
| **BSD 2-Clause** | librdkafka | Yes | No |
| **MIT** | mcp, pydantic, pydantic-settings, pytest, ruff, mypy, pytest-cov | Yes | No |
| **MPL 2.0** | certifi | Yes | File-level only |
| **UPL 1.0** | oci (dual-licensed) | Yes | No |

All licenses are **permissive** and allow commercial use, modification, and distribution. No copyleft (GPL/AGPL) dependencies exist.

### 12.2 Code Provenance

| Component | Origin | License |
|-----------|--------|---------|
| All code in `src/oci_kafka_mcp/` | **Original — written from scratch** | Apache 2.0 (project license) |
| All code in `tests/` | **Original — written from scratch** | Apache 2.0 (project license) |
| Docker/Helm configurations | **Original** | Apache 2.0 |
| Architecture patterns (tool modules, policy guard, circuit breaker) | **Inspired by** open-source MCP servers (listed below); no code copied | N/A |

### 12.3 Architectural References (Design Inspiration Only)

The following open-source projects were studied for architectural patterns. **No source code was copied or derived from any of them.**

| Project | What We Studied | URL |
|---------|----------------|-----|
| confluentinc/mcp-confluent | Modular tool handler pattern, tool naming conventions | github.com/confluentinc/mcp-confluent |
| awslabs/mcp (MSK) | Read/write mode separation, operational recommendations | github.com/awslabs/mcp |
| tuannvm/kafka-mcp-server | SASL/SCRAM + mTLS configuration patterns | github.com/tuannvm/kafka-mcp-server |
| oracle/mcp | OCI SDK authentication patterns, distribution model | github.com/oracle/mcp |

---

## Appendix A: Configuration Reference

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | `localhost:9092` | Comma-separated broker addresses |
| `KAFKA_SECURITY_PROTOCOL` | No | `PLAINTEXT` | `PLAINTEXT`, `SSL`, `SASL_PLAINTEXT`, `SASL_SSL` |
| `KAFKA_SASL_MECHANISM` | When SASL | — | `SCRAM-SHA-512`, `SCRAM-SHA-256`, `PLAIN` |
| `KAFKA_SASL_USERNAME` | When SASL | — | SASL authentication username |
| `KAFKA_SASL_PASSWORD` | When SASL | — | SASL authentication password |
| `KAFKA_SSL_CA_LOCATION` | When SSL/SASL_SSL | — | Path to CA certificate PEM file |
| `KAFKA_SSL_CERT_LOCATION` | When mTLS | — | Path to client certificate PEM file |
| `KAFKA_SSL_KEY_LOCATION` | When mTLS | — | Path to client private key PEM file |
| `OCI_CONFIG_FILE` | No | `~/.oci/config` | OCI SDK configuration file path |
| `OCI_PROFILE` | No | `DEFAULT` | OCI config profile name |
| `OCI_COMPARTMENT_ID` | No | Tenancy OCID from `~/.oci/config` | OCI compartment OCID (auto-discovered if not set) |
| `OCI_CLUSTER_ID` | No | — | OCI Kafka cluster (stream pool) OCID (LLM prompted to ask user if not set) |

## Appendix B: Tool Risk Registry

| Tool Name | Risk | Write | Confirm | Description |
|-----------|------|-------|---------|-------------|
| `oci_kafka_get_cluster_health` | LOW | No | No | Broker status, controller, topic count |
| `oci_kafka_get_cluster_config` | LOW | No | No | Cluster configuration settings |
| `oci_kafka_list_topics` | LOW | No | No | List all topics |
| `oci_kafka_describe_topic` | LOW | No | No | Topic details, partitions, config |
| `oci_kafka_create_topic` | MEDIUM | Yes | No | Create a new topic |
| `oci_kafka_update_topic_config` | MEDIUM | Yes | No | Update topic configuration |
| `oci_kafka_delete_topic` | HIGH | Yes | Yes | Delete a topic (destructive) |
| `oci_kafka_list_consumer_groups` | LOW | No | No | List consumer groups |
| `oci_kafka_describe_consumer_group` | LOW | No | No | Consumer group details |
| `oci_kafka_get_consumer_lag` | LOW | No | No | Per-partition lag metrics |
| `oci_kafka_reset_consumer_offset` | HIGH | Yes | Yes | Reset offsets (destructive) |
| `oci_kafka_delete_consumer_group` | HIGH | Yes | Yes | Delete consumer group (destructive) |
| `oci_kafka_get_partition_skew` | LOW | No | No | Detect partition imbalance |
| `oci_kafka_detect_under_replicated_partitions` | LOW | No | No | ISR health check |
| `oci_kafka_recommend_scaling` | LOW | No | No | AI-powered scaling recommendations |
| `oci_kafka_analyze_lag_root_cause` | LOW | No | No | AI-powered lag root cause analysis |
| `oci_kafka_get_oci_cluster_info` | LOW | No | No | OCI cluster metadata (OCID, name, state) |
| `oci_kafka_list_oci_clusters` | LOW | No | No | List clusters in OCI compartment |
| `oci_kafka_create_cluster` | HIGH | Yes | Yes | Create OCI Kafka cluster |
| `oci_kafka_scale_cluster` | HIGH | Yes | Yes | Scale broker count |
