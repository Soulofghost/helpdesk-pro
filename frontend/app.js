const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? '' 
  : '';

let selectedTicketId = null;

// DOM Elements
const kpiActive = document.getElementById('kpiActive');
const kpiCompliance = document.getElementById('kpiCompliance');
const kpiBreaches = document.getElementById('kpiBreaches');
const kpiResolved = document.getElementById('kpiResolved');
const ticketListBody = document.getElementById('ticketListBody');
const inspectorPlaceholder = document.getElementById('inspectorPlaceholder');
const inspectorContent = document.getElementById('inspectorContent');
const searchTickets = document.getElementById('searchTickets');
const filterPriority = document.getElementById('filterPriority');
const filterStatus = document.getElementById('filterStatus');
const refreshBtn = document.getElementById('refreshBtn');

// Nav & Views
const navBtns = document.querySelectorAll('.nav-btn');
const viewPanels = document.querySelectorAll('.view-panel');
const viewTitle = document.getElementById('viewTitle');
const viewSubtitle = document.getElementById('viewSubtitle');

// Modals
const newTicketModal = document.getElementById('newTicketModal');
const openTicketModalBtn = document.getElementById('openNewTicketModal');
const closeTicketModalBtn = document.getElementById('closeTicketModal');
const cancelTicketModalBtn = document.getElementById('cancelTicketModal');
const newTicketForm = document.getElementById('newTicketForm');

const resolveModal = document.getElementById('resolveTicketModal');
const closeResolveBtn = document.getElementById('closeResolveModal');
const cancelResolveBtn = document.getElementById('cancelResolveModal');
const resolveForm = document.getElementById('resolveTicketForm');
const resolveTicketIdInput = document.getElementById('resolveTicketId');
const resolveRootCause = document.getElementById('resolveRootCause');

// Navigation Tabs
navBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    navBtns.forEach(b => b.classList.remove('active'));
    viewPanels.forEach(p => p.classList.remove('active'));

    btn.classList.add('active');
    const view = btn.dataset.view;

    if (view === 'queue') {
      document.getElementById('viewQueue').classList.add('active');
      viewTitle.textContent = 'Incident Queue';
      viewSubtitle.textContent = 'Enterprise ticket lifecycle routing, priority escalations, and SLA countdowns';
      loadTickets();
    } else if (view === 'metrics') {
      document.getElementById('viewMetrics').classList.add('active');
      viewTitle.textContent = 'SLA Compliance & Telemetry';
      viewSubtitle.textContent = 'Service level agreement compliance, escalation metrics, and department breakdowns';
      loadMetricsView();
    }
  });
});

// Load Tickets
async function loadTickets() {
  try {
    let url = `${API_BASE}/api/tickets?`;
    if (filterPriority.value) url += `priority=${encodeURIComponent(filterPriority.value)}&`;
    if (filterStatus.value) url += `status=${encodeURIComponent(filterStatus.value)}&`;
    if (searchTickets.value.trim()) url += `search=${encodeURIComponent(searchTickets.value.trim())}&`;

    const res = await fetch(url);
    const data = await res.json();
    renderTickets(data.tickets);
    updateKPIs();
  } catch (err) {
    ticketListBody.innerHTML = `<tr><td colspan="6" class="text-center text-crimson">Failed to load incident queue</td></tr>`;
  }
}

function renderTickets(tickets) {
  if (!tickets || tickets.length === 0) {
    ticketListBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding: 2.5rem;">No incident records matching criteria.</td></tr>`;
    return;
  }

  ticketListBody.innerHTML = tickets.map(t => {
    const isSelected = t.id === selectedTicketId ? 'selected' : '';
    const prioClass = `prio-${t.priority.toLowerCase()}`;
    const statClass = `status-${t.status.toLowerCase()}`;
    const slaStateClass = `sla-${t.sla.sla_state.toLowerCase()}`;

    return `
      <tr class="${isSelected}" onclick="selectTicket('${t.id}')">
        <td style="font-family: var(--font-mono); font-weight: 700; color: var(--indigo-light);">${t.ticket_number}</td>
        <td>
          <div style="font-weight: 600;">${escapeHtml(t.title)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${t.category}</div>
        </td>
        <td><span class="prio-tag ${prioClass}">${t.priority}</span></td>
        <td><span class="status-badge ${statClass}">${t.status}</span></td>
        <td style="font-size: 0.82rem; color: var(--text-primary);">${escapeHtml(t.assigned_agent)}</td>
        <td>
          <span class="sla-badge ${slaStateClass}">
            ⏱ ${t.sla.time_display}
          </span>
        </td>
      </tr>
    `;
  }).join('');
}

// Select Ticket for Inspector
window.selectTicket = async function(ticketId) {
  selectedTicketId = ticketId;
  const rows = ticketListBody.querySelectorAll('tr');
  rows.forEach(r => r.classList.remove('selected'));

  try {
    const res = await fetch(`${API_BASE}/api/tickets/${ticketId}`);
    if (!res.ok) return;
    const t = await res.json();

    inspectorPlaceholder.style.display = 'none';
    inspectorContent.style.display = 'flex';

    const prioClass = `prio-${t.priority.toLowerCase()}`;
    const statClass = `status-${t.status.toLowerCase()}`;
    const slaStateClass = `sla-${t.sla.sla_state.toLowerCase()}`;

    let actions = '';
    if (t.status === 'OPEN') {
      actions += `<button class="btn-sm btn-sm-primary" onclick="updateTicketStatus('${t.id}', 'IN_PROGRESS')">Start Triage</button>`;
    } else if (t.status === 'ASSIGNED' || t.status === 'IN_PROGRESS' || t.status === 'PENDING_CUSTOMER') {
      actions += `<button class="btn-sm btn-sm-success" onclick="openResolveModal('${t.id}')">Resolve Incident</button>`;
      if (t.status === 'IN_PROGRESS') {
        actions += `<button class="btn-sm" onclick="updateTicketStatus('${t.id}', 'PENDING_CUSTOMER')">Request Customer Info</button>`;
      } else if (t.status === 'PENDING_CUSTOMER') {
        actions += `<button class="btn-sm btn-sm-primary" onclick="updateTicketStatus('${t.id}', 'IN_PROGRESS')">Resume Progress</button>`;
      }
    } else if (t.status === 'RESOLVED') {
      actions += `<button class="btn-sm" onclick="updateTicketStatus('${t.id}', 'CLOSED')">Close Ticket</button>`;
      actions += `<button class="btn-sm" onclick="updateTicketStatus('${t.id}', 'IN_PROGRESS')">Re-Open</button>`;
    }

    const commentsHtml = t.comments.map(c => `
      <div class="comment-card">
        <div class="comment-meta">
          <span><strong>${escapeHtml(c.author)}</strong> (${c.author_role})</span>
          <span>${new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        <div class="comment-body">${escapeHtml(c.message)}</div>
      </div>
    `).join('') || '<p style="font-size: 0.8rem; color: var(--text-muted);">No timeline notes recorded.</p>';

    inspectorContent.innerHTML = `
      <div class="inspector-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-family: var(--font-mono); font-size: 0.85rem; font-weight: 700; color: var(--indigo-light);">${t.ticket_number}</span>
          <span class="sla-badge ${slaStateClass}">⏱ ${t.sla.time_display}</span>
        </div>
        <h3 style="font-size: 1.1rem; font-weight: 700;">${escapeHtml(t.title)}</h3>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span class="prio-tag ${prioClass}">${t.priority}</span>
          <span class="status-badge ${statClass}">${t.status}</span>
        </div>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.35rem;">${escapeHtml(t.description)}</p>
        <div style="font-size: 0.78rem; color: var(--text-subtle);">
          Requester: <strong>${escapeHtml(t.requester_name)}</strong> (${escapeHtml(t.requester_email)})<br>
          Assigned: <strong>${escapeHtml(t.assigned_agent)}</strong> [${escapeHtml(t.escalation_tier)}]
        </div>
        ${t.root_cause ? `<div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); padding: 0.5rem; border-radius: 4px; font-size: 0.8rem; color: var(--emerald);"><strong>Root Cause:</strong> ${escapeHtml(t.root_cause)}</div>` : ''}
      </div>

      <div class="inspector-actions">
        ${actions}
      </div>

      <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted);">Incident Timeline & Notes</div>
      <div class="inspector-timeline">
        ${commentsHtml}
      </div>

      <div class="comment-input-area">
        <textarea id="commentMsg" rows="2" placeholder="Add technician note or response..."></textarea>
        <button class="btn-sm btn-sm-primary" style="align-self: flex-end;" onclick="postComment('${t.id}')">Post Note</button>
      </div>
    `;

    // Re-highlight row in table
    const tableRows = ticketListBody.querySelectorAll('tr');
    tableRows.forEach(tr => {
      if (tr.textContent.includes(t.ticket_number)) {
        tr.classList.add('selected');
      }
    });

  } catch (err) {
    console.error(err);
  }
};

// Update Ticket Status
window.updateTicketStatus = async function(id, nextStatus) {
  try {
    const res = await fetch(`${API_BASE}/api/tickets/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: nextStatus,
        actor: 'NOC Lead Operator'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Status transition failed: ${err.detail}`);
      return;
    }

    loadTickets();
    selectTicket(id);
  } catch (err) {
    alert('Failed to update ticket status');
  }
};

// Open Resolve Modal
window.openResolveModal = function(id) {
  resolveTicketIdInput.value = id;
  resolveRootCause.value = '';
  resolveModal.classList.add('open');
};

function closeResolve() {
  resolveModal.classList.remove('open');
}
closeResolveBtn.addEventListener('click', closeResolve);
cancelResolveBtn.addEventListener('click', closeResolve);

// Confirm Resolve
resolveForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = resolveTicketIdInput.value;
  const rootCause = resolveRootCause.value.trim();

  try {
    const res = await fetch(`${API_BASE}/api/tickets/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'RESOLVED',
        root_cause: rootCause,
        actor: 'Lead Resolution Engineer'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Resolution error: ${err.detail}`);
      return;
    }

    closeResolve();
    loadTickets();
    selectTicket(id);
  } catch (err) {
    alert('Failed to resolve ticket');
  }
});

// Post Comment
window.postComment = async function(id) {
  const msgInput = document.getElementById('commentMsg');
  const msg = msgInput.value.trim();
  if (!msg) return;

  try {
    const res = await fetch(`${API_BASE}/api/tickets/${id}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        author: 'Alex Rivera',
        author_role: 'SecOps Lead',
        message: msg,
        is_internal: true
      })
    });

    if (res.ok) {
      selectTicket(id);
    }
  } catch (err) {
    console.error(err);
  }
};

// New Ticket Modal Handlers
openTicketModalBtn.addEventListener('click', () => {
  newTicketModal.classList.add('open');
});
function closeNewTicket() {
  newTicketModal.classList.remove('open');
  newTicketForm.reset();
}
closeTicketModalBtn.addEventListener('click', closeNewTicket);
cancelTicketModalBtn.addEventListener('click', closeNewTicket);

newTicketForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    title: document.getElementById('tickTitle').value.trim(),
    category: document.getElementById('tickCategory').value,
    priority: document.getElementById('tickPriority').value,
    requester_name: document.getElementById('tickReqName').value.trim(),
    requester_email: document.getElementById('tickReqEmail').value.trim(),
    description: document.getElementById('tickDescription').value.trim()
  };

  try {
    const res = await fetch(`${API_BASE}/api/tickets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Error creating ticket: ${err.detail}`);
      return;
    }

    const created = await res.json();
    closeNewTicket();
    loadTickets();
    selectTicket(created.id);
  } catch (err) {
    alert('Failed to log incident.');
  }
});

// KPI & Metrics Telemetry
async function updateKPIs() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/sla-metrics`);
    const data = await res.json();

    kpiActive.textContent = data.open_tickets;
    kpiCompliance.textContent = `${data.sla_compliance_percentage}%`;
    kpiBreaches.textContent = data.breached_count;
    kpiResolved.textContent = data.resolved_tickets;
  } catch (err) {
    console.warn('KPI update skipped');
  }
}

async function loadMetricsView() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/sla-metrics`);
    const data = await res.json();

    // Priority bars
    const prioOrder = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
    const maxPrio = Math.max(...Object.values(data.by_priority), 1);
    document.getElementById('priorityBars').innerHTML = prioOrder.map(p => {
      const count = data.by_priority[p] || 0;
      const pct = Math.round((count / maxPrio) * 100);
      return `
        <div class="chart-bar-row">
          <div class="chart-bar-info">
            <span>${p}</span>
            <span style="font-family: var(--font-mono); font-weight: 700;">${count}</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${pct}%; background: var(--${p === 'CRITICAL' ? 'crimson' : p === 'HIGH' ? 'amber' : 'indigo'});"></div>
          </div>
        </div>
      `;
    }).join('');

    // Category bars
    const maxCat = Math.max(...data.by_category.map(c => c.count), 1);
    document.getElementById('categoryBars').innerHTML = data.by_category.map(c => {
      const pct = Math.round((c.count / maxCat) * 100);
      return `
        <div class="chart-bar-row">
          <div class="chart-bar-info">
            <span>${escapeHtml(c.category)}</span>
            <span style="font-family: var(--font-mono); font-weight: 700;">${c.count}</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${pct}%; background: var(--emerald);"></div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.warn('Metrics view failed to load');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// Event Listeners
filterPriority.addEventListener('change', loadTickets);
filterStatus.addEventListener('change', loadTickets);
searchTickets.addEventListener('input', () => {
  clearTimeout(window.searchTimeout);
  window.searchTimeout = setTimeout(loadTickets, 250);
});
refreshBtn.addEventListener('click', () => {
  loadTickets();
  updateKPIs();
});

// Initialization
loadTickets();
