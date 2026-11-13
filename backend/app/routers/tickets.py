import uuid
import datetime
from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, List

from backend.app.database import get_connection
from backend.app.schemas import TicketCreate, TicketStatusUpdate, TicketAssign, CommentCreate
from backend.app.engine.ticket_sla import (
    calculate_sla_deadlines,
    auto_route_technician,
    evaluate_sla_state,
    validate_ticket_transition,
    SLA_POLICY
)

router = APIRouter(prefix="/api", tags=["tickets"])

@router.get("/health")
def healthcheck():
    return {"status": "ok", "service": "HelpDesk Pro", "version": "1.0.0"}

@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate):
    conn = get_connection()
    cursor = conn.cursor()

    # Determine next ticket number
    cursor.execute("SELECT COUNT(*) FROM tickets;")
    count = cursor.fetchone()[0]
    ticket_number = f"HDK-{1001 + count}"

    # Auto routing
    tech, tier = auto_route_technician(payload.category, payload.priority)

    # SLA deadlines
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    resp_dl, res_dl = calculate_sla_deadlines(payload.priority, now_dt)

    t_id = str(uuid.uuid4())
    now_iso = now_dt.isoformat()

    cursor.execute("""
    INSERT INTO tickets (
        id, ticket_number, title, description, category, priority, status,
        requester_name, requester_email, assigned_agent, escalation_tier,
        created_at, response_deadline, resolution_deadline, root_cause
    ) VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, '');
    """, (
        t_id, ticket_number, payload.title, payload.description,
        payload.category, payload.priority.upper(), payload.requester_name,
        payload.requester_email, tech, tier, now_iso, resp_dl, res_dl
    ))

    # Add creation event
    cursor.execute("""
    INSERT INTO ticket_events (id, ticket_id, event_type, details, actor, created_at)
    VALUES (?, ?, 'TICKET_CREATED', ?, ?, ?);
    """, (
        str(uuid.uuid4()), t_id,
        f"Incident logged with priority {payload.priority.upper()}. SLA target: {SLA_POLICY.get(payload.priority.upper(), {}).get('resolution_hours', 24)}h",
        payload.requester_name, now_iso
    ))

    conn.commit()
    conn.close()

    return {
        "id": t_id,
        "ticket_number": ticket_number,
        "title": payload.title,
        "category": payload.category,
        "priority": payload.priority.upper(),
        "status": "OPEN",
        "assigned_agent": tech,
        "escalation_tier": tier,
        "created_at": now_iso,
        "resolution_deadline": res_dl
    }

@router.get("/tickets")
def list_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM tickets WHERE 1=1"
    params = []

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter.upper())
    if priority:
        query += " AND priority = ?"
        params.append(priority.upper())
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (title LIKE ? OR ticket_number LIKE ? OR requester_name LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        sla_info = evaluate_sla_state(
            resolution_deadline_iso=r["resolution_deadline"],
            status=r["status"],
            resolved_at_iso=r["resolved_at"]
        )

        results.append({
            "id": r["id"],
            "ticket_number": r["ticket_number"],
            "title": r["title"],
            "category": r["category"],
            "priority": r["priority"],
            "status": r["status"],
            "requester_name": r["requester_name"],
            "requester_email": r["requester_email"],
            "assigned_agent": r["assigned_agent"],
            "escalation_tier": r["escalation_tier"],
            "created_at": r["created_at"],
            "response_deadline": r["response_deadline"],
            "resolution_deadline": r["resolution_deadline"],
            "resolved_at": r["resolved_at"],
            "sla": sla_info
        })

    return {"total": len(results), "tickets": results}

@router.get("/tickets/{ticket_id}")
def get_ticket_details(ticket_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tickets WHERE id = ? OR ticket_number = ?;", (ticket_id, ticket_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    real_id = row["id"]

    cursor.execute("SELECT * FROM ticket_comments WHERE ticket_id = ? ORDER BY created_at ASC;", (real_id,))
    comm_rows = cursor.fetchall()
    comments = [{
        "id": c["id"],
        "author": c["author"],
        "author_role": c["author_role"],
        "message": c["message"],
        "is_internal": bool(c["is_internal"]),
        "created_at": c["created_at"]
    } for c in comm_rows]

    cursor.execute("SELECT * FROM ticket_events WHERE ticket_id = ? ORDER BY created_at ASC;", (real_id,))
    ev_rows = cursor.fetchall()
    events = [{
        "id": e["id"],
        "event_type": e["event_type"],
        "details": e["details"],
        "actor": e["actor"],
        "created_at": e["created_at"]
    } for e in ev_rows]

    sla_info = evaluate_sla_state(
        resolution_deadline_iso=row["resolution_deadline"],
        status=row["status"],
        resolved_at_iso=row["resolved_at"]
    )

    conn.close()

    return {
        "id": row["id"],
        "ticket_number": row["ticket_number"],
        "title": row["title"],
        "description": row["description"],
        "category": row["category"],
        "priority": row["priority"],
        "status": row["status"],
        "requester_name": row["requester_name"],
        "requester_email": row["requester_email"],
        "assigned_agent": row["assigned_agent"],
        "escalation_tier": row["escalation_tier"],
        "created_at": row["created_at"],
        "response_deadline": row["response_deadline"],
        "resolution_deadline": row["resolution_deadline"],
        "responded_at": row["responded_at"],
        "resolved_at": row["resolved_at"],
        "root_cause": row["root_cause"],
        "sla": sla_info,
        "comments": comments,
        "events": events
    }

@router.patch("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: str, payload: TicketStatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tickets WHERE id = ? OR ticket_number = ?;", (ticket_id, ticket_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    real_id = row["id"]
    current_status = row["status"]

    valid, reason = validate_ticket_transition(current_status, payload.status, payload.root_cause)
    if not valid:
        conn.close()
        raise HTTPException(status_code=400, detail=reason)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    resolved_at = row["resolved_at"]
    closed_at = row["closed_at"]

    if payload.status.upper() == "RESOLVED":
        resolved_at = now_iso
    elif payload.status.upper() == "CLOSED":
        closed_at = now_iso

    cursor.execute("""
    UPDATE tickets SET
        status = ?,
        resolved_at = ?,
        closed_at = ?,
        root_cause = COALESCE(?, root_cause)
    WHERE id = ?;
    """, (payload.status.upper(), resolved_at, closed_at, payload.root_cause, real_id))

    # Event log
    cursor.execute("""
    INSERT INTO ticket_events (id, ticket_id, event_type, details, actor, created_at)
    VALUES (?, ?, 'STATUS_CHANGED', ?, ?, ?);
    """, (
        str(uuid.uuid4()), real_id,
        f"Status changed from {current_status} to {payload.status.upper()}. {payload.comment or ''}",
        payload.actor, now_iso
    ))

    conn.commit()
    conn.close()

    return {
        "id": real_id,
        "ticket_number": row["ticket_number"],
        "previous_status": current_status,
        "new_status": payload.status.upper(),
        "resolved_at": resolved_at
    }

@router.patch("/tickets/{ticket_id}/assign")
def assign_ticket(ticket_id: str, payload: TicketAssign):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tickets WHERE id = ? OR ticket_number = ?;", (ticket_id, ticket_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    real_id = row["id"]
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cursor.execute("""
    UPDATE tickets SET
        assigned_agent = ?,
        escalation_tier = COALESCE(?, escalation_tier)
    WHERE id = ?;
    """, (payload.assigned_agent, payload.escalation_tier, real_id))

    cursor.execute("""
    INSERT INTO ticket_events (id, ticket_id, event_type, details, actor, created_at)
    VALUES (?, ?, 'TECHNICIAN_REASSIGNED', ?, ?, ?);
    """, (
        str(uuid.uuid4()), real_id,
        f"Reassigned to {payload.assigned_agent} [{payload.escalation_tier or 'Unchanged'}]",
        payload.actor, now_iso
    ))

    conn.commit()
    conn.close()

    return {
        "id": real_id,
        "ticket_number": row["ticket_number"],
        "assigned_agent": payload.assigned_agent,
        "escalation_tier": payload.escalation_tier
    }

@router.post("/tickets/{ticket_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(ticket_id: str, payload: CommentCreate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, ticket_number, responded_at FROM tickets WHERE id = ? OR ticket_number = ?;", (ticket_id, ticket_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    real_id = row["id"]
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    comm_id = str(uuid.uuid4())

    cursor.execute("""
    INSERT INTO ticket_comments (id, ticket_id, author, author_role, message, is_internal, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        comm_id, real_id, payload.author, payload.author_role,
        payload.message, 1 if payload.is_internal else 0, now_iso
    ))

    # Mark first response time if unresponded and author is technician
    if not row["responded_at"] and payload.author_role != "Customer":
        cursor.execute("UPDATE tickets SET responded_at = ? WHERE id = ?;", (now_iso, real_id))

    cursor.execute("""
    INSERT INTO ticket_events (id, ticket_id, event_type, details, actor, created_at)
    VALUES (?, ?, 'COMMENT_ADDED', ?, ?, ?);
    """, (
        str(uuid.uuid4()), real_id,
        f"{'Internal Note' if payload.is_internal else 'Public Reply'} by {payload.author}",
        payload.author, now_iso
    ))

    conn.commit()
    conn.close()

    return {
        "id": comm_id,
        "ticket_id": real_id,
        "author": payload.author,
        "is_internal": payload.is_internal,
        "created_at": now_iso
    }

@router.get("/analytics/sla-metrics")
def get_sla_metrics():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tickets;")
    total_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status;")
    status_breakdown = {r[0]: r[1] for r in cursor.fetchall()}

    cursor.execute("SELECT priority, COUNT(*) FROM tickets GROUP BY priority;")
    priority_breakdown = {r[0]: r[1] for r in cursor.fetchall()}

    cursor.execute("SELECT category, COUNT(*) FROM tickets GROUP BY category;")
    category_breakdown = [{ "category": r[0], "count": r[1] } for r in cursor.fetchall()]

    # Real-time SLA analysis
    cursor.execute("SELECT resolution_deadline, status, resolved_at FROM tickets;")
    all_tickets = cursor.fetchall()
    conn.close()

    breached_count = 0
    met_count = 0

    for t in all_tickets:
        sla = evaluate_sla_state(t[0], t[1], t[2])
        if sla["sla_state"] == "BREACHED":
            breached_count += 1
        elif sla["sla_state"] == "MET":
            met_count += 1

    compliance_rate = round((met_count / max(1, met_count + breached_count)) * 100.0, 1)

    return {
        "total_tickets": total_tickets,
        "open_tickets": status_breakdown.get("OPEN", 0) + status_breakdown.get("ASSIGNED", 0) + status_breakdown.get("IN_PROGRESS", 0),
        "resolved_tickets": status_breakdown.get("RESOLVED", 0) + status_breakdown.get("CLOSED", 0),
        "breached_count": breached_count,
        "sla_compliance_percentage": compliance_rate,
        "by_priority": priority_breakdown,
        "by_status": status_breakdown,
        "by_category": category_breakdown
    }
