#!/usr/bin/env python
"""Quick test for P0 fixes."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

print("="*60)
print("P0 Test #1: Invoice Detail Endpoint")
print("="*60)
r = client.get("/api/invoices/INV-2026-02970")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"✅ Invoice ID: {data['invoice_id']}")
    print(f"✅ Seller: {data['seller_name']}")
    print(f"✅ Financing records: {len(data['financing_records'])}")
else:
    print(f"❌ Failed: {r.text[:100]}")

print("\n" + "="*60)
print("P0 Test #2: Graph Endpoint")
print("="*60)
r = client.get("/api/invoices/INV-2026-02970/graph")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"✅ Nodes: {len(data['nodes'])}")
    print(f"✅ Edges: {len(data['edges'])}")
else:
    print(f"❌ Failed: {r.text[:100]}")

print("\n" + "="*60)
print("P0 Test #3: Verification (Risk Engine)")
print("="*60)
r = client.post("/api/invoices/INV-2026-02970/verify")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"✅ Risk Score: {data['risk_score']}/100")
    print(f"✅ Risk Level: {data['risk_level']}")
    print(f"✅ Lender Count: {data['lender_count']}")
else:
    print(f"❌ Failed: {r.text[:100]}")

print("\n" + "="*60)
print("TESTS COMPLETE")
print("="*60)
