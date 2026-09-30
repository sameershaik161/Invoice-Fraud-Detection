"""Simple test script for P0 fixes - runs in backend environment."""
import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

print("\n" + "="*70)
print("P0 FIX TEST: Invoice Detail Endpoint")
print("="*70)

# Test invoice detail with the demo invoice
test_ids = ["INV-2026-02970", "INV-2026-1001", "INV-2026-1002"]

for inv_id in test_ids:
    print(f"\nTesting GET /api/invoices/{inv_id}")
    try:
        response = client.get(f"/api/invoices/{inv_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS - Invoice: {data['invoice_id']}")
            print(f"   Seller: {data['seller_name']}")
            print(f"   Buyer: {data['buyer_name']}")
            print(f"   Amount: ₹{data['net_amount']:,.2f}")
            print(f"   Line items: {len(data['line_items'])}")
            print(f"   Financing records: {len(data['financing_records'])}")
        elif response.status_code == 404:
            print(f"⚠️  NOT FOUND")
        else:
            print(f"❌ FAILED")
            print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {e}")

print("\n" + "="*70)
print("P0 FIX TEST: Graph Endpoint")
print("="*70)

for inv_id in test_ids[:2]:  # Test with first two
    print(f"\nTesting GET /api/invoices/{inv_id}/graph")
    try:
        response = client.get(f"/api/invoices/{inv_id}/graph")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS")
            print(f"   Nodes: {len(data['nodes'])}")
            print(f"   Edges: {len(data['edges'])}")
            print(f"   Suspicious nodes: {len(data['suspicious_node_ids'])}")
            
            # Count node types
            node_types = {}
            for node in data['nodes']:
                ntype = node['type']
                node_types[ntype] = node_types.get(ntype, 0) + 1
            print(f"   Node types: {node_types}")
        elif response.status_code == 404:
            print(f"⚠️  NOT FOUND")
        else:
            print(f"❌ FAILED")
            print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {e}")

print("\n" + "="*70)
print("P0 FIX TEST: Verification with Risk Engine")
print("="*70)

test_id = "INV-2026-02970"  # Demo invoice
print(f"\nTesting POST /api/invoices/{test_id}/verify")
try:
    response = client.post(f"/api/invoices/{test_id}/verify")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS")
        print(f"   Risk Score: {data['risk_score']}/100")
        print(f"   Risk Level: {data['risk_level']}")
        print(f"   Recommended Action: {data['recommended_action']}")
        print(f"   Lender Count: {data['lender_count']}")
        print(f"   Duplicate Detected: {data['duplicate_detected']}")
        print(f"   Verification Time: {data['verification_time_ms']} ms")
        
        # Show triggered signals
        triggered = [s['name'] for s in data['signals'] if s['triggered']]
        print(f"   Triggered signals ({len(triggered)}):")
        for sig in triggered:
            print(f"      - {sig}")
        
        print(f"   Evidence items: {len(data['evidence'])}")
    else:
        print(f"❌ FAILED")
        print(f"   Error: {response.text[:200]}")
except Exception as e:
    print(f"❌ EXCEPTION: {type(e).__name__}: {e}")

print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)
print("P0 Issue #1 (Graph endpoint): Check results above")
print("P0 Issue #2 (Invoice detail): Check results above")
print("="*70)
