from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_search_endpoint_returns_invoice_results():
    response = client.get("/api/search", params={"q": "INV-2026-02970"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert "results" in payload
    assert payload["results"]
    assert any(item["type"] == "INVOICES" for item in payload["results"])


def test_alerts_endpoint_returns_real_risk_alerts():
    response = client.get("/api/alerts")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    first = payload[0]
    assert "invoice_id" in first
    assert "level" in first


def test_investigation_endpoint_returns_risk_and_timeline():
    response = client.get("/api/investigation/INV-2026-02970")
    assert response.status_code == 200
    payload = response.json()
    assert payload["invoice_id"] == "INV-2026-02970"
    assert "risk" in payload
    assert "timeline" in payload
    assert "evidence" in payload
    assert payload["risk"]["risk_score"] >= 80
