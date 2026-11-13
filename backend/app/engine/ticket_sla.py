"""
Enterprise ITSM SLA & Priority Escalation Engine
Calculates response/resolution deadlines, tracks countdowns, breach alerts, and queue routing.
"""

import datetime
from typing import Dict, Tuple, Optional

SLA_POLICY: Dict[str, Dict[str, float]] = {
    "CRITICAL": {
        "response_hours": 1.0,
        "resolution_hours": 4.0,
        "tier": "Tier 3 Critical Response Team",
    },
    "HIGH": {
        "response_hours": 2.0,
        "resolution_hours": 8.0,
        "tier": "Tier 2 Infrastructure & Ops",
    },
    "MEDIUM": {
        "response_hours": 4.0,
        "resolution_hours": 24.0,
        "tier": "Tier 1 General Support",
    },
    "LOW": {
        "response_hours": 8.0,
        "resolution_hours": 72.0,
        "tier": "Tier 1 General Support",
    },
}

CATEGORY_ROUTING: Dict[str, str] = {
    "Security & IAM": "Alex Rivera (SecOps)",
    "Network & Infrastructure": "Marcus Vance (NetOps)",
    "Hardware & Devices": "Elena Rostova (Hardware Tech)",
    "Software & Applications": "Liam Chen (SysAdmin)",
    "General & Access": "Sarah Connor (Service Desk)",
}

VALID_STATUSES = {"OPEN", "ASSIGNED", "IN_PROGRESS", "PENDING_CUSTOMER", "RESOLVED", "CLOSED"}

ALLOWED_STATUS_TRANSITIONS: Dict[str, set] = {
    "OPEN": {"ASSIGNED", "IN_PROGRESS", "CLOSED"},
    "ASSIGNED": {"IN_PROGRESS", "PENDING_CUSTOMER", "OPEN"},
    "IN_PROGRESS": {"PENDING_CUSTOMER", "RESOLVED", "ASSIGNED"},
    "PENDING_CUSTOMER": {"IN_PROGRESS", "RESOLVED"},
    "RESOLVED": {"CLOSED", "IN_PROGRESS"},
    "CLOSED": {"IN_PROGRESS"},
}


def calculate_sla_deadlines(priority: str, start_time: Optional[datetime.datetime] = None) -> Tuple[str, str]:
    """
    Computes ISO 8601 response and resolution deadlines based on incident priority.
    """
    priority = priority.upper()
    if priority not in SLA_POLICY:
        priority = "MEDIUM"

    policy = SLA_POLICY[priority]
    base_time = start_time or datetime.datetime.now(datetime.timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=datetime.timezone.utc)

    resp_deadline = base_time + datetime.timedelta(hours=policy["response_hours"])
    res_deadline = base_time + datetime.timedelta(hours=policy["resolution_hours"])

    return resp_deadline.isoformat(), res_deadline.isoformat()


def auto_route_technician(category: str, priority: str) -> Tuple[str, str]:
    """
    Determines recommended technician and escalation tier based on category and priority.
    """
    priority = priority.upper()
    policy = SLA_POLICY.get(priority, SLA_POLICY["MEDIUM"])
    tier = policy["tier"]

    # Critical priority always escalates to Lead SecOps/Infra
    if priority == "CRITICAL":
        return "Alex Rivera (SecOps Lead)", "Tier 3 Critical Response Team"

    technician = CATEGORY_ROUTING.get(category, "Sarah Connor (Service Desk)")
    return technician, tier


def evaluate_sla_state(
    resolution_deadline_iso: str,
    status: str,
    resolved_at_iso: Optional[str] = None,
    now: Optional[datetime.datetime] = None
) -> dict:
    """
    Evaluates real-time SLA breach or countdown status.
    """
    current_time = now or datetime.datetime.now(datetime.timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=datetime.timezone.utc)

    deadline = datetime.datetime.fromisoformat(resolution_deadline_iso)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=datetime.timezone.utc)

    status = status.upper()

    # If already resolved or closed
    if status in ("RESOLVED", "CLOSED"):
        if resolved_at_iso:
            resolved_dt = datetime.datetime.fromisoformat(resolved_at_iso)
            if resolved_dt.tzinfo is None:
                resolved_dt = resolved_dt.replace(tzinfo=datetime.timezone.utc)
            is_breached = resolved_dt > deadline
        else:
            is_breached = False

        return {
            "sla_state": "BREACHED" if is_breached else "MET",
            "is_breached": is_breached,
            "minutes_remaining": 0,
            "time_display": "Completed"
        }

    # If ticket is still in active queue
    diff_seconds = (deadline - current_time).total_seconds()
    minutes_remaining = int(diff_seconds // 60)

    if diff_seconds <= 0:
        return {
            "sla_state": "BREACHED",
            "is_breached": True,
            "minutes_remaining": minutes_remaining,
            "time_display": f"Breached by {abs(minutes_remaining)}m"
        }
    elif diff_seconds <= 3600:  # less than 1 hour remaining
        return {
            "sla_state": "AT_RISK",
            "is_breached": False,
            "minutes_remaining": minutes_remaining,
            "time_display": f"{minutes_remaining}m remaining"
        }
    else:
        hours_remaining = round(diff_seconds / 3600.0, 1)
        return {
            "sla_state": "HEALTHY",
            "is_breached": False,
            "minutes_remaining": minutes_remaining,
            "time_display": f"{hours_remaining}h remaining"
        }


def validate_ticket_transition(current_status: str, new_status: str, root_cause: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validates state machine transitions for ITSM lifecycle.
    """
    current_status = current_status.upper()
    new_status = new_status.upper()

    if current_status not in VALID_STATUSES:
        return False, f"Invalid current status: {current_status}"
    if new_status not in VALID_STATUSES:
        return False, f"Invalid target status: {new_status}"

    if current_status == new_status:
        return True, "No status change requested"

    allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return False, f"Cannot transition ticket from {current_status} to {new_status}"

    if new_status == "RESOLVED" and not root_cause:
        return False, "Resolution requires root-cause diagnosis notes"

    return True, "Transition authorized"
