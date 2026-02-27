"""Cluster lifecycle management tools for OCI Kafka MCP Server.

These tools use the OCI control plane API to manage Kafka cluster
lifecycle operations (create, scale). They require OCI SDK configuration.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from oci_kafka_mcp.audit.logger import audit
from oci_kafka_mcp.security.policy_guard import PolicyGuard


def register_cluster_management_tools(
    mcp: FastMCP,
    policy_guard: PolicyGuard,
) -> None:
    """Register OCI cluster lifecycle tools with the MCP server."""

    @mcp.tool()
    def oci_kafka_create_cluster(
        display_name: str,
        compartment_id: str,
        subnet_id: str,
        broker_count: int = 3,
    ) -> str:
        """Create a new OCI Streaming with Apache Kafka cluster.

        Requires --allow-writes to be enabled.
        This is a HIGH RISK operation that requires confirmation.

        This operation is asynchronous — the cluster will be in CREATING state
        until provisioning completes (typically 10-20 minutes).

        Args:
            display_name: Human-readable name for the cluster.
            compartment_id: OCI compartment OCID where the cluster will be created.
            subnet_id: OCI subnet OCID for the cluster's private network.
            broker_count: Number of broker nodes (default: 3).

        Returns the creation request status and cluster details.
        """
        params = {
            "display_name": display_name,
            "compartment_id": compartment_id,
            "subnet_id": subnet_id,
            "broker_count": broker_count,
        }

        check = policy_guard.check("oci_kafka_create_cluster", params)
        if not check.allowed:
            return json.dumps({"error": check.reason})

        if check.needs_confirmation:
            return json.dumps({
                "status": "confirmation_required",
                "message": f"Creating a new Kafka cluster '{display_name}' with {broker_count} "
                "brokers is a HIGH RISK operation. This will provision new OCI "
                "infrastructure and incur costs. Please confirm by calling this tool again.",
                "risk_level": "HIGH",
            })

        with audit.audit_tool("oci_kafka_create_cluster", params) as entry:
            try:
                result = _create_cluster_via_oci(
                    display_name, compartment_id, subnet_id, broker_count
                )
                entry.result_status = result.get("status", "unknown")
                return json.dumps(result, indent=2)
            except Exception as e:
                entry.result_status = "error"
                entry.error_message = str(e)
                return json.dumps({"error": f"Failed to create cluster: {e}"})

    @mcp.tool()
    def oci_kafka_scale_cluster(
        cluster_id: str,
        broker_count: int,
    ) -> str:
        """Scale an OCI Streaming with Apache Kafka cluster.

        Requires --allow-writes to be enabled.
        This is a HIGH RISK operation that requires confirmation.

        This operation is asynchronous — the cluster will transition through
        UPDATING state while scaling completes.

        Args:
            cluster_id: OCI Kafka cluster OCID to scale.
            broker_count: Target number of broker nodes.

        Returns the scale request status.
        """
        params = {
            "cluster_id": cluster_id,
            "broker_count": broker_count,
        }

        check = policy_guard.check("oci_kafka_scale_cluster", params)
        if not check.allowed:
            return json.dumps({"error": check.reason})

        if check.needs_confirmation:
            return json.dumps({
                "status": "confirmation_required",
                "message": f"Scaling cluster to {broker_count} brokers is a HIGH RISK "
                "operation. This will modify live infrastructure and may cause "
                "temporary partition rebalancing. Please confirm by calling this tool again.",
                "risk_level": "HIGH",
            })

        with audit.audit_tool("oci_kafka_scale_cluster", params) as entry:
            try:
                result = _scale_cluster_via_oci(cluster_id, broker_count)
                entry.result_status = result.get("status", "unknown")
                return json.dumps(result, indent=2)
            except Exception as e:
                entry.result_status = "error"
                entry.error_message = str(e)
                return json.dumps({"error": f"Failed to scale cluster: {e}"})


def _create_cluster_via_oci(
    display_name: str,
    compartment_id: str,
    subnet_id: str,
    broker_count: int,
) -> dict[str, Any]:
    """Create a Kafka cluster using the OCI SDK."""
    try:
        import oci

        config = oci.config.from_file()
        # OCI Streaming with Apache Kafka uses the kafka service client
        # The module name may vary as the service is new
        client = oci.kafka.KafkaClient(config)
        response = client.create_cluster(
            create_cluster_details=oci.kafka.models.CreateClusterDetails(
                display_name=display_name,
                compartment_id=compartment_id,
                subnet_id=subnet_id,
                broker_node_count=broker_count,
            )
        )
        cluster = response.data
        return {
            "status": "creating",
            "cluster_id": cluster.id,
            "display_name": display_name,
            "broker_count": broker_count,
            "lifecycle_state": cluster.lifecycle_state,
        }
    except ImportError:
        return {
            "status": "unavailable",
            "error": "OCI SDK is not installed. Install with: pip install oci",
        }
    except AttributeError:
        return {
            "status": "unavailable",
            "error": "OCI Kafka module (oci.kafka) is not available in the installed "
            "OCI SDK version. This feature requires OCI SDK with Kafka service support. "
            "Please update the OCI SDK or use the OCI Console to manage cluster lifecycle.",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _scale_cluster_via_oci(
    cluster_id: str,
    broker_count: int,
) -> dict[str, Any]:
    """Scale a Kafka cluster using the OCI SDK."""
    try:
        import oci

        config = oci.config.from_file()
        client = oci.kafka.KafkaClient(config)
        response = client.update_cluster(
            cluster_id=cluster_id,
            update_cluster_details=oci.kafka.models.UpdateClusterDetails(
                broker_node_count=broker_count,
            ),
        )
        cluster = response.data
        return {
            "status": "scaling",
            "cluster_id": cluster_id,
            "target_broker_count": broker_count,
            "lifecycle_state": cluster.lifecycle_state,
        }
    except ImportError:
        return {
            "status": "unavailable",
            "error": "OCI SDK is not installed. Install with: pip install oci",
        }
    except AttributeError:
        return {
            "status": "unavailable",
            "error": "OCI Kafka module (oci.kafka) is not available in the installed "
            "OCI SDK version. This feature requires OCI SDK with Kafka service support. "
            "Please update the OCI SDK or use the OCI Console to manage cluster lifecycle.",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
