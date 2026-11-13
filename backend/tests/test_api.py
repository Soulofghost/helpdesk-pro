import pytest
from fastapi.testclient import TestClient
import backend.app.database as db_mod
import backend.app.config as cfg_mod
from backend.app.main import app

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    test_db_dir = tmp_path_factory.mktemp("db")
    test_db = str(test_db_dir / "test_helpdesk.db")

    cfg_mod.DB_PATH = test_db
    db_mod.DB_PATH = test_db

    holding_conn = db_mod.init_db(test_db)

    with TestClient(app) as c:
        yield c

    holding_conn.close()

def test_healthcheck(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["service"] == "HelpDesk Pro"

def test_create_and_manage_ticket_lifecycle(client):
    # 1. Create a Critical incident
    res = client.post("/api/tickets", json={
        "title": "PostgreSQL Replica Node Replication Lag Spike",
        "description": "Database replica lag exceeded 60 seconds triggering customer read timeouts.",
        "category": "Software & Applications",
        "priority": "CRITICAL",
        "requester_name": "DevOps Site Reliability Engineer",
        "requester_email": "sre@enterprise.internal"
    })
    assert res.status_code == 201
    data = res.json()
    ticket_id = data["id"]
    assert data["ticket_number"].startswith("HDK-")
    assert data["status"] == "OPEN"
    assert "Critical Response" in data["escalation_tier"]

    # 2. List tickets
    list_res = client.get("/api/tickets?priority=CRITICAL")
    assert list_res.status_code == 200
    crit_tickets = list_res.json()["tickets"]
    assert any(t["id"] == ticket_id for t in crit_tickets)

    # 3. Add Technician Comment (updates first response time)
    comm_res = client.post(f"/api/tickets/{ticket_id}/comments", json={
        "author": "Alex Rivera",
        "author_role": "SecOps Lead",
        "message": "Investigating WAL replication stream and network bandwidth allocation.",
        "is_internal": False
    })
    assert comm_res.status_code == 201

    # 4. Status update to IN_PROGRESS
    prog_res = client.patch(f"/api/tickets/{ticket_id}/status", json={
        "status": "IN_PROGRESS",
        "actor": "Alex Rivera",
        "comment": "Re-synchronizing database buffer pools."
    })
    assert prog_res.status_code == 200
    assert prog_res.json()["new_status"] == "IN_PROGRESS"

    # 5. Resolve ticket with root cause
    resolve_res = client.patch(f"/api/tickets/{ticket_id}/status", json={
        "status": "RESOLVED",
        "root_cause": "Disk I/O saturation on replica due to runaway analytics batch job.",
        "actor": "Alex Rivera"
    })
    assert resolve_res.status_code == 200
    assert resolve_res.json()["new_status"] == "RESOLVED"

    # 6. Fetch ticket details
    detail_res = client.get(f"/api/tickets/{ticket_id}")
    assert detail_res.status_code == 200
    details = detail_res.json()
    assert details["status"] == "RESOLVED"
    assert len(details["comments"]) >= 1
    assert len(details["events"]) >= 3
    assert details["responded_at"] is not None

def test_sla_analytics(client):
    res = client.get("/api/analytics/sla-metrics")
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["total_tickets"] >= 4
    assert "CRITICAL" in metrics["by_priority"]
    assert "sla_compliance_percentage" in metrics
