"""
Graph service — builds a React Flow compatible graph for any invoice.
Falls back to a mock graph when Neo4j is unavailable (NEO4J_ENABLED=False).
"""
from __future__ import annotations

import logging
from fastapi import HTTPException
from neo4j import GraphDatabase

import data_store
from config import settings
from schemas.schemas import GraphNodeSchema, GraphEdgeSchema, GraphResponseSchema

log = logging.getLogger(__name__)
_NEO4J_DRIVER = None


def _get_neo4j_driver():
    global _NEO4J_DRIVER
    if _NEO4J_DRIVER is None:
        _NEO4J_DRIVER = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _NEO4J_DRIVER


def initialize_neo4j() -> bool:
    if not settings.NEO4J_ENABLED:
        return False
    try:
        driver = _get_neo4j_driver()
        driver.verify_connectivity()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("RETURN 1").consume()
        log.info("Connected to Neo4j database %s", settings.NEO4J_DATABASE)
        return True
    except Exception:
        log.exception("Neo4j is enabled but unavailable")
        return False


def neo4j_is_connected() -> bool:
    if not settings.NEO4J_ENABLED:
        return False
    try:
        with _get_neo4j_driver().session(database=settings.NEO4J_DATABASE) as session:
            session.run("RETURN 1").consume()
        return True
    except Exception:
        return False


def close_neo4j() -> None:
    global _NEO4J_DRIVER
    if _NEO4J_DRIVER is not None:
        _NEO4J_DRIVER.close()
        _NEO4J_DRIVER = None


def insert_invoice_graph_record(invoice_data: dict, financing_rows: list[dict] | None = None, delivery_data: dict | None = None, line_items: list[dict] | None = None) -> None:
    if not settings.NEO4J_ENABLED:
        return
    financing_rows = financing_rows or []
    line_items = line_items or []
    invoice_id = str(invoice_data.get("invoice_id", ""))
    logger = logging.getLogger(__name__)
    try:
        with _get_neo4j_driver().session(database=settings.NEO4J_DATABASE) as session:
            session.run(
                """
                MERGE (i:Invoice {invoice_id: $invoice_id})
                SET i.amount = toFloat($amount), i.invoice_date = $invoice_date, i.due_date = $due_date
                MERGE (s:Company {company_id: $seller_id})
                SET s.name = $seller_name, s.gstin = $seller_gstin, s.state = COALESCE(s.state, '')
                MERGE (b:Company {company_id: $buyer_id})
                SET b.name = $buyer_name, b.gstin = $buyer_gstin, b.state = COALESCE(b.state, '')
                MERGE (s)-[:SELLS]->(i)
                MERGE (i)-[:BILLED_TO]->(b)
                """,
                invoice_id=invoice_id,
                amount=float(invoice_data.get("net_amount") or 0),
                invoice_date=str(invoice_data.get("invoice_date") or ""),
                due_date=str(invoice_data.get("due_date") or ""),
                seller_id=str(invoice_data.get("seller_company_id") or ""),
                seller_name=str(invoice_data.get("seller_company_name") or invoice_data.get("seller_company_id") or ""),
                seller_gstin=str(invoice_data.get("seller_gstin") or ""),
                buyer_id=str(invoice_data.get("buyer_company_id") or ""),
                buyer_name=str(invoice_data.get("buyer_company_name") or invoice_data.get("buyer_company_id") or ""),
                buyer_gstin=str(invoice_data.get("buyer_gstin") or ""),
            ).consume()

            for financing in financing_rows:
                lender_id = str(financing.get("lender_id") or "")
                if not lender_id:
                    continue
                financing_id = str(financing.get("financing_id") or f"{invoice_id}_{lender_id}")
                session.run(
                    """
                    MERGE (l:Lender {lender_id: $lender_id})
                    SET l.name = $lender_name, l.type = COALESCE(l.type, 'COMMERCIAL')
                    MERGE (f:FinancingRecord {financing_id: $financing_id})
                    SET f.amount = toFloat($amount), f.date = $application_date, f.status = $status
                    MATCH (i:Invoice {invoice_id: $invoice_id})
                    MERGE (i)-[:ENCUMBERED_BY]->(f)
                    MERGE (f)-[:HELD_BY]->(l)
                    MERGE (i)-[r:FINANCED_BY {financing_id: $financing_id}]->(l)
                    SET r.amount = toFloat($amount), r.date = $application_date, r.status = $status
                    """,
                    lender_id=lender_id,
                    lender_name=lender_id,
                    financing_id=financing_id,
                    amount=float(financing.get("financed_amount") or 0),
                    application_date=str(financing.get("application_date") or ""),
                    status=str(financing.get("status") or "APPROVED"),
                    invoice_id=invoice_id,
                ).consume()

            if delivery_data and str(delivery_data.get("eway_bill_no") or ""):
                session.run(
                    """
                    MATCH (i:Invoice {invoice_id: $invoice_id})
                    MERGE (e:DeliveryProof {eway_bill_no: $eway_bill_no})
                    SET e.status = $delivery_status,
                        e.hash = $delivery_proof_hash,
                        e.seller_gstin = $seller_gstin,
                        e.buyer_gstin = $buyer_gstin,
                        e.movement_date = $movement_date
                    MERGE (i)-[:HAS_DELIVERY_PROOF]->(e)
                    """,
                    invoice_id=invoice_id,
                    eway_bill_no=str(delivery_data.get("eway_bill_no") or ""),
                    delivery_status=str(delivery_data.get("delivery_status") or "GENERATED"),
                    delivery_proof_hash=str(delivery_data.get("delivery_proof_hash") or ""),
                    seller_gstin=str(delivery_data.get("seller_gstin") or ""),
                    buyer_gstin=str(delivery_data.get("buyer_gstin") or ""),
                    movement_date=str(delivery_data.get("delivery_date") or ""),
                ).consume()
    except Exception as exc:
        logger.exception("Neo4j invoice insertion failed for %s", invoice_id)
        raise RuntimeError(f"Neo4j persistence failed: {exc}") from exc


def _make_node(nid: str, label: str, ntype: str, props: dict, risk_flag: bool = False) -> GraphNodeSchema:
    return GraphNodeSchema(id=nid, label=label, type=ntype, properties=props, risk_flag=risk_flag)


def _make_edge(eid: str, src: str, tgt: str, label: str, highlighted: bool = False) -> GraphEdgeSchema:
    return GraphEdgeSchema(id=eid, source=src, target=tgt, label=label, highlighted=highlighted)


_COMPANY_ADJ: dict[str, set[str]] = {}


def get_company_adjacency() -> dict[str, set[str]]:
    global _COMPANY_ADJ
    if not _COMPANY_ADJ:
        invoices_df = data_store.get("invoices")
        if not invoices_df.empty:
            for _, r in invoices_df.iterrows():
                s = str(r.get("seller_id", ""))
                b = str(r.get("buyer_id", ""))
                if s and b:
                    if s not in _COMPANY_ADJ:
                        _COMPANY_ADJ[s] = set()
                    _COMPANY_ADJ[s].add(b)
    return _COMPANY_ADJ


def detect_circular_network(seller_id: str, buyer_id: str, max_depth: int = 5) -> dict:
    """
    Identifies circular buyer-supplier trading loops (e.g. A -> B -> C -> A).
    Returns structured detection dict with cycle path, entities, and plain-language explanation.
    """
    if not seller_id or not buyer_id:
        return {"circular_network_detected": False, "cycle": [], "cycle_length": 0, "description": ""}

    if seller_id == buyer_id:
        return {
            "circular_network_detected": True,
            "cycle": [seller_id, buyer_id],
            "cycle_length": 1,
            "description": f"Self-trading loop detected: Company {seller_id} is both buyer and seller.",
        }

    if settings.NEO4J_ENABLED:
        try:
            depth = max(1, min(max_depth, 10)) * 2
            query = f"""
                MATCH (start:Company {{company_id: $buyer_id}})
                MATCH (finish:Company {{company_id: $seller_id}})
                MATCH path = shortestPath(
                    (start)-[:SELLS|BILLED_TO*1..{depth}]->(finish)
                )
                RETURN path
            """
            with _get_neo4j_driver().session(database=settings.NEO4J_DATABASE) as session:
                record = session.run(query, buyer_id=buyer_id, seller_id=seller_id).single()
            if record:
                path = record["path"]
                company_ids = [
                    str(dict(node)["company_id"])
                    for node in path.nodes
                    if "company_id" in node
                ]
                cycle = [seller_id, *company_ids]
                return {
                    "circular_network_detected": len(cycle) > 2,
                    "cycle": cycle,
                    "cycle_length": max(0, len(cycle) - 1),
                    "description": f"Circular buyer-supplier relationship detected across {len(cycle)-1} entities: {' -> '.join(cycle)}.",
                    "_path_nodes": list(path.nodes),
                    "_path_relationships": list(path.relationships),
                }
            return {"circular_network_detected": False, "cycle": [], "cycle_length": 0, "description": ""}
        except Exception as error:
            log.warning("Neo4j cycle lookup failed; retaining CSV detector: %s", error)

    adj = get_company_adjacency()

    # BFS from buyer_id to find shortest return path back to seller_id
    queue = [(buyer_id, [seller_id, buyer_id])]
    visited = {buyer_id}

    while queue:
        curr, path = queue.pop(0)
        if len(path) > max_depth + 1:
            continue
        for neighbor in adj.get(curr, ()):
            if neighbor == seller_id:
                full_cycle = path + [seller_id]
                return {
                    "circular_network_detected": True,
                    "cycle": full_cycle,
                    "cycle_length": len(full_cycle) - 1,
                    "description": f"Circular buyer-supplier relationship detected across {len(full_cycle)-1} entities: {' -> '.join(full_cycle)}."
                }
            if neighbor not in visited and len(path) <= max_depth:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return {"circular_network_detected": False, "cycle": [], "cycle_length": 0, "description": ""}


def _neo4j_node_id(node) -> str:
    properties = dict(node)
    if "invoice_id" in properties:
        return f"inv_{properties['invoice_id']}"
    if "eway_bill_no" in properties:
        return f"eway_{properties['eway_bill_no']}"
    if "company_id" in properties:
        return f"co_{properties['company_id']}"
    if "lender_id" in properties:
        return f"lnd_{properties['lender_id']}"
    if "financing_id" in properties:
        return f"fin_{properties['financing_id']}"
    return f"neo4j_{node.element_id}"


def _build_neo4j_invoice_graph(invoice_id: str) -> GraphResponseSchema:
    invoices_df = data_store.get("invoices")
    target_id = invoice_id
    if not invoices_df.empty and target_id not in invoices_df.index:
        from services.invoice_matcher import get_canonical_invoice_id
        canonical_id, _ = get_canonical_invoice_id(invoice_id)
        if canonical_id:
            target_id = canonical_id

    nodes: list[GraphNodeSchema] = []
    edges: list[GraphEdgeSchema] = []
    suspicious_nodes: set[str] = set()
    suspicious_edges: set[str] = set()
    node_indexes: dict[str, int] = {}

    def add_node(node, role: str = "", risk_flag: bool = False) -> str:
        properties = dict(node)
        labels = set(node.labels)
        node_id = _neo4j_node_id(node)
        if "Invoice" in labels:
            ntype = "invoice"
            label = str(properties.get("invoice_id", node_id))
            values = {
                "amount": f"₹{float(properties.get('amount', 0)):,.0f}",
                "date": str(properties.get("invoice_date", "")),
                "due_date": str(properties.get("due_date", "")),
            }
        elif "Lender" in labels:
            ntype = "lender"
            label = str(properties.get("name", properties.get("lender_id", node_id)))
            values = {"lender_id": str(properties.get("lender_id", "")), "type": str(properties.get("type", ""))}
        elif "FinancingRecord" in labels:
            ntype = "financing"
            label = f"Lien: {properties.get('financing_id', node_id)}"
            values = {
                "financing_id": str(properties.get("financing_id", "")),
                "amount": f"₹{float(properties.get('amount', 0)):,.0f}",
                "status": str(properties.get("status", "")),
            }
        elif "DeliveryProof" in labels:
            ntype = "eway"
            label = str(properties.get("eway_bill_no", node_id))
            values = {
                "hash": str(properties.get("hash", "")),
                "status": str(properties.get("status", "")),
                "origin": str(properties.get("origin_state", "")),
                "destination": str(properties.get("destination_state", "")),
                "movement_date": str(properties.get("movement_date", "")),
            }
        else:
            ntype = "company"
            label = str(properties.get("name", properties.get("company_id", node_id)))
            values = {
                "role": role or ("Seller" if "SELLER" in labels else "Buyer" if "BUYER" in labels else ""),
                "gstin": str(properties.get("gstin", "")),
                "company_id": str(properties.get("company_id", "")),
            }

        if node_id in node_indexes:
            index = node_indexes[node_id]
            if risk_flag and not nodes[index].risk_flag:
                nodes[index] = nodes[index].model_copy(update={"risk_flag": True})
        else:
            node_indexes[node_id] = len(nodes)
            nodes.append(_make_node(node_id, label, ntype, values, risk_flag=risk_flag))
        if risk_flag:
            suspicious_nodes.add(node_id)
        return node_id

    def add_edge(edge_id: str, source: str, target: str, label: str, props: dict | None = None, highlighted: bool = False) -> None:
        edges.append(GraphEdgeSchema(
            id=edge_id,
            source=source,
            target=target,
            label=label,
            properties=props or {},
            highlighted=highlighted,
        ))
        if highlighted:
            suspicious_edges.add(edge_id)

    try:
        with _get_neo4j_driver().session(database=settings.NEO4J_DATABASE) as session:
            core = session.run(
                """
                MATCH (i:Invoice {invoice_id: $invoice_id})
                OPTIONAL MATCH (s:Company)-[:SELLS]->(i)
                OPTIONAL MATCH (i)-[:BILLED_TO]->(b:Company)
                RETURN i, s, b LIMIT 1
                """,
                invoice_id=target_id,
            ).single()
            if not core:
                return GraphResponseSchema(nodes=[], edges=[], suspicious_node_ids=[], suspicious_edge_ids=[])

            invoice_node = add_node(core["i"])
            seller_node = add_node(core["s"], role="Seller") if core["s"] else None
            buyer_node = add_node(core["b"], role="Buyer") if core["b"] else None
            if seller_node:
                add_edge(f"e_sells_{target_id}", seller_node, invoice_node, "SELLS")
            if buyer_node:
                add_edge(f"e_billed_{target_id}", invoice_node, buyer_node, "BILLED_TO")

            financing_rows = list(session.run(
                """
                MATCH (i:Invoice {invoice_id: $invoice_id})
                OPTIONAL MATCH (i)-[r:FINANCED_BY]->(l:Lender)
                RETURN r, l ORDER BY r.financing_id
                """,
                invoice_id=target_id,
            ))
            financing_rows = [row for row in financing_rows if row["r"] and row["l"]]
            duplicate_financing = len(financing_rows) > 1
            for row in financing_rows:
                relation = dict(row["r"])
                lender_node = add_node(row["l"], risk_flag=duplicate_financing)
                financing_id = str(relation.get("financing_id", f"{target_id}_{len(edges)}"))
                record = session.run(
                    """
                    MATCH (f:FinancingRecord {financing_id: $financing_id})
                    RETURN f LIMIT 1
                    """,
                    financing_id=financing_id,
                ).single()
                if record:
                    record_node = add_node(record["f"], risk_flag=duplicate_financing)
                    add_edge(f"e_rec_{target_id}_{financing_id}", invoice_node, record_node, "ENCUMBERED_BY", highlighted=duplicate_financing)
                    lender_id = str(dict(row["l"]).get("lender_id", ""))
                    add_edge(f"e_held_{financing_id}_{lender_id}", record_node, lender_node, "HELD_BY", highlighted=duplicate_financing)
                add_edge(
                    f"e_fin_{target_id}_{financing_id}",
                    invoice_node,
                    lender_node,
                    "FINANCED_BY",
                    relation,
                    highlighted=duplicate_financing,
                )

            if duplicate_financing:
                suspicious_nodes.add(invoice_node)
                index = node_indexes[invoice_node]
                nodes[index] = nodes[index].model_copy(update={"risk_flag": True})

            for row in session.run(
                """
                MATCH (i:Invoice {invoice_id: $invoice_id})
                OPTIONAL MATCH (i)-[:HAS_DELIVERY_PROOF]->(e:DeliveryProof)
                RETURN e LIMIT 1
                """,
                invoice_id=target_id,
            ):
                if row["e"]:
                    proof_node = add_node(row["e"])
                    add_edge(f"e_eway_{target_id}", invoice_node, proof_node, "HAS_DELIVERY_PROOF")

            cycle_info = detect_circular_network(
                str(dict(core["s"]).get("company_id", "")) if core["s"] else "",
                str(dict(core["b"]).get("company_id", "")) if core["b"] else "",
            )
            if cycle_info.get("circular_network_detected"):
                cycle_start_edges = {f"e_sells_{target_id}", f"e_billed_{target_id}"}
                for index, edge in enumerate(edges):
                    if edge.id in cycle_start_edges:
                        edges[index] = edge.model_copy(update={"highlighted": True})
                        suspicious_edges.add(edge.id)
                suspicious_nodes.add(invoice_node)
                nodes[node_indexes[invoice_node]] = nodes[node_indexes[invoice_node]].model_copy(update={"risk_flag": True})
                for cycle_node in cycle_info.get("_path_nodes", []):
                    add_node(cycle_node, risk_flag=True)
                for relationship in cycle_info.get("_path_relationships", []):
                    source = _neo4j_node_id(relationship.start_node)
                    target = _neo4j_node_id(relationship.end_node)
                    add_edge(
                        f"e_cycle_{relationship.element_id}",
                        source,
                        target,
                        relationship.type,
                        dict(relationship),
                        highlighted=True,
                    )
                if seller_node:
                    suspicious_nodes.add(seller_node)
                    nodes[node_indexes[seller_node]] = nodes[node_indexes[seller_node]].model_copy(update={"risk_flag": True})
                if buyer_node:
                    suspicious_nodes.add(buyer_node)
                    nodes[node_indexes[buyer_node]] = nodes[node_indexes[buyer_node]].model_copy(update={"risk_flag": True})

    except Exception as error:
        log.exception("Neo4j invoice graph query failed")
        raise HTTPException(status_code=503, detail=f"Neo4j graph unavailable: {error}") from error

    return GraphResponseSchema(
        nodes=nodes,
        edges=edges,
        suspicious_node_ids=list(suspicious_nodes),
        suspicious_edge_ids=list(suspicious_edges),
    )


def build_invoice_graph(invoice_id: str) -> GraphResponseSchema:
    if settings.NEO4J_ENABLED:
        return _build_neo4j_invoice_graph(invoice_id)

    invoices_df = data_store.get("invoices")
    companies_df = data_store.get("companies")
    financing_df = data_store.get("financing")
    eway_df = data_store.get("eway_bills")
    lenders_df = data_store.get("lenders")

    nodes: list[GraphNodeSchema] = []
    edges: list[GraphEdgeSchema] = []
    suspicious_nodes: list[str] = []
    suspicious_edges: list[str] = []

    target_id = invoice_id
    if invoices_df.empty or target_id not in invoices_df.index:
        from services.invoice_matcher import get_canonical_invoice_id
        canonical_id, _ = get_canonical_invoice_id(invoice_id)
        if canonical_id and canonical_id in invoices_df.index:
            target_id = canonical_id
        else:
            return GraphResponseSchema(nodes=[], edges=[], suspicious_node_ids=[], suspicious_edge_ids=[])

    inv = invoices_df.loc[target_id]
    if hasattr(inv, "iloc") and len(inv.shape) > 1:
        inv = inv.iloc[0]

    seller_id = str(inv.get("seller_id", ""))
    buyer_id = str(inv.get("buyer_id", ""))
    net_amount = float(inv.get("net_amount", 0))

    # Invoice node
    inv_node_id = f"inv_{target_id}"
    nodes.append(_make_node(inv_node_id, target_id, "invoice", {
        "amount": f"₹{net_amount:,.0f}",
        "date": str(inv.get("invoice_date", "")),
        "due_date": str(inv.get("due_date", "")),
        "line_item": str(inv.get("primary_line_item", "")),
    }))

    # Seller node
    seller_name = seller_id
    seller_gstin = ""
    if not companies_df.empty and seller_id in companies_df.index:
        s = companies_df.loc[seller_id]
        if hasattr(s, "iloc") and len(s.shape) > 1:
            s = s.iloc[0]
        seller_name = str(s.get("company_name", seller_id))
        seller_gstin = str(s.get("gstin", ""))
    seller_node_id = f"co_{seller_id}"
    nodes.append(_make_node(seller_node_id, seller_name, "company", {
        "role": "Seller",
        "gstin": seller_gstin,
        "company_id": seller_id,
    }))
    edges.append(_make_edge(f"e_sells_{target_id}", seller_node_id, inv_node_id, "SELLS"))

    # Buyer node
    buyer_name = buyer_id
    buyer_gstin = ""
    if not companies_df.empty and buyer_id in companies_df.index:
        b = companies_df.loc[buyer_id]
        if hasattr(b, "iloc") and len(b.shape) > 1:
            b = b.iloc[0]
        buyer_name = str(b.get("company_name", buyer_id))
        buyer_gstin = str(b.get("gstin", ""))
    buyer_node_id = f"co_{buyer_id}"
    nodes.append(_make_node(buyer_node_id, buyer_name, "company", {
        "role": "Buyer",
        "gstin": buyer_gstin,
        "company_id": buyer_id,
    }))
    edges.append(_make_edge(f"e_billed_{target_id}", inv_node_id, buyer_node_id, "BILLED_TO"))

    # Financing / Lender / Encumbrance nodes
    inv_financing = financing_df[financing_df["invoice_id"] == target_id] if not financing_df.empty else None
    lender_count = 0
    if inv_financing is not None and not inv_financing.empty:
        lender_count = len(inv_financing)
        is_duplicate = lender_count > 1
        for i, (_, fin_row) in enumerate(inv_financing.iterrows()):
            fin_id = str(fin_row.get("financing_id", f"FIN_{target_id}_{i}"))
            lender_id = str(fin_row.get("lender_id", f"LND_UNK_{i}"))
            fin_amount = float(fin_row.get("financed_amount", 0))
            fin_status = str(fin_row.get("status", ""))
            lender_name = lender_id
            lender_type = ""
            if not lenders_df.empty:
                lmatch = lenders_df[lenders_df["lender_id"] == lender_id]
                if not lmatch.empty:
                    lender_name = str(lmatch.iloc[0].get("lender_name", lender_id))
                    lender_type = str(lmatch.iloc[0].get("lender_type", ""))

            lender_node_id = f"lnd_{lender_id}"
            nodes.append(_make_node(lender_node_id, lender_name, "lender", {
                "lender_id": lender_id,
                "type": lender_type,
                "financed_amount": f"₹{fin_amount:,.0f}",
                "status": fin_status,
                "application_date": str(fin_row.get("application_date", "")),
            }, risk_flag=is_duplicate))

            # Granular Financing Record node
            fin_node_id = f"fin_{fin_id}"
            nodes.append(_make_node(fin_node_id, f"Lien: {fin_id}", "financing", {
                "financing_id": fin_id,
                "amount": f"₹{fin_amount:,.0f}",
                "status": fin_status,
                "lender": lender_name,
            }, risk_flag=is_duplicate))

            # Edges: INVOICE -> FINANCING_RECORD -> LENDER
            rec_edge = _make_edge(f"e_rec_{target_id}_{fin_id}", inv_node_id, fin_node_id, "ENCUMBERED_BY", highlighted=is_duplicate)
            held_edge = _make_edge(f"e_held_{fin_id}_{lender_id}", fin_node_id, lender_node_id, "HELD_BY", highlighted=is_duplicate)
            edges.extend([rec_edge, held_edge])

            # Direct INVOICE -> LENDER FINANCED_BY edge for frontend compatibility
            edge_id = f"e_fin_{target_id}_{lender_id}"
            edge = _make_edge(edge_id, inv_node_id, lender_node_id, "FINANCED_BY", highlighted=is_duplicate)
            edges.append(edge)

            if is_duplicate:
                suspicious_nodes.extend([lender_node_id, fin_node_id])
                suspicious_edges.extend([edge_id, rec_edge.id, held_edge.id])

    if lender_count > 1:
        suspicious_nodes.append(inv_node_id)

    # E-Way Bill / Delivery proof node
    if not eway_df.empty:
        inv_eway = eway_df[eway_df["invoice_id"] == target_id]
        if not inv_eway.empty:
            ew = inv_eway.iloc[0]
            eway_node_id = f"eway_{ew['eway_bill_no']}"
            nodes.append(_make_node(eway_node_id, str(ew.get("eway_bill_no", "")), "eway", {
                "hash": str(ew.get("delivery_proof_hash", "")),
                "status": str(ew.get("delivery_status", "")),
                "origin": str(ew.get("origin_state", "")),
                "destination": str(ew.get("destination_state", "")),
                "movement_date": str(ew.get("movement_date", "")),
            }))
            edges.append(_make_edge(f"e_eway_{target_id}", inv_node_id, eway_node_id, "HAS_DELIVERY_PROOF"))

    # Circular network check (carousel trading pattern)
    cycle_info = detect_circular_network(seller_id, buyer_id)
    if cycle_info["circular_network_detected"] and len(cycle_info["cycle"]) >= 2:
        cycle_nodes = cycle_info["cycle"]
        # Add intermediate cycle nodes if not present
        existing_node_ids = {n.id for n in nodes}
        for i, c_id in enumerate(cycle_nodes[:-1]):
            c_node_id = f"co_{c_id}"
            next_c_id = cycle_nodes[i + 1]
            next_node_id = f"co_{next_c_id}"

            if c_node_id not in existing_node_ids:
                c_name = c_id
                if not companies_df.empty and c_id in companies_df.index:
                    cr = companies_df.loc[c_id]
                    if hasattr(cr, "iloc") and len(cr.shape) > 1:
                        cr = cr.iloc[0]
                    c_name = str(cr.get("company_name", c_id))
                nodes.append(_make_node(c_node_id, c_name, "company", {
                    "company_id": c_id,
                    "cycle_participant": "True"
                }, risk_flag=True))
                existing_node_ids.add(c_node_id)
                suspicious_nodes.append(c_node_id)

            # Add cycle flow edge
            cycle_edge_id = f"e_cycle_{c_id}_{next_c_id}"
            edges.append(_make_edge(cycle_edge_id, c_node_id, next_node_id, "CYCLE_FLOW", highlighted=True))
            suspicious_edges.append(cycle_edge_id)

    return GraphResponseSchema(
        nodes=nodes,
        edges=edges,
        suspicious_node_ids=list(set(suspicious_nodes)),
        suspicious_edge_ids=list(set(suspicious_edges)),
    )

