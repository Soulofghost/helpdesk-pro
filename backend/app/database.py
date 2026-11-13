import sqlite3
import datetime
import uuid
from typing import Optional
from backend.app.config import DB_PATH
from backend.app.engine.ticket_sla import calculate_sla_deadlines, auto_route_technician

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    if not path.startswith(":memory:") and "mode=memory" not in path:
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[str] = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        ticket_number TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        requester_name TEXT NOT NULL,
        requester_email TEXT NOT NULL,
        assigned_agent TEXT DEFAULT 'Unassigned',
        escalation_tier TEXT DEFAULT 'Tier 1 General Support',
        created_at TEXT NOT NULL,
        response_deadline TEXT NOT NULL,
        resolution_deadline TEXT NOT NULL,
        responded_at TEXT,
        resolved_at TEXT,
        closed_at TEXT,
        root_cause TEXT DEFAULT ''
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ticket_comments (
        id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL,
        author TEXT NOT NULL,
        author_role TEXT NOT NULL,
        message TEXT NOT NULL,
        is_internal INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ticket_events (
        id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        details TEXT NOT NULL,
        actor TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
    );
    """)

    # Seed initial tickets if empty
    cursor.execute("SELECT COUNT(*) FROM tickets;")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now(datetime.timezone.utc)
        
        seeds = [
            (
                "HDK-1001",
                "Core Gateway Packet Loss & Border Router Instability",
                "Network & Infrastructure",
                "CRITICAL",
                "OPEN",
                "DevOps Infrastructure Team",
                "devops@enterprise.internal",
                "Alex Rivera (SecOps Lead)",
                "Tier 3 Critical Response Team",
                now - datetime.timedelta(minutes=30),
            ),
            (
                "HDK-1002",
                "Okta SSO SAML 2.0 Identity Federation Failure",
                "Security & IAM",
                "HIGH",
                "IN_PROGRESS",
                "Human Resources Operations",
                "hr-ops@enterprise.internal",
                "Alex Rivera (SecOps)",
                "Tier 2 Infrastructure & Ops",
                now - datetime.timedelta(hours=2),
            ),
            (
                "HDK-1003",
                "Engineering Laptop SSD Read Fault - Kernel Panic",
                "Hardware & Devices",
                "MEDIUM",
                "ASSIGNED",
                "David Miller (Platform Architect)",
                "d.miller@enterprise.internal",
                "Elena Rostova (Hardware Tech)",
                "Tier 1 General Support",
                now - datetime.timedelta(hours=5),
            ),
            (
                "HDK-1004",
                "Internal Jira License Assignment Provisioning",
                "General & Access",
                "LOW",
                "RESOLVED",
                "Finance Department",
                "finance-desk@enterprise.internal",
                "Sarah Connor (Service Desk)",
                "Tier 1 General Support",
                now - datetime.timedelta(hours=20),
            )
        ]

        for num, title, cat, prio, stat, req_name, req_email, tech, tier, created_dt in seeds:
            t_id = str(uuid.uuid4())
            resp_dl, res_dl = calculate_sla_deadlines(prio, created_dt)
            res_at = (created_dt + datetime.timedelta(hours=3)).isoformat() if stat == "RESOLVED" else None
            root_c = "User provisioned with Atlassian Cloud Enterprise seat." if stat == "RESOLVED" else ""

            cursor.execute("""
            INSERT INTO tickets (
                id, ticket_number, title, description, category, priority, status,
                requester_name, requester_email, assigned_agent, escalation_tier,
                created_at, response_deadline, resolution_deadline, resolved_at, root_cause
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                t_id, num, title, f"Detailed incident report for: {title}",
                cat, prio, stat, req_name, req_email, tech, tier,
                created_dt.isoformat(), resp_dl, res_dl, res_at, root_c
            ))

            # Add creation event
            cursor.execute("""
            INSERT INTO ticket_events (id, ticket_id, event_type, details, actor, created_at)
            VALUES (?, ?, 'TICKET_CREATED', 'Ticket initialized via monitoring automation', ?, ?);
            """, (str(uuid.uuid4()), t_id, req_name, created_dt.isoformat()))

    conn.commit()
    return conn
