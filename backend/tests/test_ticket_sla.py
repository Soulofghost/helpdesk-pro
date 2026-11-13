import datetime
import pytest
from backend.app.engine.ticket_sla import (
    calculate_sla_deadlines,
    auto_route_technician,
    evaluate_sla_state,
    validate_ticket_transition,
    SLA_POLICY
)

def test_calculate_sla_deadlines():
    start = datetime.datetime(2026, 11, 13, 10, 0, 0, tzinfo=datetime.timezone.utc)
    
    # Critical: 1h response, 4h resolution
    resp_iso, res_iso = calculate_sla_deadlines("CRITICAL", start)
    resp_dt = datetime.datetime.fromisoformat(resp_iso)
    res_dt = datetime.datetime.fromisoformat(res_iso)

    assert (resp_dt - start).total_seconds() == 3600
    assert (res_dt - start).total_seconds() == 4 * 3600

    # Low: 8h response, 72h resolution
    resp_iso_low, res_iso_low = calculate_sla_deadlines("LOW", start)
    res_dt_low = datetime.datetime.fromisoformat(res_iso_low)
    assert (res_dt_low - start).total_seconds() == 72 * 3600

def test_auto_route_technician():
    # Security category
    tech, tier = auto_route_technician("Security & IAM", "HIGH")
    assert "Alex Rivera" in tech
    assert "Tier 2" in tier

    # Critical priority always escalates to Tier 3 Lead
    tech_crit, tier_crit = auto_route_technician("Software & Applications", "CRITICAL")
    assert "Critical Response" in tier_crit

def test_evaluate_sla_state():
    base = datetime.datetime(2026, 11, 13, 12, 0, 0, tzinfo=datetime.timezone.utc)
    deadline = base + datetime.timedelta(hours=4)
    deadline_iso = deadline.isoformat()

    # 1. Healthy: 3 hours remaining
    eval_healthy = evaluate_sla_state(deadline_iso, "OPEN", now=base + datetime.timedelta(hours=1))
    assert eval_healthy["sla_state"] == "HEALTHY"
    assert eval_healthy["is_breached"] is False

    # 2. At Risk: 30 minutes remaining
    eval_risk = evaluate_sla_state(deadline_iso, "IN_PROGRESS", now=base + datetime.timedelta(hours=3, minutes=30))
    assert eval_risk["sla_state"] == "AT_RISK"
    assert eval_risk["is_breached"] is False

    # 3. Breached: 10 minutes past deadline
    eval_breached = evaluate_sla_state(deadline_iso, "IN_PROGRESS", now=base + datetime.timedelta(hours=4, minutes=10))
    assert eval_breached["sla_state"] == "BREACHED"
    assert eval_breached["is_breached"] is True

    # 4. Resolved on time
    eval_met = evaluate_sla_state(
        deadline_iso, "RESOLVED",
        resolved_at_iso=(base + datetime.timedelta(hours=2)).isoformat(),
        now=base + datetime.timedelta(hours=5)
    )
    assert eval_met["sla_state"] == "MET"
    assert eval_met["is_breached"] is False

def test_validate_ticket_transition():
    # Valid transition
    ok, _ = validate_ticket_transition("OPEN", "IN_PROGRESS")
    assert ok is True

    # Resolution requires root cause
    ok, reason = validate_ticket_transition("IN_PROGRESS", "RESOLVED", root_cause=None)
    assert ok is False
    assert "root-cause" in reason

    ok, _ = validate_ticket_transition("IN_PROGRESS", "RESOLVED", root_cause="Replaced faulty transceivers")
    assert ok is True

    # Invalid jump
    ok, _ = validate_ticket_transition("OPEN", "RESOLVED")
    assert ok is False
