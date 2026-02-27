# OCI Kafka MCP Server — Demo Setup Guide

Complete step-by-step guide to go from zero to a working demo of the OCI Kafka MCP Server connected to a live OCI Streaming with Apache Kafka cluster.

**Time estimate:** ~30 minutes (excluding OCI provisioning wait times)

---

## Prerequisites

### On your Mac

- **Python 3.11+** (`python3 --version`)
- **uv** package manager (`brew install uv` or see [docs.astral.sh/uv](https://docs.astral.sh/uv/))
- **Claude Desktop** installed (for the demo itself)
- **SSH client** (built into macOS)

### In OCI

- An OCI tenancy with access to **OCI Streaming with Apache Kafka** service
- A compartment where you can create resources
- Permissions to create: Kafka clusters, compute instances, VCNs/subnets

---

## Phase 1: Provision OCI Resources

### 1.1 Create a VCN (if you don't have one)

1. **OCI Console > Networking > Virtual Cloud Networks > Create VCN**
2. Use "Create VCN with Internet Connectivity" wizard
3. Choose the **same region** where you'll create the Kafka cluster (e.g., us-chicago-1)
4. Note down the **VCN OCID** and **private subnet OCID**

### 1.2 Provision the Kafka Cluster

1. **OCI Console > Analytics & AI > Streaming with Apache Kafka > Create Cluster**
2. Configuration:
   - **Region:** e.g., us-chicago-1
   - **VCN/Subnet:** Select your VCN and a private subnet
   - **Broker count:** 3 (default)
   - **Security:** Enable SASL/SCRAM authentication
3. Wait for the cluster to reach **ACTIVE** state (may take 10-20 minutes)
4. From the Cluster Details page, note down:
   - **Bootstrap server URL** (e.g., `bootstrap-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com:9092`)
   - **SASL username** (e.g., `super-user-XXXXX`)
   - **SASL password** (shown once or stored in OCI Vault)
   - **Cluster OCID**

> **IMPORTANT:** The Kafka cluster and compute instance MUST be in the **same region and same VCN**. Cross-region private networking does not work.

### 1.3 Create a Compute Instance (SSH Bastion)

The OCI Kafka cluster has private-only connectivity. You need a compute instance in the same VCN to create an SSH tunnel.

1. **OCI Console > Compute > Instances > Create Instance**
2. Configuration:
   - **Region:** Same as Kafka cluster (e.g., us-chicago-1)
   - **Image:** Oracle Linux 9
   - **Shape:** VM.Standard.E4.Flex (1 OCPU, 8 GB RAM is sufficient)
   - **VCN/Subnet:** Same VCN as Kafka, use a **public subnet** (so you can SSH from your Mac)
   - **SSH Key:** Upload or paste your public SSH key
3. Once running, note down:
   - **Public IP address** of the compute instance
   - **Path to your SSH private key** on your Mac

### 1.4 Verify Security List Rules

Ensure the VCN security lists allow traffic between the compute instance and Kafka brokers:

**Kafka's private subnet — Ingress Rules:**
| Source | Protocol | Port Range | Description |
|--------|----------|------------|-------------|
| VCN CIDR (e.g., 10.0.0.0/16) | TCP | 9092-9093 | Kafka broker traffic |

**Compute's public subnet — Egress Rules:**
| Destination | Protocol | Port Range | Description |
|-------------|----------|------------|-------------|
| 0.0.0.0/0 | All | All | Allow all outbound |

### 1.5 Verify DNS Resolution

SSH into the compute instance and verify DNS resolves:

```bash
ssh -i /path/to/your/private-key opc@<compute-public-ip>

# Test DNS resolution
dig <your-bootstrap-url>
# Should return an A record with a private IP (e.g., 10.0.x.x)

# Test connectivity
nc -zv <bootstrap-hostname> 9092
# Should show: Connection to ... 9092 port [tcp/*] succeeded!
```

If DNS returns **NXDOMAIN**, check:
1. **OCI Console > Networking > DNS Management > Private DNS Zones** — the Kafka service creates a private DNS zone; ensure it's associated with your VCN
2. **OCI Console > Networking > VCN > DNS Resolver** — verify the private view is attached

Install `nc` if missing: `sudo dnf install -y nmap-ncat`

---

## Phase 2: Configure Your Mac

### 2.1 Install the MCP Server

```bash
cd /Users/abhishek/Projects/01-KafkaMCP
uv sync
```

### 2.2 Discover Broker Hostnames

Run a quick bootstrap connection to discover the individual broker hostnames:

```bash
# First, set up a basic tunnel (bootstrap only)
ssh -i /path/to/your/private-key -L 127.0.0.1:9092:<bootstrap-hostname>:9092 -N -f opc@<compute-public-ip>

# Run a quick test to get broker hostnames
source .env.oci
.venv/bin/python -c "
from oci_kafka_mcp.config import KafkaConfig
from oci_kafka_mcp.kafka.admin_client import KafkaAdminClient
import json
client = KafkaAdminClient(KafkaConfig())
health = client.get_cluster_health()
for b in health['brokers']:
    print(f\"{b['host']}:{b['port']}\")
"

# Kill the temporary tunnel
lsof -ti :9092 | xargs kill -9
```

This will output broker hostnames like:
```
br0-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com:9092
br1-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com:9092
br2-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com:9092
```

### 2.3 Configure /etc/hosts

Map the bootstrap and all broker hostnames to loopback IPs:

```bash
sudo sh -c 'cat >> /etc/hosts << EOF

# OCI Kafka MCP — SSH tunnel endpoints
127.0.0.1 <bootstrap-hostname>
127.0.0.2 <br0-hostname>
127.0.0.3 <br1-hostname>
127.0.0.4 <br2-hostname>
EOF'
```

**Example with real hostnames:**
```bash
sudo sh -c 'cat >> /etc/hosts << EOF

# OCI Kafka MCP — SSH tunnel endpoints
127.0.0.1 bootstrap-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com
127.0.0.2 br0-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com
127.0.0.3 br1-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com
127.0.0.4 br2-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com
EOF'
```

### 2.4 Create Loopback Aliases

macOS only has `127.0.0.1` active by default. Add aliases for the broker IPs:

```bash
sudo ifconfig lo0 alias 127.0.0.2
sudo ifconfig lo0 alias 127.0.0.3
sudo ifconfig lo0 alias 127.0.0.4
```

> **Note:** These aliases do NOT persist across reboots. Run them again after each restart.

### 2.5 Configure .env.oci

```bash
cp .env.oci.example .env.oci
```

Edit `.env.oci` with your cluster details:

```bash
# Bootstrap servers (resolves to 127.0.0.1 via /etc/hosts for SSH tunnel)
export KAFKA_BOOTSTRAP_SERVERS="<bootstrap-hostname>:9092"

# Security
export KAFKA_SECURITY_PROTOCOL="SASL_SSL"
export KAFKA_SASL_MECHANISM="SCRAM-SHA-512"
export KAFKA_SASL_USERNAME="<your-sasl-username>"
export KAFKA_SASL_PASSWORD="<your-sasl-password>"

# CA certificate (Python certifi bundle)
export KAFKA_SSL_CA_LOCATION="/Users/abhishek/Projects/01-KafkaMCP/.venv/lib/python3.13/site-packages/certifi/cacert.pem"
```

> **Tip:** To find the certifi CA path: `.venv/bin/python -c "import certifi; print(certifi.where())"`

---

## Phase 3: Connect and Test

### 3.1 Start the SSH Tunnel

Open a terminal and start the tunnel with all 4 forwarding rules:

```bash
ssh -i /path/to/your/private-key -N -f \
    -L 127.0.0.1:9092:<bootstrap-hostname>:9092 \
    -L 127.0.0.2:9092:<br0-hostname>:9092 \
    -L 127.0.0.3:9092:<br1-hostname>:9092 \
    -L 127.0.0.4:9092:<br2-hostname>:9092 \
    opc@<compute-public-ip>
```

The `-N -f` flags run the tunnel in the background (no interactive shell).

**Verify the tunnel is running:**
```bash
lsof -i :9092
# Should show 4 ssh processes listening
```

### 3.2 Test the Connection

```bash
cd /Users/abhishek/Projects/01-KafkaMCP
source .env.oci

# Test cluster health
.venv/bin/python -c "
from oci_kafka_mcp.config import KafkaConfig
from oci_kafka_mcp.kafka.admin_client import KafkaAdminClient
import json
client = KafkaAdminClient(KafkaConfig())
print(json.dumps(client.get_cluster_health(), indent=2))
"
```

**Expected output:**
```json
{
  "cluster_id": "XXXXX",
  "controller_id": 0,
  "broker_count": 3,
  "brokers": [
    { "id": 0, "host": "br0-clstr-...", "port": 9092 },
    { "id": 1, "host": "br1-clstr-...", "port": 9092 },
    { "id": 2, "host": "br2-clstr-...", "port": 9092 }
  ],
  "topic_count": 0
}
```

### 3.3 Run the MCP Server (standalone test)

```bash
source .env.oci
.venv/bin/oci-kafka-mcp --allow-writes
```

The server should start without errors (it uses STDIO, so no visible output until a client connects).

---

## Phase 4: Configure Claude Desktop

### 4.1 Update Claude Desktop Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "oci-kafka": {
      "command": "/Users/abhishek/Projects/01-KafkaMCP/.venv/bin/oci-kafka-mcp",
      "args": ["--allow-writes"],
      "env": {
        "KAFKA_BOOTSTRAP_SERVERS": "bootstrap-clstr-XXXXX.kafka.us-chicago-1.oci.oraclecloud.com:9092",
        "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
        "KAFKA_SASL_MECHANISM": "SCRAM-SHA-512",
        "KAFKA_SASL_USERNAME": "<your-sasl-username>",
        "KAFKA_SASL_PASSWORD": "<your-sasl-password>",
        "KAFKA_SSL_CA_LOCATION": "/Users/abhishek/Projects/01-KafkaMCP/.venv/lib/python3.13/site-packages/certifi/cacert.pem"
      }
    }
  }
}
```

> **Note:** Keep any existing `"preferences"` key alongside `"mcpServers"`.

### 4.2 Restart Claude Desktop

Quit Claude Desktop completely (Cmd+Q) and reopen it. The MCP server should connect automatically — look for the tools icon in the Claude Desktop chat input.

---

## Phase 5: Demo Script

Once everything is connected, try these prompts in Claude Desktop:

### Read-Only Operations
```
Show me the health of my Kafka cluster.
```
```
List all topics in the cluster.
```
```
Check for any under-replicated partitions.
```

### Write Operations (requires --allow-writes)
```
Create a topic called "payment-events" with 6 partitions and replication factor 3.
```
```
Create a topic called "user-activity" with 3 partitions.
```
```
Describe the payment-events topic and check for partition skew.
```

### Full Demo Flow
```
I want a complete health check of my OCI Kafka cluster. Check broker status,
list topics, look for partition skew, and check for under-replicated partitions.
Give me a summary of the cluster's health.
```

---

## Teardown

### Kill the SSH Tunnel
```bash
lsof -ti :9092 | xargs kill -9
```

### Clean Up /etc/hosts
Edit `/etc/hosts` and remove the OCI Kafka lines:
```bash
sudo vi /etc/hosts
# Remove the "OCI Kafka MCP" section
```

### Terminate OCI Resources
1. **OCI Console > Streaming with Apache Kafka > Cluster > Terminate**
2. **OCI Console > Compute > Instance > Terminate** (check "Permanently delete boot volume")

---

## Quick Reference — Demo Day Checklist

Run these in order when setting up for a new demo:

```bash
# 1. Loopback aliases (needed after every Mac reboot)
sudo ifconfig lo0 alias 127.0.0.2
sudo ifconfig lo0 alias 127.0.0.3
sudo ifconfig lo0 alias 127.0.0.4

# 2. Start SSH tunnel (update hostnames and IPs for your new cluster)
ssh -i /path/to/key -N -f \
    -L 127.0.0.1:9092:<bootstrap>:9092 \
    -L 127.0.0.2:9092:<br0>:9092 \
    -L 127.0.0.3:9092:<br1>:9092 \
    -L 127.0.0.4:9092:<br2>:9092 \
    opc@<compute-public-ip>

# 3. Verify connection
cd /Users/abhishek/Projects/01-KafkaMCP
source .env.oci
.venv/bin/python -c "
from oci_kafka_mcp.config import KafkaConfig
from oci_kafka_mcp.kafka.admin_client import KafkaAdminClient
import json
client = KafkaAdminClient(KafkaConfig())
print(json.dumps(client.get_cluster_health(), indent=2))
"

# 4. Open Claude Desktop (ensure config points to new cluster)
# 5. Demo!
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `NXDOMAIN` on compute | Private DNS zone not attached to VCN | OCI Console > DNS Management > Private DNS Zones > Associate VCN |
| `Connection refused` on compute | Wrong IP or security list blocking | Verify security list allows TCP 9092 from VCN CIDR |
| `Can't assign requested address` (SSH) | Loopback aliases not set | Run `sudo ifconfig lo0 alias 127.0.0.X` |
| `Address already in use` (SSH) | Old tunnel still running | `lsof -ti :9092 \| xargs kill -9` |
| `SSL certificate verify failed` | Wrong CA bundle or hostname mismatch | Use certifi bundle + /etc/hosts mapping |
| `Permission denied (publickey)` | Wrong SSH key | Add `-i /path/to/key` to SSH command |
| `Failed to resolve brN-clstr-...` | Broker hostnames not in /etc/hosts | Add all broker hostnames (see Phase 2.3) |
| Claude Desktop shows "disconnected" | MCP server crash or tunnel down | Check tunnel (`lsof -i :9092`), restart Claude Desktop |
| Kafka cluster in different region than compute | Cross-region private networking | Both MUST be in same region and same VCN |
