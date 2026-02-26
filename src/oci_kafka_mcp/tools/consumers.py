"""Consumer operations tools for OCI Kafka MCP Server."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from oci_kafka_mcp.audit.logger import audit
from oci_kafka_mcp.kafka.connection import CircuitBreaker
from oci_kafka_mcp.kafka.consumer_client import KafkaConsumerClient
from oci_kafka_mcp.security.policy_guard import PolicyGuard


def register_consumer_tools(
    mcp: FastMCP,
    consumer_client: KafkaConsumerClient,
    policy_guard: PolicyGuard,
    circuit_breaker: CircuitBreaker,
) -> None:
    """Register consumer operation tools with the MCP server."""

    @mcp.tool()
    def oci_kafka_list_consumer_groups() -> str:
        """List all consumer groups in the Kafka cluster.

        Returns the total group count and a list of consumer groups
        with their state and type information.
        """
        if not circuit_breaker.allow_request():
            return json.dumps({"error": "Circuit breaker is open. Kafka may be unavailable."})

        with audit.audit_tool("oci_kafka_list_consumer_groups", {}) as entry:
            try:
                result = consumer_client.list_consumer_groups()
                entry.result_status = "success"
                circuit_breaker.record_success()
                return json.dumps(result, indent=2)
            except Exception as e:
                circuit_breaker.record_failure()
                entry.result_status = "error"
                entry.error_message = str(e)
                return json.dumps({"error": f"Failed to list consumer groups: {e}"})

    @mcp.tool()
    def oci_kafka_describe_consumer_group(group_id: str) -> str:
        """Get detailed information about a consumer group.

        Args:
            group_id: The consumer group ID to describe.

        Returns the group state, coordinator, partition assignor, and
        member details including their topic-partition assignments.
        """
        if not circuit_breaker.allow_request():
            return json.dumps({"error": "Circuit breaker is open. Kafka may be unavailable."})

        params = {"group_id": group_id}
        with audit.audit_tool("oci_kafka_describe_consumer_group", params) as entry:
            try:
                result = consumer_client.describe_consumer_group(group_id)
                entry.result_status = "success"
                circuit_breaker.record_success()
                return json.dumps(result, indent=2)
            except Exception as e:
                circuit_breaker.record_failure()
                entry.result_status = "error"
                entry.error_message = str(e)
                return json.dumps(
                    {"error": f"Failed to describe consumer group '{group_id}': {e}"}
                )

    @mcp.tool()
    def oci_kafka_get_consumer_lag(group_id: str) -> str:
        """Get consumer lag for a consumer group across all assigned partitions.

        Args:
            group_id: The consumer group ID to check lag for.

        Returns total lag, and per-partition details including committed offset,
        end offset, and lag. Use this to diagnose slow consumers or processing bottlenecks.
        """
        if not circuit_breaker.allow_request():
            return json.dumps({"error": "Circuit breaker is open. Kafka may be unavailable."})

        params = {"group_id": group_id}
        with audit.audit_tool("oci_kafka_get_consumer_lag", params) as entry:
            try:
                result = consumer_client.get_consumer_lag(group_id)
                entry.result_status = "success"
                circuit_breaker.record_success()
                return json.dumps(result, indent=2)
            except Exception as e:
                circuit_breaker.record_failure()
                entry.result_status = "error"
                entry.error_message = str(e)
                return json.dumps(
                    {"error": f"Failed to get consumer lag for group '{group_id}': {e}"}
                )
