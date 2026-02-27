# OCI Kafka MCP Server — Demo Runbook

## The Elevator Pitch

Today, managing Apache Kafka in the cloud means switching between multiple consoles, CLIs, and dashboards just to answer basic questions: Is my cluster healthy? Are my consumers falling behind? Which topics have partition skew? Operators spend more time navigating tools than solving problems.

The OCI Kafka MCP Server changes this by introducing an **AI-native control plane** for OCI Streaming with Apache Kafka. Built on the open-source **Model Context Protocol (MCP)** specification, it connects LLM agents like Claude directly to a live Kafka cluster through 14 structured tools — turning natural language into real-time cluster operations. Instead of running CLI commands or clicking through dashboards, you simply ask: *"Is my cluster healthy?"* or *"Create a topic called payment-events with 6 partitions"* — and the AI agent executes the operation securely against your real infrastructure.

This is not a chatbot with pre-baked answers. Every response comes from live data — the AI agent calls Kafka Admin APIs in real time, interprets the results, and presents actionable insights. It can create topics, detect partition imbalance, check replication health, and monitor consumer lag — all through a conversational interface. And it does this with enterprise-grade safety: **read-only by default**, a **policy guard** that classifies every operation by risk level (LOW/MEDIUM/HIGH), a **circuit breaker** that prevents cascading failures, and **structured audit logging** of every action.

The architecture is intentionally simple and composable. The MCP server runs as a lightweight Python process that speaks JSON-RPC over STDIO. It connects to Kafka via the production-grade `confluent-kafka` client library with full SASL/SCRAM-SHA-512 authentication and TLS encryption. Because it implements the open MCP standard, it works with any MCP-compatible client — Claude Desktop today, but tomorrow it could plug into VS Code, custom ops dashboards, or automated runbooks. This is what the future of cloud infrastructure management looks like: AI agents that don't just monitor your systems, but help you operate them.

---

## Pre-Demo Requirements

You should already have:
- An **OCI Streaming with Apache Kafka cluster** (ACTIVE state) — note the bootstrap URL, SASL username, and SASL password
- A **compute instance** (Oracle Linux 9) in the **same VCN** as the Kafka cluster, with a public IP for SSH access
- The **SSH private key** for the compute instance on your Mac

The MCP server code, Python environment, and Claude Desktop are already set up on your Mac from previous work.

---

## Configuration Steps

### Step 1: Collect Cluster Details

From the OCI Console, gather these values from your new Kafka cluster:

| Detail | Where to Find | Example |
|--------|---------------|---------|
| Bootstrap URL | Cluster Details page | `bootstrap-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com` |
| SASL Username | Cluster Details or Vault | `super-user-XXXXX` |
| SASL Password | Cluster Details or Vault | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| Compute Public IP | Compute Instance Details | `147.224.xxx.xxx` |

### Step 2: Verify Compute-to-Kafka Connectivity

SSH into the compute instance and confirm DNS + network connectivity:

```bash
ssh -i /path/to/your-key opc@<COMPUTE_PUBLIC_IP>

# Verify DNS resolves (should return a private IP)
dig <BOOTSTRAP_URL>

# Verify port is reachable
nc -zv <BOOTSTRAP_URL> 9092
```

If `dig` returns NXDOMAIN: go to OCI Console > Networking > DNS Management > Private DNS Zones, find the Kafka zone, and associate it with your VCN.

If `nc` is missing: `sudo dnf install -y nmap-ncat`

Exit the compute SSH session once verified.

### Step 3: Discover Broker Hostnames

From your Mac, set up a temporary bootstrap-only tunnel to discover all broker hostnames:

```bash
ssh -i /path/to/your-key -N -f \
    -L 127.0.0.1:9092:<BOOTSTRAP_URL>:9092 \
    opc@<COMPUTE_PUBLIC_IP>
```

Run the discovery script (update .env.oci first — see Step 4):

```bash
cd /Users/abhishek/Projects/01-KafkaMCP
source .env.oci
.venv/bin/python -c "
from oci_kafka_mcp.config import KafkaConfig
from oci_kafka_mcp.kafka.admin_client import KafkaAdminClient
client = KafkaAdminClient(KafkaConfig())
health = client.get_cluster_health()
print('Broker hostnames (add these to /etc/hosts):')
for b in health['brokers']:
    print(f\"  {b['host']}\")
"
```

Kill the temporary tunnel:

```bash
lsof -ti :9092 | xargs kill -9
```

### Step 4: Update .env.oci

Edit `/Users/abhishek/Projects/01-KafkaMCP/.env.oci` with your new cluster details:

```bash
# Bootstrap servers (resolves to 127.0.0.1 via /etc/hosts for SSH tunnel)
export KAFKA_BOOTSTRAP_SERVERS="<BOOTSTRAP_URL>:9092"

# Security
export KAFKA_SECURITY_PROTOCOL="SASL_SSL"
export KAFKA_SASL_MECHANISM="SCRAM-SHA-512"
export KAFKA_SASL_USERNAME="<SASL_USERNAME>"
export KAFKA_SASL_PASSWORD="<SASL_PASSWORD>"

# CA certificate (does not change between clusters)
export KAFKA_SSL_CA_LOCATION="/Users/abhishek/Projects/01-KafkaMCP/.venv/lib/python3.13/site-packages/certifi/cacert.pem"
```

### Step 5: Update /etc/hosts

Remove any old OCI Kafka entries and add the new ones. Replace hostnames with those from Step 3:

```bash
# Edit hosts file
sudo vi /etc/hosts

# Add these lines (replace with your actual hostnames):
127.0.0.1 bootstrap-clstr-XXXXX.kafka.<REGION>.oci.oraclecloud.com
127.0.0.2 br0-clstr-XXXXX.kafka.<REGION>.oci.oraclecloud.com
127.0.0.3 br1-clstr-XXXXX.kafka.<REGION>.oci.oraclecloud.com
127.0.0.4 br2-clstr-XXXXX.kafka.<REGION>.oci.oraclecloud.com
```

### Step 6: Set Up Loopback Aliases and SSH Tunnel

```bash
# Loopback aliases (needed after every Mac reboot)
sudo ifconfig lo0 alias 127.0.0.2
sudo ifconfig lo0 alias 127.0.0.3
sudo ifconfig lo0 alias 127.0.0.4

# Start the full SSH tunnel (runs in background)
ssh -i /path/to/your-key -N -f \
    -L 127.0.0.1:9092:<BOOTSTRAP_URL>:9092 \
    -L 127.0.0.2:9092:<BR0_HOSTNAME>:9092 \
    -L 127.0.0.3:9092:<BR1_HOSTNAME>:9092 \
    -L 127.0.0.4:9092:<BR2_HOSTNAME>:9092 \
    opc@<COMPUTE_PUBLIC_IP>
```

### Step 7: Verify Connection

```bash
cd /Users/abhishek/Projects/01-KafkaMCP
source .env.oci
.venv/bin/python -c "
from oci_kafka_mcp.config import KafkaConfig
from oci_kafka_mcp.kafka.admin_client import KafkaAdminClient
import json
client = KafkaAdminClient(KafkaConfig())
print(json.dumps(client.get_cluster_health(), indent=2))
"
```

Expected: JSON output with `broker_count: 3` and no DNS errors.

### Step 8: Update Claude Desktop Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "oci-kafka": {
      "command": "/Users/abhishek/Projects/01-KafkaMCP/.venv/bin/oci-kafka-mcp",
      "args": ["--allow-writes"],
      "env": {
        "KAFKA_BOOTSTRAP_SERVERS": "<BOOTSTRAP_URL>:9092",
        "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
        "KAFKA_SASL_MECHANISM": "SCRAM-SHA-512",
        "KAFKA_SASL_USERNAME": "<SASL_USERNAME>",
        "KAFKA_SASL_PASSWORD": "<SASL_PASSWORD>",
        "KAFKA_SSL_CA_LOCATION": "/Users/abhishek/Projects/01-KafkaMCP/.venv/lib/python3.13/site-packages/certifi/cacert.pem"
      }
    }
  }
}
```

Restart Claude Desktop (Cmd+Q, then reopen). Look for the tools icon in the chat input area — that confirms the MCP server connected.

---

## Demo Script

### Act 1: Cluster Discovery (Read-Only)

Start with read-only operations to show the AI connecting to a live cluster.

**Prompt 1 — Cluster Health Check:**
```
Show me the health of my OCI Kafka cluster.
```
> The AI will call `oci_kafka_get_cluster_health` and display the cluster ID,
> 3 brokers with their hostnames, the controller, and topic count.
> This proves real-time connectivity to the live OCI infrastructure.

**Prompt 2 — Empty Cluster Baseline:**
```
List all topics in the cluster.
```
> Returns 0 topics on a fresh cluster. Sets the stage for the next act.

**Prompt 3 — Replication Health:**
```
Check if there are any under-replicated partitions in the cluster.
```
> The AI calls `oci_kafka_detect_under_replicated_partitions`.
> On a healthy cluster, this returns "healthy: true" with 0 under-replicated partitions.

---

### Act 2: Infrastructure as Conversation (Write Operations)

Show the AI creating and managing real infrastructure through natural language.

**Prompt 4 — Create Topics:**
```
I need to set up topics for an e-commerce platform. Please create:
1. "order-events" with 6 partitions and replication factor 3
2. "payment-transactions" with 6 partitions and replication factor 3
3. "user-activity" with 3 partitions and replication factor 3
```
> The AI calls `oci_kafka_create_topic` three times, creating real topics
> on the OCI Kafka cluster. Each call goes through the policy guard
> (MEDIUM risk — allowed with --allow-writes).

**Prompt 5 — Verify Creation:**
```
List all topics and describe the order-events topic in detail.
```
> Shows the 3 new topics, then drills into order-events showing
> all 6 partitions with their leader, replicas, and ISR details
> across all 3 brokers.

**Prompt 6 — Update Configuration:**
```
Update the order-events topic to set retention to 7 days and enable log compaction.
```
> The AI calls `oci_kafka_update_topic_config` with
> `retention.ms=604800000` and `cleanup.policy=compact`.

---

### Act 3: Operational Intelligence (Diagnostics)

Show the AI performing operational analysis that typically requires expertise.

**Prompt 7 — Partition Balance Analysis:**
```
Analyze the partition distribution across brokers. Is there any skew?
```
> The AI calls `oci_kafka_get_partition_skew`, calculates the skew ratio
> across all brokers, and provides an actionable recommendation.
> With 3 brokers and evenly partitioned topics, it should show balanced distribution.

**Prompt 8 — Comprehensive Health Assessment:**
```
Give me a complete health assessment of this cluster. Check broker status,
replication health, partition balance, and list all topics with their details.
I want a summary report suitable for an ops review.
```
> This is the showstopper. The AI orchestrates multiple tool calls:
> cluster health, under-replicated partitions, partition skew, list topics,
> and describe each topic — then synthesizes everything into a readable
> summary report. This demonstrates the power of AI-driven operations:
> what would take 5-10 CLI commands becomes a single natural language request.

---

### Act 4: Safety Guardrails (Policy Guard)

Demonstrate that the system has enterprise safety built in.

**Prompt 9 — High-Risk Operation:**
```
Delete the user-activity topic.
```
> The AI calls `oci_kafka_delete_topic` which is classified as HIGH risk.
> The policy guard returns a confirmation warning before proceeding.
> This shows that destructive operations have guardrails — the AI doesn't
> blindly execute dangerous commands.

---

### Act 5: Clean Up

**Prompt 10 — Teardown:**
```
Delete all the topics we created: order-events, payment-transactions, and user-activity.
```

---

## Key Talking Points During Demo

- **"Every response is live data"** — This isn't mock data or cached responses. Every tool call hits the real Kafka Admin API on the OCI cluster in real time.

- **"14 tools, zero CLI commands"** — The AI has access to cluster health, topic CRUD, consumer group monitoring, partition skew detection, and replication health — all through natural language.

- **"Read-only by default"** — The server starts in read-only mode. Write operations require an explicit `--allow-writes` flag. You decide what the AI can do.

- **"Risk-classified operations"** — Every tool has a risk level. LOW operations (health checks) execute freely. MEDIUM operations (create topic) require write mode. HIGH operations (delete topic) require explicit confirmation.

- **"Open standard, not vendor lock-in"** — Built on the Model Context Protocol (MCP), an open specification. Works with Claude Desktop today, but the same server works with any MCP-compatible client.

- **"Circuit breaker prevents cascading failures"** — If Kafka becomes unavailable, the circuit breaker trips and returns fast errors instead of hanging. It auto-recovers when the cluster comes back.

- **"Audit trail for every action"** — Every tool execution is logged as structured JSON with timestamp, tool name, input hash, duration, and result status. Full compliance-ready audit trail.

---

## Troubleshooting Quick Reference

| Symptom | Fix |
|---------|-----|
| `lsof -i :9092` shows nothing | SSH tunnel died — restart it (Step 6) |
| DNS errors for `brN-clstr-...` | /etc/hosts missing broker entries (Step 5) |
| `Can't assign requested address` | Loopback aliases missing — run `sudo ifconfig lo0 alias 127.0.0.X` |
| `Address already in use` | Kill old tunnel: `lsof -ti :9092 \| xargs kill -9` |
| `SSL certificate verify failed` | Certifi path wrong — run `.venv/bin/python -c "import certifi; print(certifi.where())"` |
| Claude Desktop shows no tools icon | Restart Claude Desktop; check config JSON for syntax errors |
| `NXDOMAIN` from compute instance | Private DNS zone not associated with VCN (see Step 2) |

---

## Post-Demo Teardown

```bash
# Kill SSH tunnel
lsof -ti :9092 | xargs kill -9

# Remove /etc/hosts entries
sudo vi /etc/hosts   # delete the OCI Kafka lines

# Terminate OCI resources via Console:
#   1. Streaming with Apache Kafka > Cluster > Terminate
#   2. Compute > Instance > Terminate (delete boot volume)
```
