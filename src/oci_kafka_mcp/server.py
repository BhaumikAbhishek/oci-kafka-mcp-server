"""OCI Kafka MCP Server — Main entry point.

An MCP server that enables AI agents to manage OCI Streaming with
Apache Kafka clusters through structured tool execution.
"""

from __future__ import annotations

import argparse
import logging
import sys

from mcp.server.fastmcp import FastMCP

from oci_kafka_mcp.config import load_config
from oci_kafka_mcp.kafka.admin_client import KafkaAdminClient
from oci_kafka_mcp.kafka.connection import CircuitBreaker
from oci_kafka_mcp.kafka.consumer_client import KafkaConsumerClient
from oci_kafka_mcp.security.policy_guard import PolicyGuard
from oci_kafka_mcp.tools.cluster import register_cluster_tools
from oci_kafka_mcp.tools.cluster_management import register_cluster_management_tools
from oci_kafka_mcp.tools.consumers import register_consumer_tools
from oci_kafka_mcp.tools.observability import register_observability_tools
from oci_kafka_mcp.tools.topics import register_topic_tools

logger = logging.getLogger("oci_kafka_mcp")


def create_server(allow_writes: bool = False) -> FastMCP:
    """Create and configure the MCP server with all tools registered.

    Args:
        allow_writes: If True, enable write tools (create/delete topic, etc.).
                      If False, only read-only tools are functional.
    """
    config = load_config()

    # Override allow_writes from CLI argument
    if allow_writes:
        config.allow_writes = True

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # Initialize the MCP server
    mcp = FastMCP(
        "OCI Kafka MCP Server",
        instructions=(
            "AI-native control interface for OCI Streaming with Apache Kafka. "
            "Provides structured tools for cluster, topic, consumer, and "
            "observability operations."
        ),
    )

    # Initialize shared components
    admin_client = KafkaAdminClient(config.kafka)
    consumer_client = KafkaConsumerClient(config.kafka)
    policy_guard = PolicyGuard(allow_writes=config.allow_writes)
    circuit_breaker = CircuitBreaker()

    # Register all tool modules
    register_cluster_tools(mcp, admin_client, policy_guard, circuit_breaker)
    register_cluster_management_tools(mcp, policy_guard)
    register_topic_tools(mcp, admin_client, policy_guard, circuit_breaker)
    register_consumer_tools(mcp, consumer_client, policy_guard, circuit_breaker)
    register_observability_tools(mcp, admin_client, circuit_breaker)

    mode = "read-write" if config.allow_writes else "read-only"
    logger.info("OCI Kafka MCP Server initialized in %s mode", mode)
    logger.info("Kafka brokers: %s", config.kafka.bootstrap_servers)
    logger.info(
        "Security protocol: %s", config.kafka.security_protocol
    )

    return mcp


def main() -> None:
    """CLI entry point for the MCP server."""
    parser = argparse.ArgumentParser(
        description="OCI Kafka MCP Server — AI-native Kafka management",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        default=False,
        help="Enable write tools (createTopic, deleteTopic, scaleCluster, etc.)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    args = parser.parse_args()

    mcp = create_server(allow_writes=args.allow_writes)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
