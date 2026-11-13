# HelpDesk Pro

[![CI Pipeline](https://github.com/Soulofghost/helpdesk-pro/actions/workflows/ci.yml/badge.svg)](https://github.com/Soulofghost/helpdesk-pro/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-indigo.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Architecture: Clean ITSM](https://img.shields.io/badge/Architecture-Clean--ITSM-6366f1.svg)]()

> **HelpDesk Pro** is an enterprise IT Service Management (ITSM) and Incident Management platform. It features real-time Service Level Agreement (SLA) breach countdown timers, priority severity matrix escalation queues, technician category routing, and structured root-cause resolution workflows.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Client ["NOC Operations Console"]
        UI["Incident Console (HTML5 / CSS3 / Vanilla JS)"]
        Inspector["Live Ticket Inspector & Timeline"]
        Telemetry["SLA Compliance Gauges"]
    end

    subgraph Gateway ["FastAPI ITSM Gateway"]
        TicketRouter["/api/tickets & /api/analytics"]
        SLAEngine["SLA Countdown & Breach Engine"]
        RoutingEngine["Technician Queue Router"]
        StateMachine["ITSM State Transition Validator"]
    end

    subgraph Storage ["Persistence Layer"]
        SQLite[("SQLite WAL Persistent Store")]
        EventStream[("Indelible Event & Comment Audit Log")]
    end

    UI --> TicketRouter
    TicketRouter --> SLAEngine
    TicketRouter --> RoutingEngine
    TicketRouter --> StateMachine
    TicketRouter --> SQLite
    StateMachine --> EventStream
```

---

## ⚡ Core Engineering Capabilities

1. **SLA Policy Matrix & Real-Time Breach Engine (`ticket_sla.py`)**
   - Automatically calculates target response and resolution deadlines at ticket ingestion:
     - **CRITICAL (P1):** 1 hour response, 4 hours resolution $\to$ auto-escalates to *Tier 3 Critical Response*.
     - **HIGH (P2):** 2 hours response, 8 hours resolution $\to$ routes to *Tier 2 Infrastructure & Ops*.
     - **MEDIUM (P3):** 4 hours response, 24 hours resolution $\to$ routes to *Tier 1 General Support*.
     - **LOW (P4):** 8 hours response, 72 hours resolution $\to$ routes to *Tier 1 General Support*.
   - Evaluates dynamic countdown states:
     - `HEALTHY`: $> 1$ hour remaining in SLA window.
     - `AT_RISK`: $\le 1$ hour remaining prior to breach.
     - `BREACHED`: Deadline exceeded while ticket remains unresolved.
     - `MET`: Ticket resolved within SLA deadline.

2. **Automated Category Routing**
   - Directs incident triage based on operational domain:
     - `Security & IAM` $\to$ Alex Rivera (SecOps Lead)
     - `Network & Infrastructure` $\to$ Marcus Vance (NetOps)
     - `Hardware & Devices` $\to$ Elena Rostova (Hardware Tech)
     - `Software & Applications` $\to$ Liam Chen (SysAdmin)
     - `General & Access` $\to$ Sarah Connor (Service Desk)

3. **ITSM Lifecycle State Machine**
   - Enforces transition governance:
     $$\text{OPEN} \longrightarrow \text{ASSIGNED} \longrightarrow \text{IN\_PROGRESS} \rightleftharpoons \text{PENDING\_CUSTOMER} \longrightarrow \text{RESOLVED} \longrightarrow \text{CLOSED}$$
   - Resolution Gate: Tickets cannot transition to `RESOLVED` without technical root-cause documentation.

4. **Bi-Directional Comment & Event Trail**
   - Segregates customer-facing replies from internal technician notes.
   - Automatically timestamps first response time upon initial support technician interaction.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health status and engine version |
| `GET` | `/api/tickets` | Query incident queue (filters: priority, status, category, search) |
| `POST` | `/api/tickets` | Dispatch new incident (auto-generates HDK-xxxx, calculates SLA) |
| `GET` | `/api/tickets/{id}` | Full ticket telemetry with live SLA countdown and timeline |
| `PATCH` | `/api/tickets/{id}/status` | Execute state machine transition (`IN_PROGRESS`, `RESOLVED`, etc.) |
| `PATCH` | `/api/tickets/{id}/assign` | Reassign ticket to technician or escalation tier |
| `POST` | `/api/tickets/{id}/comments` | Post public reply or internal technician note |
| `GET` | `/api/analytics/sla-metrics` | Telemetry on SLA compliance rate, breaches, and priority volume |

---

## 🚀 Getting Started

### Local Development

1. **Clone repository:**
   ```bash
   git clone https://github.com/Soulofghost/helpdesk-pro.git
   cd helpdesk-pro
   ```

2. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Run tests:**
   ```bash
   pytest backend/tests -v
   ```

4. **Start the application:**
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```
   Open `http://localhost:8000` to access the NOC Incident Console.

---

### Docker Deployment

```bash
docker-compose up --build -d
```

---

## 👨‍💻 Author

**Alvin MS**  
GitHub: [@Soulofghost](https://github.com/Soulofghost)
