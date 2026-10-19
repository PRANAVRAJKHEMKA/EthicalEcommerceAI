"""FairCart AI — Base Analytics Connector Interface (Slice 5)."""

from abc import ABC, abstractmethod
from typing import Any

from backend.app.models.decision_twin_schemas import (
    ConnectorSyncResult,
    ExternalConnectorConfig,
)


class BaseAnalyticsConnector(ABC):
    """Abstract contract for authorized external e-commerce and analytics connectors."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Connector provider identifier (e.g. 'google_analytics_4', 'shopify')."""
        pass

    @property
    @abstractmethod
    def read_only_scopes(self) -> list[str]:
        """Declared least-privilege read-only authorization scopes."""
        pass

    @abstractmethod
    def test_connection(self, credentials: dict[str, str]) -> tuple[bool, str, str]:
        """Tests whether provided credentials can authenticate successfully.

        Returns:
            (success: bool, masked_account_id: str, message: str)
        """
        pass

    @abstractmethod
    def sync_data(
        self,
        credentials: dict[str, str],
        storefront_id: str = "primary_storefront",
        merchant_id: str = "usr_demo_merchant",
    ) -> ConnectorSyncResult:
        """Fetches analytics traffic or order lines and ingests them into the multi-store tables."""
        pass
