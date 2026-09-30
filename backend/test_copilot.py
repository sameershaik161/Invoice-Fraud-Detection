"""Runtime tests for the read-only AI Investigation Copilot API."""
from __future__ import annotations

import unittest
import json
from unittest.mock import patch
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from main import app
from services.llm_provider import GeminiAdapter, LLMProvider, LLMResult, ProviderAdapter


class _TestAdapter(ProviderAdapter):
    def __init__(self, name: str, result: str | None = None, fail: bool = False):
        super().__init__("test-key", "test-model")
        self.name = name
        self.result = result
        self.fail = fail

    def generate(self, system: str, prompt: str, json_mode: bool = False) -> str:
        if self.fail:
            raise RuntimeError("provider unavailable")
        return self.result or "{}"


class CopilotEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def ask(self, message: str, **extra):
        return self.client.post("/api/copilot/chat", json={"message": message, **extra})

    def test_basic_system_question_uses_grounded_fallback(self):
        response = self.ask("What does this system detect?")
        self.assertEqual(response.status_code, 200)
        self.assertIn("duplicate financing", response.json()["answer"].lower())
        self.assertFalse(response.json()["llm_used"])

    def test_invoice_risk_uses_live_risk_engine(self):
        response = self.ask("Why is INV-2026-02970 risky?")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        risk = next(item for item in payload["findings"] if item["kind"] == "risk")
        self.assertEqual(payload["invoice_id"], "INV-2026-02970")
        self.assertEqual(risk["value"]["score"], 80)
        self.assertEqual(risk["value"]["level"], "CRITICAL")
        self.assertTrue(any(item.get("source_type") == "Risk Engine" for item in payload["evidence"]))

    def test_financing_and_delivery_queries_return_current_records(self):
        financing = self.ask("Who financed it?", invoice_id="INV-2026-02970").json()
        delivery = self.ask("Show delivery proof", invoice_id="INV-2026-02970").json()
        financing_finding = next(item for item in financing["findings"] if item["kind"] == "financing")
        delivery_finding = next(item for item in delivery["findings"] if item["kind"] == "delivery")
        self.assertEqual(len(financing_finding["value"]), 2)
        self.assertEqual(delivery_finding["value"]["delivery_status"], "DELIVERED")

    def test_gstin_activity_includes_risk_engine_lender_pattern(self):
        response = self.ask("Check GSTIN activity", invoice_id="INV-2026-02970")
        self.assertEqual(response.status_code, 200)
        finding = next(item for item in response.json()["findings"] if item["kind"] == "gstin")
        self.assertIn("9 lenders", finding["detail"])

    def test_delivery_reuse_question_includes_hash_collision_evidence(self):
        response = self.ask("Is the delivery proof reused?", invoice_id="INV-2026-02970")
        self.assertEqual(response.status_code, 200)
        finding = next(item for item in response.json()["findings"] if item["kind"] == "delivery")
        self.assertIn("matches another invoice", finding["detail"])

    def test_circular_network_uses_existing_graph_tools(self):
        response = self.ask("Is there a circular network?", invoice_id="INV-2026-02970")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        network = next(item for item in payload["findings"] if item["kind"] == "network")
        self.assertGreater(network["value"]["edges"], 0)
        self.assertIn("detect_circular_network", payload["tools"])

    def test_modified_invoice_id_is_resolved(self):
        response = self.ask("INV202602970")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["invoice_id"], "INV-2026-02970")
        self.assertIn("modified_invoice_id", payload["intents"])

    def test_line_item_query_returns_matcher_result(self):
        response = self.ask("Find matching line items", invoice_id="INV-2026-02970")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("line_item_matching", payload["intents"])
        self.assertTrue(any(item["kind"] == "line_items" for item in payload["findings"]))

    def test_investigation_summary_gathers_and_exports_verified_report(self):
        response = self.ask("Generate an investigation summary", invoice_id="INV-2026-02970")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("get_invoice_timeline", payload["tools"])
        self.assertIn("detect_circular_network", payload["tools"])
        self.assertIn("INV-2026-02970", payload["report_text"])
        self.assertIn("CRITICAL", payload["report_text"])
        self.assertIn("LND013", payload["report_text"])
        self.assertIn("DELIVERED", payload["report_text"])
        timeline = next(item["value"] for item in payload["findings"] if item["kind"] == "timeline")
        dated_events = [event["date"] for event in timeline if len(event["date"]) == 10]
        self.assertEqual(dated_events, sorted(dated_events))

    def test_company_network_is_bounded_and_data_backed(self):
        response = self.ask("Who is connected to CMP0836?")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        network = next(item for item in payload["findings"] if item["kind"] == "network")
        self.assertLessEqual(len(network["value"]["links"]), 20)
        self.assertIn("get_company_network", payload["tools"])

    def test_company_context_followup_resolves_lenders(self):
        response = self.ask("Who finances companies connected to this seller?", context_entity_id="CMP0836", context_entity_type="company")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        network = next(item for item in payload["findings"] if item["kind"] == "network")
        self.assertTrue(network["value"]["lender_ids"])
        self.assertIn("get_company_network", payload["tools"])

    def test_report_endpoint_returns_real_attachment(self):
        response = self.client.get("/api/copilot/report", params={"invoice_id": "INV-2026-02970"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response.headers["content-disposition"])
        self.assertIn("INV-2026-02970-investigation-report.txt", response.headers["content-disposition"])
        self.assertGreater(len(response.content), 500)
        self.assertIn(b"LND013", response.content)
        self.assertIn(b"DELIVERED", response.content)

    def test_provider_fallback_chain_and_intent_allowlist(self):
        primary = _TestAdapter("primary", fail=True)
        fallback = _TestAdapter("fallback", json.dumps({"intents": ["risk_analysis", "DROP"]}))
        provider = LLMProvider([primary, fallback])
        plan, selected = provider.plan("Why risky?", "INV-2026-02970", [])
        self.assertEqual(plan, ["risk_analysis"])
        self.assertEqual(selected, "fallback")

    def test_llm_claims_require_valid_evidence_citations(self):
        class FakeProvider:
            configured = True
            provider_names = ["mock"]

            def plan(self, *_args):
                return [], "mock"

            def generate(self, _system, prompt, json_mode=False):
                payload = json.loads(prompt)
                ref_id = payload["evidence"][0]["ref_id"]
                return LLMResult(json.dumps({"claims": [{"text": "Verified invoice investigation.", "evidence_refs": [ref_id]}]}), "mock")

        with patch("services.copilot_service.build_llm_provider", return_value=FakeProvider()):
            response = self.ask("Why is INV-2026-02970 risky?")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["llm_used"])
        self.assertIn("[E1]", payload["answer"])

    def test_llm_planner_can_select_only_allowlisted_tools(self):
        class FakeProvider:
            configured = True
            provider_names = ["mock"]

            def plan(self, *_args):
                return ["risk_analysis", "DELETE"], "mock"

            def generate(self, _system, prompt, json_mode=False):
                evidence = json.loads(prompt)["evidence"]
                return LLMResult(json.dumps({"claims": [{"text": "Risk information was retrieved.", "evidence_refs": [evidence[0]["ref_id"]]}]}), "mock")

        with patch("services.copilot_service.build_llm_provider", return_value=FakeProvider()):
            response = self.ask("Explain this", invoice_id="INV-2026-02970")
        payload = response.json()
        self.assertIn("get_invoice_risk", payload["tools"])
        self.assertNotIn("DELETE", payload["intents"])

    def test_provider_status_is_evidence_mode_without_keys(self):
        response = self.client.get("/api/copilot/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "Evidence Mode")
        self.assertFalse(response.json()["configured"])

    def test_gemini_adapter_keeps_key_in_server_request_header(self):
        response = MagicMock()
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        with patch("services.llm_provider.httpx.post", return_value=response) as post:
            adapter = GeminiAdapter("server-only-key", "gemini-test", "https://example.test/v1beta")
            self.assertEqual(adapter.generate("system", "prompt"), "ok")
        args, kwargs = post.call_args
        self.assertIn("generateContent", args[0])
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "server-only-key")
        self.assertNotIn("key", kwargs.get("params", {}))

    def test_invalid_entity_context_is_rejected(self):
        response = self.ask("Who finances it?", context_entity_id="DROP ALL", context_entity_type="company")
        self.assertEqual(response.status_code, 422)

    def test_contextual_follow_up_uses_prior_invoice(self):
        response = self.ask(
            "Who financed it?",
            history=[{"role": "user", "content": "Investigate INV-2026-02970"}],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["invoice_id"], "INV-2026-02970")

    def test_invalid_invoice_and_unknown_question_do_not_invent_data(self):
        missing = self.ask("Why is INV-2099-99999 risky?").json()
        unknown = self.ask("Tell me a joke").json()
        self.assertIn("couldn't find verified data", missing["answer"].lower())
        self.assertIn("couldn't find verified data", unknown["answer"].lower())
        self.assertEqual(missing["findings"], [])

    def test_verification_unknown_invoice_returns_404_not_low_risk(self):
        response = self.client.post("/api/invoices/INV-2099-99999/verify")
        self.assertEqual(response.status_code, 404)

    def test_overview_does_not_fabricate_verifications_today(self):
        response = self.client.get("/api/analytics/overview")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["verified_today"])

    def test_arbitrary_cypher_and_write_attempt_are_rejected_without_tools(self):
        for query in ("MATCH (n) RETURN n", "MATCH (n) DETACH DELETE n", "CREATE (n:Invoice)"):
            with self.subTest(query=query):
                response = self.ask(query)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["tools"], [])
                self.assertEqual(payload["fallback_reason"], "unsafe_query_rejected")

    def test_neo4j_failure_keeps_csv_answer_available(self):
        with patch("services.copilot_service.build_invoice_graph", side_effect=RuntimeError("offline")):
            response = self.ask("Show the company network", invoice_id="INV-2026-02970")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["kind"] == "network" and item["title"] == "Graph unavailable" for item in payload["findings"]))
        self.assertTrue(any(item["kind"] == "invoice" for item in payload["findings"]))

    def test_request_limits_reject_oversized_input(self):
        response = self.ask("x" * 1201)
        self.assertEqual(response.status_code, 422)

    def test_live_invoice_ingestion_and_duplicate_detection(self):
        test_id = "INV-DEMO-NEW-001"
        payload = {
            "invoice_id": test_id,
            "invoice_date": "2026-10-01",
            "invoice_amount": 245000.0,
            "currency": "INR",
            "invoice_type": "PURCHASE",
            "invoice_description": "Demo product batch",
            "seller_company_id": "CMP0001",
            "seller_company_name": "Apex Suppliers 0001 Pvt Ltd",
            "seller_gstin": "36JI0Y6DPBHS1ZA",
            "buyer_company_id": "CMP0002",
            "buyer_company_name": "Green Solutions 0002 Pvt Ltd",
            "buyer_gstin": "33HV3A3ZMF8M1ZC",
            "financing": [{
                "lender_id": "LND010",
                "financing_amount": 220000.0,
                "financing_date": "2026-10-01",
                "financing_status": "APPROVED",
            }],
            "delivery": {
                "eway_bill_no": "EWB-DEMO-NEW-001",
                "delivery_status": "GENERATED",
                "delivery_date": "2026-10-02",
                "additional_metadata": "demo",
            },
            "line_items": [{
                "description": "Hydraulic Pump",
                "hsn_code": "8413",
                "quantity": 5,
                "unit_price": 12000,
                "total_amount": 60000,
            }],
            "allow_similar": True,
        }

        check = self.client.post("/api/invoices/check-duplicate", json=payload)
        self.assertEqual(check.status_code, 200)
        self.assertIn(check.json()["result"], {"NO_SIGNIFICANT_MATCH", "SIMILAR_INVOICE", "POSSIBLE_DUPLICATE"})

        create = self.client.post("/api/invoices", json=payload)
        self.assertEqual(create.status_code, 200)
        self.assertEqual(create.json()["status"], "INVOICE_CREATED")
        self.assertEqual(create.json()["invoice_id"], test_id)

        duplicate = self.client.post("/api/invoices/check-duplicate", json=payload)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["result"], "EXACT_DUPLICATE")


if __name__ == "__main__":
    unittest.main()
