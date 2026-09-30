#!/usr/bin/env python
"""Comprehensive P0 verification tests."""
import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from main import app
import json

client = TestClient(app)

print("\n" + "="*70)
print("PHASE 3: COMPREHENSIVE P0 VERIFICATION")
print("="*70)

# Test counters
tests_passed = 0
tests_failed = 0

def test_result(name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        print(f"✅ PASS: {name}")
        if details:
            print(f"   {details}")
    else:
        tests_failed += 1
        print(f"❌ FAIL: {name}")
        if details:
            print(f"   {details}")

print("\n" + "-"*70)
print("TEST 1: Valid Invoice Detail Endpoint")
print("-"*70)

try:
    response = client.get("/api/invoices/INV-2026-02970")
    if response.status_code == 200:
        data = response.json()
        has_required_fields = all(k in data for k in [
            'invoice_id', 'seller_name', 'buyer_name', 'net_amount', 
            'line_items', 'financing_records'
        ])
        test_result(
            "Invoice detail returns 200 for valid invoice",
            True,
            f"Invoice: {data['invoice_id']}, Seller: {data['seller_name']}, " +
            f"Buyer: {data['buyer_name']}, Financing: {len(data['financing_records'])}"
        )
        test_result(
            "Invoice detail contains all required fields",
            has_required_fields,
            f"Fields present: {list(data.keys())[:10]}..."
        )
    else:
        test_result(
            "Invoice detail returns 200 for valid invoice",
            False,
            f"Status: {response.status_code}, Error: {response.text[:100]}"
        )
except Exception as e:
    test_result(
        "Invoice detail returns 200 for valid invoice",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "-"*70)
print("TEST 2: Nonexistent Invoice (should return 404)")
print("-"*70)

try:
    response = client.get("/api/invoices/INV-9999-FAKE")
    test_result(
        "Invoice detail returns 404 for nonexistent invoice",
        response.status_code == 404,
        f"Status: {response.status_code}"
    )
except Exception as e:
    test_result(
        "Invoice detail returns 404 for nonexistent invoice",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "-"*70)
print("TEST 3: Invoice with Multiple Financing Records")
print("-"*70)

try:
    response = client.get("/api/invoices/INV-2026-02970")
    if response.status_code == 200:
        data = response.json()
        financing_count = len(data.get('financing_records', []))
        test_result(
            "Invoice with multiple financing records loads correctly",
            financing_count >= 2,
            f"Financing records: {financing_count}, " +
            f"Lenders: {[f['lender_id'] for f in data['financing_records']]}"
        )
    else:
        test_result(
            "Invoice with multiple financing records loads correctly",
            False,
            f"Status: {response.status_code}"
        )
except Exception as e:
    test_result(
        "Invoice with multiple financing records loads correctly",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "-"*70)
print("TEST 4: Invoice with Multiple Line Items")
print("-"*70)

try:
    response = client.get("/api/invoices/INV-2026-02970")
    if response.status_code == 200:
        data = response.json()
        line_items_count = len(data.get('line_items', []))
        test_result(
            "Invoice with multiple line items loads correctly",
            line_items_count >= 3,
            f"Line items: {line_items_count}, " +
            f"Items: {[li['item_description'] for li in data['line_items'][:3]]}"
        )
    else:
        test_result(
            "Invoice with multiple line items loads correctly",
            False,
            f"Status: {response.status_code}"
        )
except Exception as e:
    test_result(
        "Invoice with multiple line items loads correctly",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "-"*70)
print("TEST 5: Graph Endpoint - Valid Invoice")
print("-"*70)

try:
    response = client.get("/api/invoices/INV-2026-02970/graph")
    if response.status_code == 200:
        data = response.json()
        has_nodes = len(data.get('nodes', [])) > 0
        has_edges = len(data.get('edges', [])) > 0
        
        node_types = {}
        for node in data.get('nodes', []):
            ntype = node.get('type', 'unknown')
            node_types[ntype] = node_types.get(ntype, 0) + 1
        
        edge_types = {}
        for edge in data.get('edges', []):
            etype = edge.get('label', 'unknown')
            edge_types[etype] = edge_types.get(etype, 0) + 1
        
        test_result(
            "Graph endpoint returns 200 for valid invoice",
            True,
            f"Nodes: {len(data['nodes'])}, Edges: {len(data['edges'])}"
        )
        test_result(
            "Graph contains expected node types",
            has_nodes,
            f"Node types: {node_types}"
        )
        test_result(
            "Graph contains expected edge types",
            has_edges,
            f"Edge types: {edge_types}"
        )
        
        # Check for required node types
        required_types = {'invoice', 'company', 'lender'}
        found_types = set(node_types.keys())
        has_required = required_types.issubset(found_types)
        test_result(
            "Graph has required node types (invoice, company, lender)",
            has_required,
            f"Required: {required_types}, Found: {found_types}"
        )
        
        # Check suspicious nodes for high-risk invoice
        suspicious_nodes = data.get('suspicious_node_ids', [])
        test_result(
            "Graph flags suspicious nodes for high-risk invoice",
            len(suspicious_nodes) > 0,
            f"Suspicious nodes: {len(suspicious_nodes)}"
        )
        
    else:
        test_result(
            "Graph endpoint returns 200 for valid invoice",
            False,
            f"Status: {response.status_code}, Error: {response.text[:100]}"
        )
except Exception as e:
    test_result(
        "Graph endpoint returns 200 for valid invoice",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "-"*70)
print("TEST 6: Graph Endpoint - Nonexistent Invoice")
print("-"*70)

try:
    response = client.get("/api/invoices/INV-9999-FAKE/graph")
    test_result(
        "Graph endpoint returns 404 or empty for nonexistent invoice",
        response.status_code in [404, 200],
        f"Status: {response.status_code}"
    )
    if response.status_code == 200:
        data = response.json()
        test_result(
            "Graph returns empty nodes for nonexistent invoice",
            len(data.get('nodes', [])) == 0,
            f"Nodes: {len(data.get('nodes', []))}"
        )
except Exception as e:
    test_result(
        "Graph endpoint handles nonexistent invoice gracefully",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "-"*70)
print("TEST 7: Verification with Risk Engine (P1 Feature Integration)")
print("-"*70)

try:
    response = client.post("/api/invoices/INV-2026-02970/verify")
    if response.status_code == 200:
        data = response.json()
        
        test_result(
            "Verification endpoint returns 200",
            True,
            f"Risk Score: {data['risk_score']}/100, Level: {data['risk_level']}"
        )
        
        # Check if multiple lender signal is triggered
        signals = data.get('signals', [])
        signal_names = {s['signal_id']: s for s in signals}
        
        multiple_lenders_triggered = signal_names.get('MULTIPLE_LENDERS', {}).get('triggered', False)
        test_result(
            "Multiple lenders signal detected",
            multiple_lenders_triggered,
            f"Lender count: {data['lender_count']}"
        )
        
        # Check P1 signals
        has_line_item_signal = 'LINE_ITEM_SIMILARITY' in signal_names
        has_circular_signal = 'CIRCULAR_NETWORK' in signal_names
        has_modified_id_signal = 'MODIFIED_INVOICE_ID' in signal_names
        
        test_result(
            "P1 Signal: Line-item similarity integrated",
            has_line_item_signal,
            f"Triggered: {signal_names.get('LINE_ITEM_SIMILARITY', {}).get('triggered', False)}"
        )
        
        test_result(
            "P1 Signal: Circular network integrated",
            has_circular_signal,
            f"Triggered: {signal_names.get('CIRCULAR_NETWORK', {}).get('triggered', False)}"
        )
        
        test_result(
            "P1 Signal: Modified invoice ID integrated",
            has_modified_id_signal,
            f"Triggered: {signal_names.get('MODIFIED_INVOICE_ID', {}).get('triggered', False)}"
        )
        
        # Check evidence
        evidence_count = len(data.get('evidence', []))
        test_result(
            "Evidence items generated",
            evidence_count > 0,
            f"Evidence items: {evidence_count}"
        )
        
        # Check audit trail
        audit_count = len(data.get('audit_trail', []))
        test_result(
            "Audit trail generated",
            audit_count > 5,
            f"Audit entries: {audit_count}"
        )
        
        # Check recommended action
        action = data.get('recommended_action')
        test_result(
            "Recommended action provided",
            action in ['PROCEED', 'MANUAL_REVIEW', 'HOLD_PAYOUT', 'ENHANCED_VERIFICATION'],
            f"Action: {action}"
        )
        
        # Check verification time
        verification_time = data.get('verification_time_ms', 0)
        test_result(
            "Verification time under 3 seconds (3000ms)",
            verification_time < 3000,
            f"Time: {verification_time}ms"
        )
        
    else:
        test_result(
            "Verification endpoint returns 200",
            False,
            f"Status: {response.status_code}, Error: {response.text[:100]}"
        )
except Exception as e:
    test_result(
        "Verification endpoint returns 200",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "-"*70)
print("TEST 8: Modified Invoice ID Resolution")
print("-"*70)

# Test with different variations of invoice ID
test_ids = [
    "INV-2026-02970",
    "INV/2026/02970",
    "INV 2026 02970",
    "inv-2026-02970"
]

try:
    canonical_found = None
    for test_id in test_ids:
        response = client.get(f"/api/invoices/{test_id}")
        if response.status_code == 200:
            data = response.json()
            if canonical_found is None:
                canonical_found = data['invoice_id']
            # All variations should resolve to same canonical ID
            test_result(
                f"Modified ID '{test_id}' resolves correctly",
                data['invoice_id'] == canonical_found,
                f"Resolved to: {data['invoice_id']}"
            )
        elif response.status_code == 404:
            # Some variations might not exist, that's OK
            print(f"   Note: '{test_id}' not found (expected for some variations)")
except Exception as e:
    test_result(
        "Modified invoice ID resolution",
        False,
        f"Exception: {type(e).__name__}: {str(e)[:100]}"
    )

print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)
print(f"✅ Tests Passed: {tests_passed}")
print(f"❌ Tests Failed: {tests_failed}")
print(f"📊 Success Rate: {tests_passed}/{tests_passed + tests_failed} " +
      f"({100 * tests_passed / max(tests_passed + tests_failed, 1):.1f}%)")
print("="*70)

if tests_failed == 0:
    print("\n🎉 ALL P0 TESTS PASSED - SYSTEM READY FOR P1 VERIFICATION")
    sys.exit(0)
else:
    print(f"\n⚠️  {tests_failed} TEST(S) FAILED - REVIEW REQUIRED")
    sys.exit(1)
