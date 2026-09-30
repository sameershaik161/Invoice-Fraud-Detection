# InvoiceFactoringGuard

> **Detect Duplicate Financing. Explain the Risk. Protect Working Capital.**

An explainable multi-lender invoice intelligence and double-financing prevention platform built for Hackzen 2026 Problem Statement #21.

---

## Problem

An MSME may submit the same invoice to multiple lenders, receiving financing against the same receivable from each — creating a "double-financing" fraud risk.

```
Invoice INV-1024
Seller: ABC Pvt Ltd → Buyer: XYZ Industries → Amount: ₹10,00,000

               ┌── Lender A → ₹8,00,000
Invoice ───────┤
               └── Lender B → ₹8,00,000   ← RISK
```

## Solution

A multi-signal, explainable risk intelligence platform that:
1. **Detects** duplicate financing across lenders
2. **Explains** exactly why an invoice was flagged
3. **Visualizes** the relationship graph between seller, buyer, invoice and lenders
4. **Recommends** a concrete action (Proceed / Review / Hold)
5. **Audits** every verification step with timestamps

---

## Architecture

```
Frontend (React/Vite/TS)
      ↕  REST API
Backend (FastAPI/Python)
      ↕  Pandas in-memory
Dataset (CSV files)
      ↕  optional
Neo4j (Graph DB)
```

### Risk Engine — 6 Signals

| Signal | Weight |
|--------|--------|
| Multiple lenders | +30 |
| Invoice content similarity (TF-IDF) | +25 |
| Seller GSTIN multi-lender pattern | +15 |
| Delivery proof hash collision | +10 |
| Financing timing overlap (≤14 days) | +10 |
| High-value invoice + multi-lender | +10 |

**Risk Levels:** LOW (0–29) | MEDIUM (30–59) | HIGH (60–79) | CRITICAL (80–100)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, TypeScript, Tailwind CSS |
| Visualization | React Flow (graph), Recharts (charts) |
| Animation | Framer Motion |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Similarity | scikit-learn TF-IDF + cosine similarity |
| Data | Pandas (in-memory CSV) |
| Graph DB | Neo4j 5 (optional) |
| Icons | Lucide React |

---

## Dataset

> **IMPORTANT:** This is **synthetic hackathon data**. Not real banking, GST, lender, or customer data.

Files in `data/`:
- `companies.csv` — 1,001 companies with GSTIN, state, industry
- `lenders.csv` — 25 lenders
- `invoices.csv` — 5,001 invoices
- `invoice_line_items.csv` — ~126k line items
- `financing_records.csv` — ~5,800 financing records
- `eway_bills.csv` — ~5,081 e-way bills
- `fraud_labels.csv` — ground truth (NORMAL / DOUBLE_FINANCING)
- `risk_features.csv` — pre-computed risk scores

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/api/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

### Neo4j (optional)

```bash
docker run -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.20-community
```

Set `NEO4J_ENABLED=true` in `.env`.

### Docker Compose (all services)

```bash
docker-compose up
```

---

## Environment Variables

Copy `.env.example` to `.env`:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_ENABLED=false
DEBUG=true
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health check |
| GET | `/api/invoices` | List invoices (filterable) |
| GET | `/api/invoices/{id}` | Invoice detail |
| POST | `/api/invoices/{id}/verify` | **Run full risk verification** |
| GET | `/api/invoices/{id}/risk` | Risk result |
| GET | `/api/invoices/{id}/graph` | Entity relationship graph |
| GET | `/api/lenders` | Lender list with stats |
| GET | `/api/analytics/overview` | Dashboard KPIs |
| GET | `/api/analytics/charts` | Chart data |
| GET | `/api/demo/invoice` | Demo invoice ID |

---

## Demo Instructions

1. Start backend and frontend
2. Navigate to **Invoice Verification**
3. Click **"Demo"** to load `INV-2026-02970`
4. Click **"Verify Invoice"**
5. Watch the step-by-step verification sequence
6. See the **CRITICAL RISK** result with evidence
7. Click **"View Graph"** to see the lender relationship
8. Open **Audit Trail**

Expected result:
- Risk Score: ~85/100
- Risk Level: HIGH / CRITICAL
- Duplicate Financing: DETECTED
- Recommended Action: HOLD PAYOUT

---

## Future Scope

- Real e-Way Bill API validation
- GST portal integration
- Real-time streaming (Kafka)
- Graph embeddings + GNN fraud detection
- Temporal graph analysis
- Production authentication (OAuth2)
- Enterprise audit logging

---

> InvoiceFactoringGuard assists lenders and auditors with explainable risk detection.
> It does not claim 100% fraud detection and is designed as a human-in-the-loop system.
