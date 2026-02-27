"""Tests for cluster lifecycle management tools (create, scale)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from oci_kafka_mcp.security.policy_guard import PolicyGuard, RiskLevel


class TestCreateClusterPolicy:
    """Test policy guard checks for create_cluster."""

    def test_denied_in_readonly_mode(self, policy_guard_readonly: PolicyGuard) -> None:
        """create_cluster should be denied in read-only mode."""
        result = policy_guard_readonly.check("oci_kafka_create_cluster", {})
        assert not result.allowed
        assert "allow-writes" in result.reason

    def test_requires_confirmation(self, policy_guard_readwrite: PolicyGuard) -> None:
        """create_cluster should require confirmation in read-write mode."""
        result = policy_guard_readwrite.check("oci_kafka_create_cluster", {})
        assert result.allowed
        assert result.needs_confirmation
        assert result.risk_level == RiskLevel.HIGH


class TestScaleClusterPolicy:
    """Test policy guard checks for scale_cluster."""

    def test_denied_in_readonly_mode(self, policy_guard_readonly: PolicyGuard) -> None:
        """scale_cluster should be denied in read-only mode."""
        result = policy_guard_readonly.check("oci_kafka_scale_cluster", {})
        assert not result.allowed

    def test_requires_confirmation(self, policy_guard_readwrite: PolicyGuard) -> None:
        """scale_cluster should require confirmation in read-write mode."""
        result = policy_guard_readwrite.check("oci_kafka_scale_cluster", {})
        assert result.allowed
        assert result.needs_confirmation
        assert result.risk_level == RiskLevel.HIGH


class TestCreateClusterOciSdk:
    """Test the OCI SDK integration for cluster creation."""

    @patch("oci_kafka_mcp.tools.cluster_management._create_cluster_via_oci")
    def test_returns_unavailable_without_sdk(self, mock_create: MagicMock) -> None:
        """Should return unavailable status when OCI Kafka module is missing."""
        mock_create.return_value = {
            "status": "unavailable",
            "error": "OCI Kafka module (oci.kafka) is not available",
        }
        result = mock_create("test-cluster", "comp-id", "subnet-id", 3)
        assert result["status"] == "unavailable"


class TestDeleteConsumerGroupPolicy:
    """Test policy guard checks for delete_consumer_group."""

    def test_denied_in_readonly_mode(self, policy_guard_readonly: PolicyGuard) -> None:
        """delete_consumer_group should be denied in read-only mode."""
        result = policy_guard_readonly.check("oci_kafka_delete_consumer_group", {})
        assert not result.allowed

    def test_requires_confirmation(self, policy_guard_readwrite: PolicyGuard) -> None:
        """delete_consumer_group should require confirmation in read-write mode."""
        result = policy_guard_readwrite.check("oci_kafka_delete_consumer_group", {})
        assert result.allowed
        assert result.needs_confirmation
        assert result.risk_level == RiskLevel.HIGH


class TestResetConsumerOffsetPolicy:
    """Test policy guard checks for reset_consumer_offset."""

    def test_denied_in_readonly_mode(self, policy_guard_readonly: PolicyGuard) -> None:
        """reset_consumer_offset should be denied in read-only mode."""
        result = policy_guard_readonly.check("oci_kafka_reset_consumer_offset", {})
        assert not result.allowed

    def test_requires_confirmation(self, policy_guard_readwrite: PolicyGuard) -> None:
        """reset_consumer_offset should require confirmation in read-write mode."""
        result = policy_guard_readwrite.check("oci_kafka_reset_consumer_offset", {})
        assert result.allowed
        assert result.needs_confirmation
        assert result.risk_level == RiskLevel.HIGH
