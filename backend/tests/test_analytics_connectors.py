"""Unit tests for FairCart Decision Twin — External Analytics Connectors (Slice 5)."""

import os
import tempfile
import unittest

from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.engine.connectors.crypto import (
    InvalidVaultKeyError,
    MissingVaultKeyError,
    decrypt_credentials,
    encrypt_credentials,
    get_vault_encryption_key,
    mask_credential_value,
)
from backend.app.engine.connectors.ga4_connector import GA4Connector
from backend.app.engine.connectors.service import ConnectorService
from backend.app.engine.connectors.shopify_connector import ShopifyConnector
from backend.app.models.decision_twin_schemas import ConnectorConfigureRequest


class TestAnalyticsConnectors(unittest.TestCase):
    """Test suite covering crypto vault, GA4 & Shopify connectors, and orchestration service."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(db_path=self.db_path)

        # Explicit test-only vault key
        self._orig_vault_key = settings.CONNECTOR_VAULT_KEY
        self._orig_secret_key = settings.SECRET_KEY
        settings.CONNECTOR_VAULT_KEY = "hermetic-test-vault-key-32bytes-secret!"
        settings.SECRET_KEY = None

        self.service = ConnectorService(db_path=self.db_path)
        self.ga4 = GA4Connector()
        self.shopify = ShopifyConnector()

    def tearDown(self):
        settings.CONNECTOR_VAULT_KEY = self._orig_vault_key
        settings.SECRET_KEY = self._orig_secret_key
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except Exception:
                pass

    def test_missing_vault_key_refuses_encryption(self):
        """Verifies encrypt_credentials raises MissingVaultKeyError when no key is set."""
        settings.CONNECTOR_VAULT_KEY = None
        settings.SECRET_KEY = None
        with self.assertRaises(MissingVaultKeyError):
            encrypt_credentials({"token": "secret123"})

    def test_insecure_prohibited_key_refuses_encryption(self):
        """Verifies encrypt_credentials raises InvalidVaultKeyError when fallback or short key is used."""
        # 1. Prohibited default key
        settings.CONNECTOR_VAULT_KEY = "faircart-decision-twin-internal-vault-secret-key-2026"
        with self.assertRaises(InvalidVaultKeyError):
            encrypt_credentials({"token": "secret123"})

        # 2. Too short key (< 16 chars)
        settings.CONNECTOR_VAULT_KEY = "short_key_123"
        with self.assertRaises(InvalidVaultKeyError):
            encrypt_credentials({"token": "secret123"})

    def test_configure_connector_refuses_persistence_without_key(self):
        """Verifies service.configure_connector refuses to persist credentials when vault key is missing."""
        settings.CONNECTOR_VAULT_KEY = None
        settings.SECRET_KEY = None
        req = ConnectorConfigureRequest(
            provider="shopify",
            credentials={"shop_url": "acme.myshopify.com", "access_token": "shpat_12345678901234567890"},
            merchant_id="usr_test_merchant",
        )
        with self.assertRaises(MissingVaultKeyError):
            self.service.configure_connector(req)

        # Verify nothing was persisted to database
        configs = self.service.list_connectors(merchant_id="usr_test_merchant")
        shp = next(c for c in configs if c.provider == "shopify")
        self.assertEqual(shp.status, "unconfigured")

    def test_credential_encryption_and_decryption(self):
        secret_payload = {"api_token": "shpat_abc123secret999", "client_id": "oauth_client_777"}
        encrypted = encrypt_credentials(secret_payload)
        self.assertIsInstance(encrypted, str)
        self.assertNotIn("shpat_abc123secret999", encrypted)

        decrypted = decrypt_credentials(encrypted)
        self.assertEqual(decrypted, secret_payload)

    def test_decryption_with_wrong_key_returns_empty_dict(self):
        """Verifies decrypt_credentials returns {} and never leaks plaintext on mismatched key."""
        secret_payload = {"api_token": "shpat_abc123secret999"}
        encrypted = encrypt_credentials(secret_payload, key_override="initial-encryption-key-for-test-32b!")
        # Decrypt with different key
        decrypted = decrypt_credentials(encrypted, key_override="completely-different-key-for-test-32b!")
        self.assertEqual(decrypted, {})

    def test_credential_masking(self):
        masked = mask_credential_value("shpat_1234567890abcdef")
        self.assertEqual(masked, "shpa...cdef")
        self.assertEqual(mask_credential_value("short"), "***")

    def test_ga4_connector_validation(self):
        # Missing property
        valid, _, msg = self.ga4.test_connection({})
        self.assertFalse(valid)
        self.assertIn("Missing", msg)

        # Valid credentials
        valid, masked_id, msg = self.ga4.test_connection({
            "property_id": "properties/987654321",
            "client_email": "service-account@faircart.iam.gserviceaccount.com",
        })
        self.assertTrue(valid)
        self.assertIn("GA4-Prop", masked_id)
        self.assertIn("validated", msg.lower())

    def test_shopify_connector_validation(self):
        # Invalid domain
        valid, _, msg = self.shopify.test_connection({
            "shop_url": "invalid_domain",
            "access_token": "shpat_12345678901234567890",
        })
        self.assertFalse(valid)

        # Valid store
        valid, masked_id, msg = self.shopify.test_connection({
            "shop_url": "mystore.myshopify.com",
            "access_token": "shpat_12345678901234567890",
        })
        self.assertTrue(valid)
        self.assertIn("mystore.myshopify.com", masked_id)

    def test_connector_service_lifecycle(self):
        # 1. Initial list -> both unconfigured
        connectors = self.service.list_connectors(merchant_id="usr_test_merchant")
        self.assertEqual(len(connectors), 2)
        for c in connectors:
            self.assertEqual(c.status, "unconfigured")

        # 2. Configure Shopify
        cfg_req = ConnectorConfigureRequest(
            provider="shopify",
            credentials={"shop_url": "acme.myshopify.com", "access_token": "shpat_12345678901234567890"},
            merchant_id="usr_test_merchant",
        )
        conf = self.service.configure_connector(cfg_req)
        self.assertEqual(conf.status, "connected")
        self.assertIn("acme.myshopify.com", conf.masked_account_id)

        # 3. List again -> Shopify is connected, GA4 is unconfigured
        updated = self.service.list_connectors(merchant_id="usr_test_merchant")
        shp = next(c for c in updated if c.provider == "shopify")
        ga4 = next(c for c in updated if c.provider == "google_analytics_4")
        self.assertEqual(shp.status, "connected")
        self.assertEqual(ga4.status, "unconfigured")

        # 4. Sync data from Shopify
        sync_res = self.service.sync_connector(
            provider="shopify",
            storefront_id="primary_storefront",
            merchant_id="usr_test_merchant",
        )
        self.assertEqual(sync_res.status, "success")
        self.assertGreater(sync_res.records_ingested, 0)

        # 5. Disconnect Shopify
        deleted = self.service.disconnect_connector(provider="shopify", merchant_id="usr_test_merchant")
        self.assertTrue(deleted)

        post_delete = self.service.list_connectors(merchant_id="usr_test_merchant")
        shp_post = next(c for c in post_delete if c.provider == "shopify")
        self.assertEqual(shp_post.status, "unconfigured")


if __name__ == "__main__":
    unittest.main()
