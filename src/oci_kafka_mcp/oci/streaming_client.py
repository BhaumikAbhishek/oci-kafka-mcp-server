"""OCI Streaming API wrapper for cluster lifecycle operations.

This module wraps the OCI Python SDK's StreamAdminClient to support
cluster-level operations (create, scale, describe) that go through
the OCI control plane rather than the Kafka protocol.

Note: Phase 1 focuses on Kafka protocol operations. OCI API operations
(create/scale cluster) will be fully implemented in Phase 2 when
OCI Streaming exposes these capabilities for the managed Kafka service.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class OciStreamingClient:
    """Wrapper for OCI Streaming control plane operations.

    Currently a placeholder for Phase 2 implementation.
    Phase 1 cluster operations use the Kafka AdminClient directly.
    """

    def __init__(self, config_file: str = "~/.oci/config", profile: str = "DEFAULT") -> None:
        self._config_file = config_file
        self._profile = profile
        self._client = None

    def _get_client(self) -> Any:
        """Lazily initialize the OCI StreamAdminClient.

        Deferred to avoid import errors when OCI SDK is not configured.
        """
        if self._client is None:
            try:
                import oci

                config = oci.config.from_file(self._config_file, self._profile)
                self._client = oci.streaming.StreamAdminClient(config)
            except Exception as e:
                logger.warning("OCI SDK not configured: %s. OCI operations will be unavailable.", e)
                return None
        return self._client

    def list_streams(self, compartment_id: str) -> dict[str, Any]:
        """List all streams in a compartment. (Phase 2)"""
        client = self._get_client()
        if client is None:
            return {"error": "OCI SDK not configured"}

        try:
            response = client.list_streams(compartment_id=compartment_id)
            streams = []
            for stream in response.data:
                streams.append({
                    "id": stream.id,
                    "name": stream.name,
                    "partitions": stream.partitions,
                    "lifecycle_state": stream.lifecycle_state,
                })
            return {"stream_count": len(streams), "streams": streams}
        except Exception as e:
            return {"error": f"Failed to list streams: {e}"}

    def describe_stream(self, stream_id: str) -> dict[str, Any]:
        """Get detailed stream information. (Phase 2)"""
        client = self._get_client()
        if client is None:
            return {"error": "OCI SDK not configured"}

        try:
            response = client.get_stream(stream_id=stream_id)
            stream = response.data
            return {
                "id": stream.id,
                "name": stream.name,
                "partitions": stream.partitions,
                "lifecycle_state": stream.lifecycle_state,
                "compartment_id": stream.compartment_id,
                "stream_pool_id": stream.stream_pool_id,
                "messages_endpoint": stream.messages_endpoint,
                "time_created": str(stream.time_created),
            }
        except Exception as e:
            return {"error": f"Failed to describe stream: {e}"}
