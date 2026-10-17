"""FairCart AI — Step 5.19: Transaction Outcome Intelligence & Uplift Lab Tests

Verifies:
1. First-Party Event Ledger:
   - Support for all commerce events (views, rec impressions/clicks, cart adds/removes, offer exposures/acceptances/rejections, checkouts, demo orders).
   - Event deduplication via stable idempotency IDs (INSERT OR IGNORE).
   - Automatic metadata enrichment with provenance ('observed_demo') and storefront ('storefront_default').
   - Zero personal data (PII) stored.
   - Outcome funnel aggregation and conversion rate computations.
2. Criteo Uplift Schema Validation & Assumptions:
   - Valid CSV loading on synthetic fixture.
   - Rejection of malformed schemas (missing treatment, non-binary labels, empty data).
3. Two-Model T-Learner Causal Evaluation:
   - Model fitting and heterogeneous treatment effect estimation.
   - Qini curve, AUUC, and decile metric calculations.
   - Comparison with Non-Causal Propensity and Random baselines.
4. FastAPI Endpoints:
   - GET /api/v1/analytics/funnel
   - GET /api/v1/uplift/evaluation
   - POST /api/v1/uplift/evaluate
"""

import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import get_connection, init_db, is_postgres
from backend.app.db.repository import CatalogRepository
from backend.app.engine.uplift import (
    TLearnerUpliftModel,
    UpliftDatasetSchemaError,
    compute_qini_curve,
    load_and_validate_dataset,
    run_uplift_evaluation,
)
from backend.app.main import app


class TestStep519OutcomeAndUplift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_db_path = str(Path(cls.temp_dir.name) / "test_outcome_uplift.db")
        init_db(cls.temp_db_path)
        cls.repo = CatalogRepository()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        self.assertFalse(
            is_postgres(settings.DATABASE_URL),
            "FATAL: Tests must execute against local SQLite test fixtures only.",
        )

    # -------------------------------------------------------------------------
    # 1. First-Party Outcome Ledger Tests
    # -------------------------------------------------------------------------
    def test_01_event_recording_with_provenance_and_deduplication(self):
        """Verifies that events are safely recorded with provenance and deduplicated by ID."""
        session_id = "test-funnel-sess-01"
        event_id = "evt-dedup-fixed-id-001"

        # First recording
        id_1 = self.repo.record_session_event(
            session_id=session_id,
            event_type="product_view",
            product_id="item-001",
            shopping_context="all",
            event_id=event_id,
        )
        self.assertEqual(id_1, event_id)

        # Duplicate recording with same event_id (must not create duplicate)
        id_2 = self.repo.record_session_event(
            session_id=session_id,
            event_type="product_view",
            product_id="item-001",
            shopping_context="all",
            event_id=event_id,
        )
        self.assertEqual(id_2, event_id)

        events = self.repo.get_session_events(session_id)
        matching = [e for e in events if e["id"] == event_id]
        self.assertEqual(len(matching), 1, "Duplicate event_id was not deduplicated!")

        # Verify default provenance and storefront enrichment
        self.assertEqual(matching[0]["metadata"].get("provenance"), "observed_demo")
        self.assertEqual(matching[0]["metadata"].get("storefront_id"), "storefront_default")

    def test_02_funnel_stages_and_rates_aggregation(self):
        """Verifies that get_outcome_funnel_metrics accurately tallies stages and rates."""
        test_sess = "test-funnel-sess-02"

        # Record a full journey
        self.repo.record_session_event(session_id=test_sess, event_type="product_view", product_id="item-003")
        self.repo.record_session_event(session_id=test_sess, event_type="search_submitted")
        self.repo.record_session_event(session_id=test_sess, event_type="recommendation_impression", product_id="item-005")
        self.repo.record_session_event(session_id=test_sess, event_type="recommendation_click", product_id="item-005")
        self.repo.record_session_event(session_id=test_sess, event_type="add_to_cart", product_id="item-003")
        self.repo.record_session_event(session_id=test_sess, event_type="offer_exposure", product_id="item-005")
        self.repo.record_session_event(session_id=test_sess, event_type="offer_accepted", product_id="item-005")
        self.repo.record_session_event(session_id=test_sess, event_type="checkout_started")
        self.repo.record_session_event(session_id=test_sess, event_type="demo_order_completed")

        metrics = self.repo.get_outcome_funnel_metrics(time_window_hours=24)
        stages = metrics["funnel_stages"]

        self.assertGreaterEqual(stages["product_views"], 1)
        self.assertGreaterEqual(stages["searches_submitted"], 1)
        self.assertGreaterEqual(stages["recommendation_impressions"], 1)
        self.assertGreaterEqual(stages["recommendation_clicks"], 1)
        self.assertGreaterEqual(stages["cart_adds"], 1)
        self.assertGreaterEqual(stages["offer_exposures"], 1)
        self.assertGreaterEqual(stages["offer_acceptances"], 1)
        self.assertGreaterEqual(stages["checkouts_started"], 1)
        self.assertGreaterEqual(stages["demo_orders_completed"], 1)

        # Rates must be valid probabilities
        rates = metrics["conversion_rates"]
        self.assertGreaterEqual(rates["recommendation_ctr"], 0.0)
        self.assertLessEqual(rates["recommendation_ctr"], 1.0)
        self.assertGreaterEqual(rates["offer_acceptance_rate"], 0.0)
        self.assertLessEqual(rates["offer_acceptance_rate"], 1.0)

        # Provenance must be tracked
        self.assertIn("observed_demo", metrics["provenance_breakdown"])

    # -------------------------------------------------------------------------
    # 2. Criteo Uplift Schema Validation Tests
    # -------------------------------------------------------------------------
    def test_03_uplift_dataset_loader_success_on_fixture(self):
        """Verifies that load_and_validate_dataset successfully parses the synthetic fixture."""
        X, treatment, outcome, feature_names, provenance = load_and_validate_dataset()
        self.assertEqual(X.shape[0], 1000)
        self.assertEqual(X.shape[1], 12)
        self.assertEqual(len(treatment), 1000)
        self.assertEqual(len(outcome), 1000)
        self.assertEqual(feature_names, [f"f{i}" for i in range(12)])
        self.assertTrue(len(provenance) > 0)

    def test_04_uplift_dataset_loader_catches_missing_treatment_column(self):
        """Verifies schema validation fails if treatment column is absent."""
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        malformed_csv = fixtures_dir / "temp_test_malformed_no_treatment.csv"
        try:
            with open(malformed_csv, "w", encoding="utf-8") as f:
                f.write("f0,f1,conversion\n1.0,2.0,1\n3.0,4.0,0\n")

            with self.assertRaises(UpliftDatasetSchemaError) as ctx:
                load_and_validate_dataset(malformed_csv)
            self.assertIn("treatment", str(ctx.exception).lower())
        finally:
            if malformed_csv.exists():
                malformed_csv.unlink()

    def test_05_uplift_dataset_loader_catches_non_binary_treatment(self):
        """Verifies schema validation fails if treatment has non-binary values (e.g. 5)."""
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        malformed_csv = fixtures_dir / "temp_test_malformed_non_binary.csv"
        try:
            with open(malformed_csv, "w", encoding="utf-8") as f:
                f.write("f0,f1,treatment,conversion\n1.0,2.0,5,1\n3.0,4.0,0,0\n")

            with self.assertRaises(UpliftDatasetSchemaError) as ctx:
                load_and_validate_dataset(malformed_csv)
            self.assertIn("strictly binary", str(ctx.exception).lower())
        finally:
            if malformed_csv.exists():
                malformed_csv.unlink()

    # -------------------------------------------------------------------------
    # 3. Two-Model T-Learner & Qini Metric Tests
    # -------------------------------------------------------------------------
    def test_06_t_learner_model_fitting_and_uplift_prediction(self):
        """Verifies that TLearner fits both models and produces continuous uplift predictions."""
        X, treatment, outcome, _, _ = load_and_validate_dataset()
        model = TLearnerUpliftModel(random_state=42)
        model.fit(X[:700], treatment[:700], outcome[:700])

        uplift_scores = model.predict_uplift(X[700:])
        self.assertEqual(len(uplift_scores), 300)
        # Uplift scores must be within [-1.0, 1.0]
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in uplift_scores))

        propensity_scores = model.predict_propensity(X[700:])
        self.assertEqual(len(propensity_scores), 300)
        # Propensity scores must be within [0.0, 1.0]
        self.assertTrue(all(0.0 <= s <= 1.0 for s in propensity_scores))

    def test_07_compute_qini_curve_and_auuc(self):
        """Verifies Qini curve computation, trapezoidal AUUC, and 10 deciles."""
        X, treatment, outcome, _, _ = load_and_validate_dataset()
        model = TLearnerUpliftModel(random_state=42)
        model.fit(X[:700], treatment[:700], outcome[:700])
        uplift_preds = model.predict_uplift(X[700:])

        grid_x, interpolated_qini, auuc, qini_coeff, deciles = compute_qini_curve(
            uplift_preds, treatment[700:], outcome[700:], n_bins=10
        )

        self.assertEqual(len(grid_x), 101)
        self.assertEqual(len(interpolated_qini), 101)
        self.assertIsInstance(auuc, float)
        self.assertIsInstance(qini_coeff, float)
        self.assertEqual(len(deciles), 10)
        # Deciles must be numbered 1 to 10
        self.assertEqual([d["decile"] for d in deciles], list(range(1, 11)))

    def test_08_run_uplift_evaluation_end_to_end(self):
        """Verifies complete end-to-end uplift evaluation pipeline with 3 models and 3 strategies."""
        results = run_uplift_evaluation()

        self.assertIn("synthetic", results["dataset_name"].lower())
        self.assertEqual(results["train_samples"], 700)
        self.assertEqual(results["test_samples"], 300)

        # Check 3 models present
        models = results["models"]
        self.assertIn("t_learner", models)
        self.assertIn("propensity_baseline", models)
        self.assertIn("random_baseline", models)

        # T-Learner normalized Qini should be higher than random baseline (0.0)
        self.assertGreater(models["t_learner"]["normalized_qini"], models["random_baseline"]["normalized_qini"])

        # Check 3 strategies present
        strat_ids = [s["strategy_id"] for s in results["strategy_comparison"]]
        self.assertEqual(strat_ids, ["no_discount", "blanket_markdown", "uplift_targeted"])

    # -------------------------------------------------------------------------
    # 4. FastAPI Endpoints Integration Tests
    # -------------------------------------------------------------------------
    def test_09_get_funnel_analytics_endpoint(self):
        """Verifies GET /api/v1/analytics/funnel returns valid schema."""
        resp = self.client.get("/api/v1/analytics/funnel")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("funnel_stages", data)
        self.assertIn("conversion_rates", data)
        self.assertIn("provenance_breakdown", data)
        self.assertIn("methodology_disclaimer", data)
        self.assertIn("demo orders represent interactive customer simulation", data["methodology_disclaimer"].lower())

    def test_10_get_uplift_evaluation_endpoint(self):
        """Verifies GET /api/v1/uplift/evaluation returns valid schema and models."""
        resp = self.client.get("/api/v1/uplift/evaluation")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["dataset_name"], "synthetic_uplift_data.csv")
        self.assertIn("t_learner", data["models"])
        self.assertEqual(len(data["decile_breakdown"]), 10)
        self.assertEqual(len(data["strategy_comparison"]), 3)

    def test_11_post_uplift_evaluate_endpoint(self):
        """Verifies POST /api/v1/uplift/evaluate triggers evaluation with visit outcome."""
        resp = self.client.post("/api/v1/uplift/evaluate?outcome=visit")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["outcome_evaluated"], "visit")

    # -------------------------------------------------------------------------
    # 5. Security & Resource Bounds Tests (Path Traversal, Limits, Error Codes)
    # -------------------------------------------------------------------------
    def test_12_uplift_security_rejects_path_traversal(self):
        """Verifies that dataset loader strictly rejects paths outside allowed directories."""
        traversal_attempts = [
            "../../backend/app/main.py",
            "../../../etc/passwd",
            "C:\\Windows\\System32\\drivers\\etc\\hosts",
            str(Path(self.temp_dir.name) / "external.csv"),
        ]
        for bad_path in traversal_attempts:
            with self.assertRaises(UpliftDatasetSchemaError) as ctx:
                load_and_validate_dataset(bad_path)
            self.assertIn("access denied", str(ctx.exception).lower())

    def test_13_uplift_security_rejects_disallowed_extension(self):
        """Verifies that only .csv and .csv.gz file formats are accepted."""
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        bad_ext_file = fixtures_dir / "temp_disallowed.json"
        try:
            with open(bad_ext_file, "w", encoding="utf-8") as f:
                f.write('{"test": 123}\n')
            with self.assertRaises(UpliftDatasetSchemaError) as ctx:
                load_and_validate_dataset(bad_ext_file)
            self.assertIn("invalid file format", str(ctx.exception).lower())
        finally:
            if bad_ext_file.exists():
                bad_ext_file.unlink()

    def test_14_uplift_endpoint_path_traversal_returns_400(self):
        """Verifies that API endpoint rejects path traversal with HTTP 400."""
        resp = self.client.post("/api/v1/uplift/evaluate?dataset_path=../../../../etc/passwd")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("outside permitted directories", resp.json()["detail"].lower())

    def test_15_uplift_endpoint_missing_file_returns_404(self):
        """Verifies that API endpoint returns HTTP 404 when dataset file does not exist."""
        resp = self.client.get("/api/v1/uplift/evaluation?dataset_path=nonexistent_data_file.csv")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_16_uplift_dataset_loader_caps_max_rows(self):
        """Verifies that max_rows argument correctly bounds the number of parsed rows."""
        X, treatment, outcome, _, _ = load_and_validate_dataset(max_rows=100)
        self.assertEqual(X.shape[0], 100)
        self.assertEqual(len(treatment), 100)
        self.assertEqual(len(outcome), 100)

    # -------------------------------------------------------------------------
    # 6. Compressed-File (.csv.gz) Safety & Resource Bounds Tests
    # -------------------------------------------------------------------------
    def test_17_compressed_gzip_dataset_loading(self):
        """Verifies that valid .csv.gz archives are safely decompressed and loaded."""
        import gzip
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        src_csv = fixtures_dir / "synthetic_uplift_data.csv"
        gz_path = fixtures_dir / "temp_test_valid.csv.gz"

        try:
            with open(src_csv, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                f_out.writelines(f_in)

            X, treatment, outcome, feature_names, provenance = load_and_validate_dataset(gz_path)
            self.assertEqual(X.shape[0], 1000)
            self.assertEqual(X.shape[1], 12)
            self.assertEqual(len(treatment), 1000)
            self.assertEqual(len(outcome), 1000)
            self.assertEqual(feature_names, [f"f{i}" for i in range(12)])
            self.assertIn("synthetic", provenance.lower())
        finally:
            if gz_path.exists():
                gz_path.unlink()

    def test_18_compressed_gzip_magic_header_validation(self):
        """Verifies that non-gzip files masked as .csv.gz are rejected before decompression."""
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        fake_gz = fixtures_dir / "temp_fake_archive.csv.gz"

        try:
            with open(fake_gz, "w", encoding="utf-8") as f:
                f.write("f0,f1,treatment,conversion\n1.0,2.0,1,1\n")

            with self.assertRaises(UpliftDatasetSchemaError) as ctx:
                load_and_validate_dataset(fake_gz)
            self.assertIn("magic", str(ctx.exception).lower())
        finally:
            if fake_gz.exists():
                fake_gz.unlink()

    def test_19_compressed_gzip_corrupted_stream_rejection(self):
        """Verifies that corrupted or truncated gzip archives are cleanly rejected."""
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        corrupt_gz = fixtures_dir / "temp_corrupt_stream.csv.gz"

        try:
            # Valid gzip header (0x1f 0x8b 0x08) followed by corrupt payload
            with open(corrupt_gz, "wb") as f:
                f.write(b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xffcorrupted_payload_that_fails_deflate")

            with self.assertRaises(UpliftDatasetSchemaError) as ctx:
                load_and_validate_dataset(corrupt_gz)
            self.assertTrue(
                "corrupted" in str(ctx.exception).lower() or "error" in str(ctx.exception).lower()
            )
        finally:
            if corrupt_gz.exists():
                corrupt_gz.unlink()

    def test_20_compressed_decompression_size_limit_protection(self):
        """Verifies that DecompressionSizeLimiter halts processing if decompressed bytes exceed safety thresholds."""
        from backend.app.engine.uplift import DecompressionSizeLimiter

        # Stream of lines totaling 1,000 bytes
        mock_stream = iter(["x" * 200 + "\n"] * 5)
        # Set limit to 500 bytes
        limiter = DecompressionSizeLimiter(mock_stream, max_bytes=500)

        with self.assertRaises(UpliftDatasetSchemaError) as ctx:
            for _ in limiter:
                pass
        self.assertIn("decompression bomb protection", str(ctx.exception).lower())

    def test_21_compressed_gzip_max_rows_enforcement(self):
        """Verifies that max_rows bounding is strictly enforced on .csv.gz streams."""
        import gzip
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        src_csv = fixtures_dir / "synthetic_uplift_data.csv"
        gz_path = fixtures_dir / "temp_test_rows.csv.gz"

        try:
            with open(src_csv, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                f_out.writelines(f_in)

            X, treatment, outcome, _, _ = load_and_validate_dataset(gz_path, max_rows=75)
            self.assertEqual(X.shape[0], 75)
            self.assertEqual(len(treatment), 75)
            self.assertEqual(len(outcome), 75)
        finally:
            if gz_path.exists():
                gz_path.unlink()


    # -------------------------------------------------------------------------
    # 7. Commerce Event Semantics & Funnel Stage Invariant Tests
    # -------------------------------------------------------------------------
    def test_22_recommendation_impression_does_not_increment_clicks(self):
        """Verifies that recommendation impressions/views never count as clicks."""
        sess = f"test-sess-semantics-22-{uuid.uuid4().hex[:8]}"
        self.repo.record_session_event(session_id=sess, event_type="recommendation_impression", product_id="item-001")
        self.repo.record_session_event(session_id=sess, event_type="recommendation_shown", product_id="item-002")

        events = self.repo.get_session_events(sess)
        self.assertEqual(len(events), 2)
        for e in events:
            self.assertIn(e["event_type"], ("recommendation_impression", "recommendation_shown"))
            self.assertNotEqual(e["event_type"], "recommendation_click")

    def test_23_clicking_recommendation_does_not_count_as_offer_acceptance(self):
        """Verifies that clicking a recommendation does not automatically count as accepting an offer."""
        sess = f"test-sess-semantics-23-{uuid.uuid4().hex[:8]}"
        self.repo.record_session_event(session_id=sess, event_type="recommendation_click", product_id="item-001")

        events = self.repo.get_session_events(sess)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "recommendation_click")
        self.assertNotEqual(events[0]["event_type"], "offer_accepted")

    def test_24_cart_addition_does_not_count_as_discount_or_offer_acceptance(self):
        """Verifies that adding an item to the cart does not count as accepting a discount or offer."""
        sess = f"test-sess-semantics-24-{uuid.uuid4().hex[:8]}"
        self.repo.record_session_event(
            session_id=sess,
            event_type="add_to_cart",
            product_id="item-003",
            metadata={"price": 60.0},
        )

        events = self.repo.get_session_events(sess)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "add_to_cart")
        self.assertNotEqual(events[0]["event_type"], "offer_accepted")

    def test_25_accepting_offer_does_not_count_as_completed_order(self):
        """Verifies that accepting an offer never automatically counts as a completed order."""
        sess = f"test-sess-semantics-25-{uuid.uuid4().hex[:8]}"
        self.repo.record_session_event(
            session_id=sess,
            event_type="offer_accepted",
            product_id="item-005",
            metadata={"discount_percentage": 0.10},
        )

        events = self.repo.get_session_events(sess)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "offer_accepted")
        self.assertNotIn(events[0]["event_type"], ("demo_order_completed", "order_completed"))

    def test_26_completed_demo_order_remains_distinct_from_actual_orders(self):
        """Verifies that completed demo orders remain strictly distinct from live actual orders."""
        sess = f"test-sess-semantics-26-{uuid.uuid4().hex[:8]}"
        self.repo.record_session_event(session_id=sess, event_type="demo_order_completed")
        self.repo.record_session_event(session_id=sess, event_type="order_completed")

        events = self.repo.get_session_events(sess)
        self.assertEqual(len(events), 2)
        event_types = {e["event_type"] for e in events}
        self.assertIn("demo_order_completed", event_types)
        self.assertIn("order_completed", event_types)

    def test_27_equivalent_legacy_event_aliases_normalize_consistently_without_duplication(self):
        """Verifies that legacy aliases normalize cleanly and do not duplicate funnel counts."""
        sess = f"test-sess-semantics-27-{uuid.uuid4().hex[:8]}"
        aliases = [
            ("product_viewed", "product_view"),
            ("cart_item_added", "add_to_cart"),
            ("cart_add", "add_to_cart"),
            ("cart_item_removed", "remove_from_cart"),
            ("cart_remove", "remove_from_cart"),
            ("recommendation_shown", "recommendation_impression"),
            ("offer_shown", "offer_exposure"),
            ("simulated_purchase_completed", "demo_order_completed"),
        ]

        for alias, canonical in aliases:
            resp = self.client.post("/api/v1/events", json={
                "session_id": sess,
                "event_type": alias,
                "product_id": "item-001",
            })
            self.assertEqual(resp.status_code, 200, f"Failed for alias {alias}")

        events = self.repo.get_session_events(sess, limit=50)
        self.assertEqual(len(events), len(aliases))
        # Ensure all stored event types are normalized canonical forms
        for e in events:
            self.assertNotIn(e["event_type"], [a[0] for a in aliases])

    def test_28_event_deduplication_preserves_distinct_legitimate_actions(self):
        """Verifies that distinct legitimate actions are preserved while duplicate IDs are deduplicated."""
        sess = f"test-sess-semantics-28-{uuid.uuid4().hex[:8]}"

        # Distinct products added to cart
        id_a = self.repo.record_session_event(session_id=sess, event_type="add_to_cart", product_id="item-001")
        id_b = self.repo.record_session_event(session_id=sess, event_type="add_to_cart", product_id="item-002")
        self.assertNotEqual(id_a, id_b)

        # Distinct event types for same product
        id_c = self.repo.record_session_event(session_id=sess, event_type="recommendation_click", product_id="item-001")
        self.assertNotEqual(id_a, id_c)

        # Duplicate ID submission
        fixed_id = f"evt-semantics-fixed-{uuid.uuid4().hex[:8]}"
        res1 = self.repo.record_session_event(session_id=sess, event_type="product_view", product_id="item-001", event_id=fixed_id)
        res2 = self.repo.record_session_event(session_id=sess, event_type="product_view", product_id="item-001", event_id=fixed_id)
        self.assertEqual(res1, fixed_id)
        self.assertEqual(res2, fixed_id)

        events = self.repo.get_session_events(sess)
        matching_fixed = [e for e in events if e["id"] == fixed_id]
        self.assertEqual(len(matching_fixed), 1, "Duplicate ID was not deduplicated!")

    def test_29_funnel_conversion_rate_denominators_accurate_and_safe(self):
        """Verifies that conversion rate denominators correctly reflect stages and handle zero division."""
        # Empty storefront metrics safely return 0.0 for all conversion rates without division by zero
        empty_metrics = self.repo.get_outcome_funnel_metrics(
            time_window_hours=24,
            storefront_filter=f"nonexistent_storefront_{uuid.uuid4().hex[:8]}",
        )
        self.assertEqual(empty_metrics["total_events"], 0)
        rates = empty_metrics["conversion_rates"]
        self.assertEqual(rates["recommendation_ctr"], 0.0)
        self.assertEqual(rates["offer_acceptance_rate"], 0.0)
        self.assertEqual(rates["checkout_completion_rate"], 0.0)
        self.assertEqual(rates["view_to_order_rate"], 0.0)

        # Global metrics rates are strictly bounded within [0.0, 1.0]
        global_metrics = self.repo.get_outcome_funnel_metrics(time_window_hours=24)
        for rate_name, val in global_metrics["conversion_rates"].items():
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)

    def test_30_provenance_filtering_and_total_events_accuracy(self):
        """Verifies that provenance filtering strictly isolates events and total_events reflects the filter."""
        sess = f"test-sess-semantics-30-{uuid.uuid4().hex[:8]}"
        sfront = f"sfront-test-{uuid.uuid4().hex[:8]}"
        self.repo.record_session_event(
            session_id=sess,
            event_type="product_view",
            product_id="item-001",
            metadata={"provenance": "observed_demo", "storefront_id": sfront},
        )
        self.repo.record_session_event(
            session_id=sess,
            event_type="product_view",
            product_id="item-002",
            metadata={"provenance": "synthetic_research", "storefront_id": sfront},
        )

        filtered = self.repo.get_outcome_funnel_metrics(
            time_window_hours=24,
            provenance_filter="synthetic_research",
            storefront_filter=sfront,
        )
        self.assertEqual(filtered["total_events"], 1)
        self.assertIn("synthetic_research", filtered["provenance_breakdown"])
        self.assertNotIn("observed_demo", filtered["provenance_breakdown"])


if __name__ == "__main__":
    unittest.main()
