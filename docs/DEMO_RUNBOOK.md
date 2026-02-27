# OCI Kafka MCP Server — Demo Runbook

## The Elevator Pitch

Today, managing Apache Kafka in the cloud means switching between multiple consoles, CLIs, and dashboards just to answer basic questions: Is my cluster healthy? Are my consumers falling behind? Which topics have partition skew? Operators spend more time navigating tools than solving problems.

The OCI Kafka MCP Server changes this by introducing an **AI-native control plane** for OCI Streaming with Apache Kafka. Built on the open-source **Model Context Protocol (MCP)** specification, it connects LLM agents like Claude directly to a live Kafka cluster through 18 structured tools — turning natural language into real-time cluster operations. Instead of running CLI commands or clicking through dashboards, you simply ask: *"Is my cluster healthy?"* or *"Create a topic called payment-events with 6 partitions"* — and the AI agent executes the operation securely against your real infrastructure.

This is not a chatbot with pre-baked answers. Every response comes from live data — the AI agent calls Kafka Admin APIs in real time, interprets the results, and presents actionable insights. It can create topics, detect partition imbalance, check replication health, monitor consumer lag, and even run **AI-powered diagnostics** that orchestrate multiple Kafka operations to produce scaling recommendations and lag root cause analyses — all through a conversational interface. And it does this with enterprise-grade safety: **read-only by default**, a **policy guard** that classifies every operation by risk level (LOW/MEDIUM/HIGH), a **circuit breaker** that prevents cascading failures, and **structured audit logging** of every action.

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

## Tool Inventory

The MCP server exposes **18 tools** across 6 modules. Every tool returns structured JSON that the LLM agent interprets and presents as natural language.

### Cluster Operations (2 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `oci_kafka_get_cluster_health` | LOW | Broker list, controller ID, topic count — the cluster heartbeat |
| `oci_kafka_get_cluster_config` | LOW | Cluster-wide configuration settings |

### Topic Operations (5 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `oci_kafka_list_topics` | LOW | List all topics in the cluster |
| `oci_kafka_describe_topic` | LOW | Partition details, leaders, replicas, ISR for a topic |
| `oci_kafka_create_topic` | MEDIUM | Create a topic with specified partitions and replication factor |
| `oci_kafka_update_topic_config` | MEDIUM | Change topic settings (retention, compaction, etc.) |
| `oci_kafka_delete_topic` | HIGH | Delete a topic — requires confirmation |

### Consumer Operations (5 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `oci_kafka_list_consumer_groups` | LOW | List all consumer groups |
| `oci_kafka_describe_consumer_group` | LOW | Group state, members, coordinator, assigned partitions |
| `oci_kafka_get_consumer_lag` | LOW | Per-partition lag, committed offsets, end offsets |
| `oci_kafka_reset_consumer_offset` | HIGH | Reset offsets to earliest/latest/specific — requires confirmation |
| `oci_kafka_delete_consumer_group` | HIGH | Delete a consumer group — requires confirmation |

### Observability (2 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `oci_kafka_get_partition_skew` | LOW | Detect partition imbalance across brokers (skew ratio) |
| `oci_kafka_detect_under_replicated_partitions` | LOW | Find partitions where ISR < replica count |

### AI Diagnostics (2 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `oci_kafka_recommend_scaling` | LOW | Orchestrates health + skew + replication data into scaling recommendations with severity levels |
| `oci_kafka_analyze_lag_root_cause` | LOW | Correlates consumer state, per-partition lag, topic topology into ranked root cause analysis |

### Cluster Lifecycle — OCI Control Plane (2 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `oci_kafka_create_cluster` | HIGH | Provision a new OCI Streaming with Apache Kafka cluster via OCI SDK |
| `oci_kafka_scale_cluster` | HIGH | Scale broker count for an existing cluster via OCI SDK |

**Summary:** 11 read-only (LOW risk) · 2 write (MEDIUM risk) · 5 destructive/lifecycle (HIGH risk, confirmation required)

---

## Demo Script

> **Tip:** Copy-paste the prompts below directly into Claude Desktop.
> The demo builds progressively — each act showcases a new capability layer.

### Act 1: Cluster Discovery — "Is anybody home?"

Establish that this is a live connection to real OCI infrastructure.

**Prompt 1 — Cluster Health:**
```
Show me the health of my OCI Kafka cluster.
```
> **What happens:** The AI calls `oci_kafka_get_cluster_health` and displays
> the cluster ID, 3 brokers with their hostnames and ports, the active
> controller, and total topic count — all from live Kafka Admin API calls.
>
> **Talking point:** "Every response is live data from the Kafka Admin API.
> No mock data, no caching."

**Prompt 2 — Cluster Configuration:**
```
Show me the cluster configuration and list all topics.
```
> **What happens:** The AI calls `oci_kafka_get_cluster_config` and
> `oci_kafka_list_topics` — demonstrating multi-tool orchestration in a single
> natural language request. Fresh cluster = 0 topics.
>
> **Talking point:** "The AI decides which tools to call based on your intent.
> One sentence triggered two API calls."

---

### Act 2: Infrastructure as Conversation — "Build me a platform"

Show the AI creating and managing real Kafka infrastructure through natural language.

**Prompt 3 — Create Topics:**
```
I'm building an e-commerce event streaming platform. Please create these topics:
1. "order-events" with 6 partitions and replication factor 3
2. "payment-transactions" with 6 partitions and replication factor 3
3. "inventory-updates" with 3 partitions and replication factor 3
4. "user-activity" with 3 partitions and replication factor 3
```
> **What happens:** The AI calls `oci_kafka_create_topic` four times, creating
> real topics on the live OCI cluster. Each operation passes through the
> policy guard (MEDIUM risk — allowed with `--allow-writes`).
>
> **Talking point:** "Four production-grade topics created with a single sentence.
> Each went through our policy guard — risk-classified at MEDIUM."

**Prompt 4 — Deep Inspection:**
```
List all topics, then give me the full details of order-events — I want to see
every partition, its leader broker, replicas, and in-sync replicas.
```
> **What happens:** The AI calls `oci_kafka_list_topics`, then
> `oci_kafka_describe_topic`. Shows all 6 partitions with their leader
> distribution across the 3 brokers, replica assignments, and ISR status.
>
> **Talking point:** "Full partition-level visibility. You can see how Kafka
> distributed leaders across brokers for load balancing."

**Prompt 5 — Update Configuration:**
```
Update the order-events topic: set retention to 7 days and max message size to 2MB.
Also set payment-transactions retention to 30 days since we need longer audit trails.
```
> **What happens:** The AI calls `oci_kafka_update_topic_config` twice with
> the correct Kafka config keys (`retention.ms=604800000`,
> `max.message.bytes=2097152`, `retention.ms=2592000000`).
>
> **Talking point:** "The AI translates '7 days' into the correct millisecond
> value. It knows Kafka configuration semantics."

---

### Act 3: Observability — "How healthy is my cluster?"

Show the AI performing operational analysis that typically requires Kafka expertise.

**Prompt 6 — Partition Balance:**
```
Analyze the partition distribution across all brokers. Is there any skew or imbalance?
```
> **What happens:** The AI calls `oci_kafka_get_partition_skew`. It calculates
> the skew ratio across all brokers and reports whether any broker is carrying
> a disproportionate share of leader partitions.
>
> **Talking point:** "Partition skew is one of the most common Kafka performance
> killers. This tool catches it before it becomes a production issue."

**Prompt 7 — Replication Health:**
```
Check the replication health. Are any partitions under-replicated?
```
> **What happens:** The AI calls `oci_kafka_detect_under_replicated_partitions`.
> On a healthy cluster: "healthy: true, 0 under-replicated." This proves
> all replicas are in sync across all brokers.
>
> **Talking point:** "Under-replicated partitions mean data durability is at risk.
> This check would normally require running `kafka-topics.sh --describe` and
> parsing the output — here it's a single natural language question."

---

### Act 4: AI-Powered Diagnostics — "What should I do?"

This is the differentiator. Show the AI not just reading data, but reasoning about it.

**Prompt 8 — Scaling Recommendation (Showstopper):**
```
Should I scale this cluster? Give me a full scaling assessment with recommendations.
```
> **What happens:** The AI calls `oci_kafka_recommend_scaling` — a single tool
> that orchestrates **three internal Kafka operations** (cluster health, partition
> skew analysis, under-replicated partition detection) and produces a structured
> diagnostic report. The report includes:
> - Cluster capacity summary (brokers, topics, total partitions)
> - Per-broker load analysis with deviation percentages
> - Replication health assessment
> - Actionable recommendations with severity levels (INFO/WARNING/CRITICAL)
>
> The AI then interprets this structured report and presents human-readable
> scaling advice.
>
> **Talking point:** "This is the AI-native advantage. One question triggered
> three Kafka API calls, cross-referenced the results, calculated per-broker
> deviation metrics, and produced a ranked recommendation report. Try doing
> that with a CLI."

**Prompt 9 — Comprehensive Ops Report:**
```
Give me a complete operational health assessment of this cluster. I want broker
status, replication health, partition balance, topic inventory with details, and
any recommended actions. Format it as an ops review summary.
```
> **What happens:** The AI orchestrates **multiple tools**: cluster health,
> partition skew, under-replicated partitions, list topics, describe each topic,
> and scaling recommendations — then synthesizes everything into a single
> executive summary. What would take 8-10 CLI commands and manual correlation
> becomes one conversational request.
>
> **Talking point:** "This is infrastructure observability through conversation.
> The AI is your SRE co-pilot."

---

### Act 5: Consumer Group Intelligence — "Why is my consumer behind?"

Demonstrate consumer group monitoring and AI-powered lag diagnosis.

**Prompt 10 — Consumer Group Discovery:**
```
List all consumer groups and show me their details.
```
> **What happens:** The AI calls `oci_kafka_list_consumer_groups` and
> `oci_kafka_describe_consumer_group` for each group. Shows group state
> (Stable/Empty/Rebalancing), member count, coordinator broker, and
> partition assignments.
>
> **Note:** On a fresh demo cluster with no producers/consumers running,
> this will return an empty list. That's expected — mention that in production
> this would show all active consumer groups. If you have a consumer group
> available, use the next prompt.

**Prompt 11 — Lag Root Cause Analysis (if consumer groups exist):**
```
Analyze the lag for consumer group "<GROUP_ID>" and tell me why it might be
falling behind. What are the potential root causes?
```
> **What happens:** The AI calls `oci_kafka_analyze_lag_root_cause` — a single
> tool that orchestrates **four internal operations** (describe consumer group,
> get per-partition lag, describe involved topics, get cluster health) and produces
> a structured root cause analysis:
> - Per-partition lag breakdown with severity (NONE/LOW/MEDIUM/HIGH/CRITICAL)
> - Hot partition detection
> - Consumer-to-partition ratio analysis
> - Potential root causes ranked by likelihood with specific remediation steps
>
> **Talking point:** "The AI diagnosed lag across 4 different data sources
> and ranked root causes by likelihood. This is operational intelligence,
> not just monitoring."

---

### Act 6: Safety Guardrails — "But is it safe?"

Demonstrate enterprise-grade safety controls.

**Prompt 12 — High-Risk Operation:**
```
Delete the user-activity topic.
```
> **What happens:** The AI calls `oci_kafka_delete_topic` which is classified as
> **HIGH risk**. The policy guard returns a confirmation requirement before
> proceeding. The AI communicates the risk and asks for explicit confirmation.
>
> **Talking point:** "Every tool has a risk classification. LOW operations execute
> freely. MEDIUM needs write mode. HIGH requires explicit confirmation. The AI
> can't accidentally destroy your infrastructure."

**Prompt 13 — Read-Only Mode Explanation:**
```
What happens if I run the server without --allow-writes?
```
> **What happens:** The AI explains that all 7 write tools (create/update/delete
> topic, create/scale cluster, reset offset, delete consumer group) are blocked.
> Only the 11 read-only tools work. This is the default safe mode.
>
> **Talking point:** "Read-only by default. You explicitly opt into write
> operations. Defense in depth."

---

### Act 7: Clean Up

**Prompt 14 — Teardown:**
```
Delete all the topics we created: order-events, payment-transactions,
inventory-updates, and user-activity.
```
> The AI deletes each topic. Each goes through the HIGH risk policy guard
> with confirmation.

---

## Key Talking Points During Demo

- **"18 tools, zero CLI commands"** — Cluster health, topic CRUD, consumer group monitoring, partition skew detection, replication health, AI-powered scaling recommendations, and lag root cause analysis — all through natural language.

- **"Every response is live data"** — This isn't mock data or cached responses. Every tool call hits the real Kafka Admin API on the OCI cluster in real time.

- **"AI diagnostics, not just wrappers"** — The `recommend_scaling` and `analyze_lag_root_cause` tools orchestrate 3-4 Kafka API calls each, cross-reference the results, and produce structured diagnostic reports. The AI then interprets these into actionable recommendations. This is operational intelligence.

- **"Read-only by default"** — The server starts in read-only mode. Write operations require an explicit `--allow-writes` flag. You decide what the AI can do.

- **"Risk-classified operations"** — Every tool has a risk level. LOW operations (health checks) execute freely. MEDIUM operations (create topic) require write mode. HIGH operations (delete topic, reset offsets) require explicit confirmation.

- **"Open standard, not vendor lock-in"** — Built on the Model Context Protocol (MCP), an open specification by Anthropic. Works with Claude Desktop today, but the same server works with any MCP-compatible client — VS Code, custom dashboards, automated runbooks.

- **"Circuit breaker prevents cascading failures"** — If Kafka becomes unavailable, the circuit breaker trips (after 5 consecutive failures) and returns fast errors instead of hanging. It auto-recovers when the cluster comes back.

- **"Audit trail for every action"** — Every tool execution is logged as structured JSON with timestamp, tool name, input hash, duration, and result status. Full compliance-ready audit trail.

- **"Production-grade security"** — SASL/SCRAM-SHA-512 authentication, TLS 1.2+ encryption, no credentials in code. The same security posture as any production Kafka client.

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
