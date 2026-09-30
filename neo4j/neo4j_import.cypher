// InvoiceFactoringGuard - Neo4j import guide
// Load CSVs into Neo4j's import directory, then run these statements.

CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.company_id IS UNIQUE;
CREATE CONSTRAINT lender_id IF NOT EXISTS FOR (l:Lender) REQUIRE l.lender_id IS UNIQUE;
CREATE CONSTRAINT invoice_id IF NOT EXISTS FOR (i:Invoice) REQUIRE i.invoice_id IS UNIQUE;
CREATE CONSTRAINT financing_id IF NOT EXISTS FOR (f:FinancingRecord) REQUIRE f.financing_id IS UNIQUE;
CREATE CONSTRAINT eway_bill_no IF NOT EXISTS FOR (e:DeliveryProof) REQUIRE e.eway_bill_no IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///data/companies.csv' AS row
MERGE (c:Company {company_id: row.company_id})
SET c.name=row.company_name, c.gstin=row.gstin, c.state=row.state, c.industry=row.industry;

LOAD CSV WITH HEADERS FROM 'file:///data/lenders.csv' AS row
MERGE (l:Lender {lender_id: row.lender_id})
SET l.name=row.lender_name, l.type=row.lender_type;

LOAD CSV WITH HEADERS FROM 'file:///data/invoices.csv' AS row
MERGE (i:Invoice {invoice_id: row.invoice_id})
SET i.amount=toFloat(row.net_amount), i.invoice_date=row.invoice_date, i.due_date=row.due_date;

LOAD CSV WITH HEADERS FROM 'file:///data/invoices.csv' AS row
MATCH (i:Invoice {invoice_id: row.invoice_id})
MATCH (s:Company {company_id: row.seller_id})
MATCH (b:Company {company_id: row.buyer_id})
SET s:SELLER, b:BUYER
MERGE (s)-[:SELLS]->(i)
MERGE (i)-[:BILLED_TO]->(b);

LOAD CSV WITH HEADERS FROM 'file:///data/financing_records.csv' AS row
MATCH (i:Invoice {invoice_id: row.invoice_id})
MATCH (l:Lender {lender_id: row.lender_id})
MERGE (f:FinancingRecord {financing_id: row.financing_id})
SET f.amount=toFloat(row.financed_amount), f.date=row.application_date,
    f.status=row.status, f.product_type=row.product_type
MERGE (i)-[:ENCUMBERED_BY]->(f)
MERGE (f)-[:HELD_BY]->(l)
MERGE (i)-[r:FINANCED_BY {financing_id: row.financing_id}]->(l)
SET r.amount=toFloat(row.financed_amount), r.date=row.application_date, r.status=row.status;

LOAD CSV WITH HEADERS FROM 'file:///data/eway_bills.csv' AS row
MATCH (i:Invoice {invoice_id: row.invoice_id})
MERGE (e:DeliveryProof {eway_bill_no: row.eway_bill_no})
SET e.status=row.delivery_status, e.hash=row.delivery_proof_hash,
    e.seller_gstin=row.seller_gstin, e.buyer_gstin=row.buyer_gstin,
    e.origin_state=row.origin_state, e.destination_state=row.destination_state,
    e.movement_date=row.movement_date, e.transporter_id=row.transporter_id
MERGE (i)-[:HAS_DELIVERY_PROOF]->(e);

// Find invoices financed by multiple lenders.
MATCH (i:Invoice)-[:FINANCED_BY]->(l:Lender)
WITH i, collect(l) AS lenders
WHERE size(lenders) > 1
RETURN i.invoice_id AS invoice, [x IN lenders | x.name] AS lenders;

// Find the core double-financing pattern.
MATCH (s:Company)-[:SELLS]->(i:Invoice)-[:FINANCED_BY]->(l1:Lender),
      (i)-[:FINANCED_BY]->(l2:Lender)
WHERE l1 <> l2
RETURN s.name AS seller, i.invoice_id AS invoice,
       l1.name AS lender_1, l2.name AS lender_2;
