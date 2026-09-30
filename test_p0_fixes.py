"""Test P0 Fixes for InvoiceFactoringGuard."""
import requests
import time
import json

BASE_URL = "http://localhost:8000/api"

def test_invoice_detail():
    """Test P0 Issue #2: Invoice detail endpoint."""
    print("\n" + "="*60)
    print("TEST: Invoice Detail Endpoint (P0 Issue #2)")
    print("="*60)
    
    # Test with a known invoice ID
    test_ids = ["INV-2026-1001", "INV-2026-1002", "INV-2026-1003"]
    
    for inv_id in test_ids:
        try:
            print(f"\nTesting GET /api/invoices/{inv_id}")
            response = requests.get(f"{BASE_URL}/invoices/{inv_id}", timeout=5)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS - Invoice ID: {data.get('invoice_id')}")
                print(f"   Seller: {data.get('seller_name')} ({data.get('seller_gstin')})")
                print(f"   Buyer: {data.get('buyer_name')} ({data.get('buyer_gstin')})")
                print(f"   Amount: ₹{data.get('net_amount'):,.2f}")
                print(f"   Line items: {len(data.get('line_items', []))}")
                print(f"   Financing records: {len(data.get('financing_records', []))}")
            elif response.status_code == 404:
                print(f"⚠️  NOT FOUND (expected for invalid IDs)")
            else:
                print(f"❌ FAILED - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")

def test_graph_endpoint():
    """Test P0 Issue #1: Graph endpoint."""
    print("\n" + "="*60)
    print("TEST: Graph Endpoint (P0 Issue #1)")
    print("="*60)
    
    test_ids = ["INV-2026-1001", "INV-2026-1002", "INV-2026-1003"]
    
    for inv_id in test_ids:
        try:
            print(f"\nTesting GET /api/invoices/{inv_id}/graph")
            response = requests.get(f"{BASE_URL}/invoices/{inv_id}/graph", timeout=5)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS")
                print(f"   Nodes: {len(data.get('nodes', []))}")
                print(f"   Edges: {len(data.get('edges', []))}")
                print(f"   Suspicious nodes: {len(data.get('suspicious_node_ids', []))}")
                print(f"   Suspicious edges: {len(data.get('suspicious_edge_ids', []))}")
                
                # Sample a few node types
                node_types = {}
                for node in data.get('nodes', []):
                    ntype = node.get('type', 'unknown')
                    node_types[ntype] = node_types.get(ntype, 0) + 1
                print(f"   Node types: {node_types}")
            elif response.status_code == 404:
                print(f"⚠️  NOT FOUND (expected for invalid IDs)")
            else:
                print(f"❌ FAILED - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")

def test_verification():
    """Test the verification endpoint with multiple scenarios."""
    print("\n" + "="*60)
    print("TEST: Verification Endpoint (Full Risk Engine)")
    print("="*60)
    
    test_ids = ["INV-2026-1001", "INV-2026-1002"]
    
    for inv_id in test_ids:
        try:
            print(f"\nTesting POST /api/invoices/{inv_id}/verify")
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/invoices/{inv_id}/verify", timeout=10)
            elapsed_ms = (time.time() - start_time) * 1000
            
            print(f"Status: {response.status_code}")
            print(f"Response time: {elapsed_ms:.1f} ms")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS")
                print(f"   Risk Score: {data.get('risk_score')}/100")
                print(f"   Risk Level: {data.get('risk_level')}")
                print(f"   Recommended Action: {data.get('recommended_action')}")
                print(f"   Lender Count: {data.get('lender_count')}")
                print(f"   Duplicate Detected: {data.get('duplicate_detected')}")
                print(f"   Verification Time: {data.get('verification_time_ms')} ms")
                
                # Count triggered signals
                triggered = sum(1 for s in data.get('signals', []) if s.get('triggered'))
                print(f"   Signals triggered: {triggered}/{len(data.get('signals', []))}")
                
                # Show evidence count
                print(f"   Evidence items: {len(data.get('evidence', []))}")
            else:
                print(f"❌ FAILED - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")

def main():
    print("\n" + "#"*60)
    print("# InvoiceFactoringGuard - P0 Fixes Validation")
    print("#"*60)
    print("\nWaiting for backend to be ready...")
    
    # Wait for backend
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL.replace('/api', '')}/health", timeout=2)
            if response.status_code == 200:
                print("✅ Backend is ready!")
                break
        except Exception:
            if i < max_retries - 1:
                print(f"   Retry {i+1}/{max_retries}...")
                time.sleep(2)
            else:
                print("❌ Backend is not responding. Please start it with: python backend/main.py")
                return
    
    # Run tests
    test_invoice_detail()
    test_graph_endpoint()
    test_verification()
    
    print("\n" + "#"*60)
    print("# Test Suite Complete")
    print("#"*60)

if __name__ == "__main__":
    main()
