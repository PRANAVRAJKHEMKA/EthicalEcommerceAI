"""FairCart AI — Connector Orchestration Service (Slice 5)

Manages connector registry, encrypted credential storage, health checks,
and scheduled/manual synchronization for GA4 and Shopify connectors.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.db.database import get_connection
from backend.app.engine.connectors.base import BaseAnalyticsConnector
from backend.app.engine.connectors.crypto import (
    decrypt_credentials,
    encrypt_credentials,
)
from backend.app.engine.connectors.ga4_connector import GA4Connector
from backend.app.engine.connectors.shopify_connector import ShopifyConnector
from backend.app.models.decision_twin_schemas import (
    ConnectorConfigureRequest,
    ConnectorSyncResult,
    ExternalConnectorConfig,
)

logger = logging.getLogger("faircart.twin.connectors.service")


class ConnectorService:
    """Service managing external analytics and e-commerce integrations."""

    def __init__(self, db_path: str | None = None, database_url: str | None = None):
        self.db_path = db_path
        self.database_url = database_url
        self._connectors: dict[str, BaseAnalyticsConnector] = {
            "google_analytics_4": GA4Connector(),
            "shopify": ShopifyConnector(),
        }

    def _get_connection(self):
        return get_connection(self.db_path, self.database_url)

    def list_connectors(self, merchant_id: str = "usr_demo_merchant") -> list[ExternalConnectorConfig]:
        """Lists configuration and health status of all supported external connectors."""
        conn = self._get_connection()
        configs: list[ExternalConnectorConfig] = []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM external_connector_configs
                WHERE merchant_id = ?
            """, (merchant_id,))
            rows = cursor.fetchall()
            row_map = {r["provider"]: r for r in rows}

            for provider, connector in self._connectors.items():
                if provider in row_map:
                    r = row_map[provider]
                    audit = []
                    try:
                        audit = json.loads(r["audit_log_json"])
                    except Exception:
                        pass

                    configs.append(ExternalConnectorConfig(
                        provider=provider,
                        merchant_id=merchant_id,
                        status=r["status"],
                        masked_account_id=r["masked_account_id"],
                        last_sync_at=r["last_sync_at"],
                        sync_frequency_hours=24,
                        read_only_scopes=connector.read_only_scopes,
                        audit_log=audit,
                    ))
                else:
                    # Default unconfigured state (truthful, no fake connection)
                    configs.append(ExternalConnectorConfig(
                        provider=provider,
                        merchant_id=merchant_id,
                        status="unconfigured",
                        masked_account_id=None,
                        last_sync_at=None,
                        sync_frequency_hours=24,
                        read_only_scopes=connector.read_only_scopes,
                        audit_log=[],
                    ))

            return configs
        finally:
            conn.close()

    def configure_connector(self, request: ConnectorConfigureRequest) -> ExternalConnectorConfig:
        """Validates credentials, encrypts them at rest, and persists the connector configuration."""
        provider = request.provider.lower()
        if provider not in self._connectors:
            raise ValueError(f"Unsupported connector provider: '{provider}'. Supported: {list(self._connectors.keys())}")

        connector = self._connectors[provider]
        valid, masked_id, msg = connector.test_connection(request.credentials)
        if not valid:
            raise ValueError(f"Credential validation failed for {provider}: {msg}")

        encrypted = encrypt_credentials(request.credentials)
        now = datetime.now(timezone.utc).isoformat()
        audit_entry = {
            "timestamp": now,
            "action": "CONFIGURED",
            "message": f"Credentials validated and encrypted. Account: {masked_id}",
        }

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            config_id = f"conn_{provider}_{request.merchant_id}"
            cursor.execute("""
                INSERT OR REPLACE INTO external_connector_configs (
                    id, merchant_id, provider, status, masked_account_id,
                    encrypted_credentials, settings_json, last_sync_at,
                    audit_log_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config_id,
                request.merchant_id,
                provider,
                "connected",
                masked_id,
                encrypted,
                json.dumps({"configured_by": request.merchant_id}),
                None,
                json.dumps([audit_entry]),
                now,
                now,
            ))
            conn.commit()

            return ExternalConnectorConfig(
                provider=provider,
                merchant_id=request.merchant_id,
                status="connected",
                masked_account_id=masked_id,
                last_sync_at=None,
                sync_frequency_hours=24,
                read_only_scopes=connector.read_only_scopes,
                audit_log=[audit_entry],
            )
        finally:
            conn.close()

    def sync_connector(
        self,
        provider: str,
        storefront_id: str = "primary_storefront",
        merchant_id: str = "usr_demo_merchant",
    ) -> ConnectorSyncResult:
        """Executes a data synchronization cycle for an active connector."""
        provider = provider.lower()
        if provider not in self._connectors:
            return ConnectorSyncResult(
                provider=provider,
                status="error",
                records_ingested=0,
                details=f"Unknown provider '{provider}'",
            )

        connector = self._connectors[provider]
        conn = self._get_connection()
        encrypted_creds = ""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT encrypted_credentials, audit_log_json FROM external_connector_configs
                WHERE merchant_id = ? AND provider = ?
            """, (merchant_id, provider))
            row = cursor.fetchone()
            if not row or not row["encrypted_credentials"]:
                return ConnectorSyncResult(
                    provider=provider,
                    status="unconfigured",
                    records_ingested=0,
                    details="Connector is not configured. Supply API credentials first.",
                )
            encrypted_creds = row["encrypted_credentials"]
            audit_log = []
            try:
                audit_log = json.loads(row["audit_log_json"])
            except Exception:
                pass
        finally:
            conn.close()

        credentials = decrypt_credentials(encrypted_creds)
        result = connector.sync_data(
            credentials=credentials,
            storefront_id=storefront_id,
            merchant_id=merchant_id,
            db_path=self.db_path,
            database_url=self.database_url,
        )

        # Update last_sync_at and audit log
        now = datetime.now(timezone.utc).isoformat()
        audit_log.append({
            "timestamp": now,
            "action": "SYNC_EXECUTED",
            "status": result.status,
            "records": result.records_ingested,
            "details": result.details,
        })

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE external_connector_configs
                SET last_sync_at = ?, audit_log_json = ?, updated_at = ?
                WHERE merchant_id = ? AND provider = ?
            """, (now, json.dumps(audit_log[-10:]), now, merchant_id, provider))
            conn.commit()
        finally:
            conn.close()

        return result

    def disconnect_connector(self, provider: str, merchant_id: str = "usr_demo_merchant") -> bool:
        """Removes connector credentials and resets state to unconfigured."""
        provider = provider.lower()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM external_connector_configs
                WHERE merchant_id = ? AND provider = ?
            """, (merchant_id, provider))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
