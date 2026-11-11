// ===================================================================
// Workspace extension JS — Projects, Administration,
// Library (Knowledge Base & Interactive Reader), Maps, Support tabs.
// Backed by live /api/projects, /api/users, and /api/orders APIs.
// ===================================================================

function showToast(message) {
  const toast = document.getElementById("workspaceToast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3200);
}

function openModal(id) { document.getElementById(id)?.classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id)?.classList.add("hidden"); }

// ---------------------------------------------------------------
// PROJECTS TAB (database-backed via /api/projects)
// ---------------------------------------------------------------
let financeChart = null;
async function initFinanceChart() {
  const canvas = document.getElementById("financeChart");
  if (!canvas || typeof Chart === "undefined") return;
  let ordersTotal = 0;
  let projectsBudget = 0;
  try {
    const [ordRes, projRes] = await Promise.all([fetch("/api/orders"), fetch("/api/projects")]);
    if (ordRes.ok) {
      const ordJson = await ordRes.json();
      ordersTotal = (ordJson.orders || []).reduce((acc, o) => acc + (Number(o.order_value) || 0), 0);
    }
    if (projRes.ok) {
      const projJson = await projRes.json();
      projectsBudget = (projJson.projects || []).reduce((acc, p) => acc + (Number(p.budget) || 0), 0);
    }
  } catch (e) {}

  if (financeChart) {
    try { financeChart.destroy(); } catch (e) {}
  }

  financeChart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: ["Live Order Value", "Allocated Project Budgets"],
      datasets: [{
        label: "Amount (INR)",
        data: [ordersTotal, projectsBudget],
        backgroundColor: ["rgba(15,108,189,0.75)", "rgba(217,119,6,0.75)"],
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { callback: (v) => "₹" + Number(v).toLocaleString("en-IN") } },
      },
    },
  });
}

function projectRowHtml(p) {
  const initial = (p.owner || "?").trim()[0]?.toUpperCase() || "?";
  const budgetFmt = "₹" + Number(p.budget || 0).toLocaleString("en-IN");
  const pct = Math.max(0, Math.min(100, Number(p.progress || 0)));
  const statusText = p.status || "Planning";
  return `<tr>
    <td><b>${p.name}</b></td>
    <td>${p.client || "Internal"}</td>
    <td><div class="cust-cell"><span class="cust-avatar">${initial}</span>${p.owner || "Admin"}</div></td>
    <td class="mono">${p.deadline || "—"}</td><td class="mono">${budgetFmt}</td>
    <td><div class="progress-track"><div class="progress-fill" style="width:${pct}%;"></div></div></td>
    <td><span class="status-pill status-processing">${statusText}</span></td>
    <td style="text-align:right;"><button class="btn btn-dark btn-sm" onclick="deleteProjectRow('${p.id}')" style="padding:3px 8px;font-size:0.75rem;">Delete</button></td>
  </tr>`;
}

async function renderProjectsFromDb() {
  const tbody = document.getElementById("projectsTableBody");
  if (!tbody) return;
  let projects = [];
  try {
    const res = await fetch("/api/projects");
    if (res.ok) {
      const json = await res.json();
      projects = json.projects || [];
    }
  } catch (e) {}

  tbody.innerHTML = "";
  if (projects.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">No projects stored in the database yet. Click <b>New Project</b> to add one.</td></tr>';
  } else {
    projects.forEach((p) => tbody.insertAdjacentHTML("beforeend", projectRowHtml(p)));
  }

  const countEl = document.getElementById("projTableCount");
  if (countEl) countEl.textContent = `${projects.length} project${projects.length === 1 ? "" : "s"}`;
  const activeEl = document.getElementById("statActiveProjects");
  if (activeEl) activeEl.textContent = String(projects.length);
  const budgetEl = document.getElementById("statProjectBudget");
  if (budgetEl) {
    const totalBudget = projects.reduce((acc, p) => acc + (Number(p.budget) || 0), 0);
    budgetEl.textContent = "₹" + totalBudget.toLocaleString("en-IN");
  }
  const compEl = document.getElementById("statCompletion");
  if (compEl) {
    const avg = projects.length > 0 ? Math.round(projects.reduce((acc, p) => acc + (Number(p.progress) || 0), 0) / projects.length) : 0;
    compEl.textContent = `${avg}%`;
  }
}

window.deleteProjectRow = async function(projectId) {
  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" });
    if (res.ok) {
      await renderProjectsFromDb();
      await initFinanceChart();
      showToast("Project deleted.");
    }
  } catch (e) {}
};

function addProjectNotification(text) {
  const feed = document.getElementById("projectNotifFeed");
  if (!feed) return;
  if (feed.querySelector("p.muted")) feed.innerHTML = "";
  const row = document.createElement("div");
  row.className = "notif-row";
  row.innerHTML = `<span class="notif-dot dot-indigo"></span>
    <div><b>New project created</b><p>${text}</p><span class="notif-when">Just now</span></div>`;
  feed.prepend(row);
  const countEl = document.getElementById("projNotifCount");
  if (countEl) {
    const cur = parseInt(countEl.textContent, 10) || 0;
    countEl.textContent = `${cur + 1} update${cur + 1 === 1 ? "" : "s"}`;
  }
}

document.getElementById("newProjectBtn")?.addEventListener("click", () => openModal("newProjectModal"));
document.getElementById("closeProjectModal")?.addEventListener("click", () => closeModal("newProjectModal"));
document.getElementById("newProjectForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    name: document.getElementById("npName").value.trim(),
    client: (document.getElementById("npClient")?.value || "Internal").trim(),
    owner: document.getElementById("npOwner").value.trim(),
    deadline: document.getElementById("npDeadline").value,
    budget: parseFloat(document.getElementById("npBudget").value || "0") || 0,
    status: "In Progress",
    progress: 10,
  };
  if (!payload.name || !payload.owner) return;
  try {
    const res = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      await renderProjectsFromDb();
      await initFinanceChart();
      addProjectNotification(`"${payload.name}" owned by ${payload.owner}.`);
      e.target.reset();
      closeModal("newProjectModal");
      showToast(`Project "${payload.name}" saved.`);
    }
  } catch (err) {
    showToast("Failed to save project: " + err.message);
  }
});

// ---------------------------------------------------------------
// ADMINISTRATION TAB (database-backed via /api/users)
// ---------------------------------------------------------------
function userRowHtml(u) {
  const initial = (u.name || "?").trim()[0]?.toUpperCase() || "?";
  const statusClass = (u.status || "").toLowerCase() === "active" ? "status-delivered" : "status-processing";
  return `<tr>
    <td><div class="cust-cell"><span class="cust-avatar">${initial}</span>${u.name}</div></td>
    <td class="mono">${u.email}</td><td>${u.role || "Member"}</td>
    <td><span class="status-pill ${statusClass}">${u.status || "Active"}</span></td>
    <td style="text-align:right;"><button class="btn btn-dark btn-sm" onclick="deleteTeamUser('${u.email}')" style="padding:3px 8px;font-size:0.75rem;">Remove</button></td>
  </tr>`;
}

async function renderUsersFromDb() {
  const tbody = document.getElementById("adminUsersTableBody");
  if (!tbody) return;
  let users = [];
  try {
    const res = await fetch("/api/users");
    if (res.ok) {
      const json = await res.json();
      users = json.users || [];
    }
  } catch (e) {}

  tbody.innerHTML = "";
  if (users.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">No team members registered in the database yet. Click <b>Invite User</b> to add one.</td></tr>';
  } else {
    users.forEach((u) => tbody.insertAdjacentHTML("beforeend", userRowHtml(u)));
  }

  const countEl = document.getElementById("adminTableCount");
  if (countEl) countEl.textContent = `${users.length} user${users.length === 1 ? "" : "s"}`;
  const totalUsersEl = document.getElementById("statTotalUsers");
  if (totalUsersEl) totalUsersEl.textContent = String(users.length);
  const activeEl = document.getElementById("statActiveUsers");
  if (activeEl) activeEl.textContent = String(users.filter((u) => (u.status || "Active") === "Active").length);
  const roles = new Set(users.map((u) => u.role).filter(Boolean));
  const rolesEl = document.getElementById("statDistinctRoles");
  if (rolesEl) rolesEl.textContent = String(roles.size);

  document.querySelectorAll("[data-role-count]").forEach((el) => {
    const roleName = el.getAttribute("data-role-count");
    const n = users.filter((u) => (u.role || "").toLowerCase() === (roleName || "").toLowerCase()).length;
    el.textContent = `${n} member${n === 1 ? "" : "s"}`;
  });
}

window.deleteTeamUser = async function(email) {
  try {
    const res = await fetch(`/api/users/${encodeURIComponent(email)}`, { method: "DELETE" });
    if (res.ok) {
      await renderUsersFromDb();
      showToast("User removed.");
    }
  } catch (e) {}
};

document.getElementById("inviteUserBtn")?.addEventListener("click", () => openModal("inviteUserModal"));
document.getElementById("closeInviteModal")?.addEventListener("click", () => closeModal("inviteUserModal"));
document.getElementById("inviteUserForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    name: document.getElementById("iuName").value.trim(),
    email: document.getElementById("iuEmail").value.trim(),
    dept: (document.getElementById("iuDept")?.value || "Security Operations").trim(),
    role: document.getElementById("iuRole").value,
    status: "Active",
  };
  if (!payload.name || !payload.email) return;
  try {
    const res = await fetch("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      await renderUsersFromDb();
      e.target.reset();
      closeModal("inviteUserModal");
      showToast(`Member "${payload.name}" added.`);
    }
  } catch (err) {
    showToast("Failed to save user: " + err.message);
  }
});

// ---------------------------------------------------------------
// RICH KNOWLEDGE BASE ARTICLES & DOCUMENT READER
// ---------------------------------------------------------------
const DOC_ARTICLES = {
  "Data Protection & Privacy Policy": {
    category: "Policy",
    badgeClass: "policy",
    subtitle: "Compliance with Digital Personal Data Protection (DPDP) Act, 2023 · v4.2",
    content: `
      <div class="doc-callout">
        <b>⚖️ Regulatory Baseline:</b> This document governs TrapWire Private Limited's processing, safeguarding, and mandatory reporting protocols for digital personal data under the <b>Digital Personal Data Protection Act, 2023 (DPDP Act)</b>, CERT-In cybersecurity directives, and global security deception standards.
      </div>

      <h3>1. Purpose and Scope</h3>
      <p>This policy defines mandatory standards for all employees, data processors, contractors, and automated systems handling digital personal data of Indian citizens ("Data Principals"). As a <b>Data Fiduciary</b> under Section 8 of the DPDP Act, TrapWire is legally bound to implement technical and organizational measures to prevent personal data breaches.</p>

      <h3>2. Core Principles of Data Protection</h3>
      <ul>
        <li><b>Purpose Limitation (Section 6):</b> Personal data (e.g. customer names, PAN, Aadhaar, billing records) may only be processed for specified, lawful purposes for which explicit, informed consent has been provided.</li>
        <li><b>Data Minimisation & Masking:</b> Direct identifiers are strictly masked in standard administrative UI views (e.g. <code>•••• •••• 9012</code> for Aadhaar, <code>••••••847K</code> for PAN).</li>
        <li><b>Storage Limitation (Section 8(7)):</b> Digital personal data must be erased as soon as the specified purpose is fulfilled or consent is withdrawn.</li>
        <li><b>Security Safeguards (Section 8(5)):</b> Reasonable security safeguards must be established to prevent breach, exfiltration, unauthorized modification, or exposure.</li>
      </ul>

      <div class="doc-callout danger">
        <b>🚨 Statutory Penalties (Section 33 &amp; Schedule):</b>
        Failure to take reasonable security safeguards to prevent personal data breaches carries financial penalties of up to <b>₹250 Crores (INR 2.5 Billion)</b> imposed by the Data Protection Board of India.
      </div>

      <h3>3. Technical Safeguards & Honeypot Deception Architecture</h3>
      <p>To defend against internal and external threat actors, TrapWire employs an active deception grid:</p>
      <table class="doc-table">
        <thead>
          <tr>
            <th>Security Layer</th>
            <th>Implementation Mechanism</th>
            <th>DPDP Compliance Objective</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Shadow Vault Decoys</b></td>
            <td>Synthetic high-value customer records with embedded tracking beacons.</td>
            <td>Zero-day exfiltration detection without exposing genuine Data Principal records.</td>
          </tr>
          <tr>
            <td><b>Canary Attribution</b></td>
            <td>Unique cryptographic phone-home markers embedded in exported datasets.</td>
            <td>Identifies attacker source IP, ISP, and timestamp for evidentiary reporting.</td>
          </tr>
          <tr>
            <td><b>Automated DPB Dispatch</b></td>
            <td>Real-time compilation of incident reports for Data Protection Board submission.</td>
            <td>Guarantees 100% adherence to 72-hour statutory breach reporting mandates.</td>
          </tr>
        </tbody>
      </table>

      <h3>4. Mandatory Incident Response Protocol (Section 8(6))</h3>
      <ol>
        <li><b>Immediate Detection & Triage:</b> Automated honeypot alarms trigger instant WebSocket broadcasts to the SOC Defender console and admin notification endpoints.</li>
        <li><b>Deception Isolation:</b> Threat actors are seamlessly sandboxed into synthetic decoy tables while production databases remain completely isolated.</li>
        <li><b>Statutory Notification:</b> A formal breach notification containing incident scope, impacted fields, and remediation steps must be submitted to the <b>Data Protection Board of India (DPB)</b> within 72 hours.</li>
      </ol>

      <div class="doc-callout warning">
        <b>💡 Knowledge Upgrade Check:</b>
        Did you know? Under DPDP Act 2023, data breaches must also be communicated to every affected Data Principal in clear, plain language detailing preventive measures they should take.
      </div>
    `
  },
  "Incident Response Playbook": {
    category: "Policy",
    badgeClass: "policy",
    subtitle: "Standard Operating Procedure for Cybersecurity & Data Breach Incidents · SOP-SEC-01",
    content: `
      <div class="doc-callout">
        <b>🛡️ SOC Standard Operating Procedure:</b> Designed according to NIST SP 800-61 Rev 2 and DPDP Act 2023 breach response guidelines.
      </div>
      <h3>Phase 1: Preparation & Tooling</h3>
      <p>Ensure all automated honeypot alarms, canary token monitors, and live WebSocket telemetry feeds are operational 24/7 across all endpoints.</p>

      <h3>Phase 2: Detection & Analysis</h3>
      <p>Identify anomalies such as repeated brute-force authentication failures, SQL injection probing against <code>/api/login</code>, or unauthorized calls to <code>/api/export</code>.</p>

      <h3>Phase 3: Containment & Deception Engagement</h3>
      <p>If suspicious activity is verified, automatically flag the session as <code>SUSPICIOUS</code>. Deliver canary-laced decoy databases rather than real customer records to track exfiltration paths.</p>

      <h3>Phase 4: Eradication & Remediation</h3>
      <p>Revoke compromised bearer tokens, blacklist offending external IP subnets, and seal vulnerable API endpoints.</p>

      <h3>Phase 5: DPB & CERT-In Reporting</h3>
      <p>Execute automated generation of the <b>DPDP Compliance Incident Report PDF</b> and register the submission token on the national DPB registry.</p>
    `
  },
  "DPDP Compliance Audit Report": {
    category: "Report",
    badgeClass: "report",
    subtitle: "Independent Readiness Assessment · Q2 2026 Audit Findings",
    content: `
      <div class="doc-callout">
        <b>📊 Overall Audit Score: 98.4% (EXEMPLARY)</b> — Full adherence to DPDP Act 2023 data fiduciary obligations and ISO/IEC 27001:2022 standards.
      </div>
      <h3>Executive Summary</h3>
      <p>TrapWire Pvt Ltd underwent a comprehensive compliance evaluation. The audit examined consent architectures, data masking, honeypot decoys, and incident response pipelines.</p>

      <h3>Key Findings</h3>
      <ul>
        <li><b>Consent Logging:</b> 100% of customer orders contain verifiable consent timestamps.</li>
        <li><b>Deception Readiness:</b> Canary tracking tokens successfully caught 100% of adversarial exfiltrations.</li>
        <li><b>Report Dispatch Latency:</b> Automated DPB report generation completes in under <b>1.2 seconds</b>.</li>
      </ul>
    `
  },
  "Security Awareness Training Deck": {
    category: "Training",
    badgeClass: "training",
    subtitle: "Internal SOC & Employee Cybersecurity Hygiene Module · 2026",
    content: `
      <h3>Module Overview: Social Engineering & Credential Protection</h3>
      <p>This training deck educates employees on recognizing phishing attacks, brute force attempts, and credential stuffing threats.</p>
      <div class="doc-callout">
        <b>Key Takeaways:</b>
        <ul>
          <li>Always enforce multi-factor authentication (MFA) on corporate portals.</li>
          <li>Never share or copy unmasked customer PII outside the secure TrapWire console.</li>
          <li>Report suspicious login alerts immediately to the SOC Desk via the Support Center.</li>
        </ul>
      </div>
    `
  },
  "New Project Charter Template": {
    category: "Template",
    badgeClass: "template",
    subtitle: "Standardized Framework for Enterprise Deployments",
    content: `
      <h3>Project Scope & Deliverables</h3>
      <p>Use this template to define project objectives, stakeholder responsibilities, milestone timelines, and DPDP compliance sign-offs before kickoff.</p>
      <div class="doc-callout">
        <b>Requirement:</b> Every new project handling digital personal data must undergo a mandatory Data Protection Impact Assessment (DPIA).
      </div>
    `
  },
  "Weekly Status Report Template": {
    category: "Template",
    badgeClass: "template",
    subtitle: "Executive Progress & Metrics Reporting Structure",
    content: `
      <h3>Weekly Engineering & Operations Template</h3>
      <p>Structured layout for summarizing weekly sprint velocities, threat containment statistics, infrastructure uptime, and customer fulfillment SLAs.</p>
    `
  },
  "Q2 FY26 Financial Report": {
    category: "Report",
    badgeClass: "report",
    subtitle: "Quarterly Revenue, OPEX, and Compliance Investment Review",
    content: `
      <h3>Financial Highlights</h3>
      <p>Total Revenue: ₹58.4 Lakhs · OPEX: ₹32.1 Lakhs · Security & R&D Investment: ₹14.8 Lakhs. On track to meet fiscal milestones.</p>
    `
  },
  "New Hire Onboarding Guide": {
    category: "Training",
    badgeClass: "training",
    subtitle: "Security Policies & Setup for Engineering & Operations Personnel",
    content: `
      <h3>Welcome to TrapWire!</h3>
      <p>This guide walks new hires through workstation hardening, password manager configuration, Git signing keys, and our internal code of ethics.</p>
    `
  },
  "Client Proposal Template": {
    category: "Template",
    badgeClass: "template",
    subtitle: "Enterprise Cybersecurity Services & Deception Architecture Pitch",
    content: `
      <h3>Enterprise Value Proposition</h3>
      <p>Template highlighting TrapWire's breach detection deception technology, DPDP compliance automation, and real-time SOC alerting for enterprise clients.</p>
    `
  },
  "Vendor Code of Conduct": {
    category: "Policy",
    badgeClass: "policy",
    subtitle: "Third-Party Data Processor Security & Ethics Guidelines",
    content: `
      <h3>Third-Party Vendor Mandates</h3>
      <p>Vendors and external Data Processors contracted by TrapWire must strictly comply with DPDP Act 2023 provisions, maintain ISO 27001 certification, and allow periodic security audits.</p>
    `
  }
};

function openDocReader(docTitle) {
  const doc = DOC_ARTICLES[docTitle] || {
    category: "Document",
    badgeClass: "policy",
    subtitle: "TrapWire Knowledge Base Document",
    content: `<p>Document content for <b>${docTitle}</b> is currently being synchronized.</p>`
  };

  const modal = document.getElementById("docReaderModal");
  const heading = document.getElementById("docReaderHeading");
  const meta = document.getElementById("docReaderMeta");
  const badge = document.getElementById("docReaderBadge");
  const body = document.getElementById("docReaderBody");

  if (!modal || !heading || !body) return;

  heading.textContent = docTitle;
  meta.textContent = doc.subtitle || "TrapWire Knowledge Base";
  if (badge) {
    badge.textContent = (doc.category || "DOCUMENT").toUpperCase();
    badge.className = `doc-badge-pill ${doc.badgeClass || 'policy'}`;
  }
  body.innerHTML = doc.content;

  modal.classList.remove("hidden");
}

function closeDocReader() {
  const modal = document.getElementById("docReaderModal");
  if (modal) modal.classList.add("hidden");
}

// ---------------------------------------------------------------
// LIBRARY TAB
// ---------------------------------------------------------------
const LIBRARY_DOCS = [
  { title: "Data Protection & Privacy Policy", cat: "Policy", type: "pdf", size: "412 KB", updated: "12 Aug 2026" },
  { title: "Incident Response Playbook", cat: "Policy", type: "pdf", size: "780 KB", updated: "03 Aug 2026" },
  { title: "New Project Charter Template", cat: "Template", type: "docx", size: "58 KB", updated: "20 Jul 2026" },
  { title: "Weekly Status Report Template", cat: "Template", type: "xlsx", size: "34 KB", updated: "01 Aug 2026" },
  { title: "Q2 FY26 Financial Report", cat: "Report", type: "xlsx", size: "1.1 MB", updated: "15 Jul 2026" },
  { title: "DPDP Compliance Audit Report", cat: "Report", type: "pdf", size: "960 KB", updated: "28 Aug 2026" },
  { title: "Security Awareness Training Deck", cat: "Training", type: "ppt", size: "3.2 MB", updated: "10 Jun 2026" },
  { title: "New Hire Onboarding Guide", cat: "Training", type: "pdf", size: "540 KB", updated: "22 May 2026" },
  { title: "Client Proposal Template", cat: "Template", type: "docx", size: "76 KB", updated: "05 Aug 2026" },
  { title: "Vendor Code of Conduct", cat: "Policy", type: "pdf", size: "300 KB", updated: "18 Apr 2026" },
];

function docCardHtml(d) {
  return `<div class="doc-card" data-cat="${d.cat}" data-search="${d.title.toLowerCase()}" onclick="openDocReader('${d.title.replace(/'/g, "\\'")}')">
    <div class="doc-icon ${d.type}">${d.type.toUpperCase()}</div>
    <div class="doc-cat-tag">${d.cat}</div>
    <div class="doc-title">${d.title}</div>
    <div class="doc-meta">${d.size} · Updated ${d.updated}</div>
    <div class="doc-foot">
      <span style="color:#0F6CBD;font-weight:600;font-size:0.8rem;display:flex;align-items:center;gap:4px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
        Read &amp; Upgrade
      </span>
      <a href="#" onclick="event.stopPropagation(); event.preventDefault(); showToast('Document downloaded (PDF export).');">Download</a>
    </div>
  </div>`;
}

function renderLibrary() {
  const grid = document.getElementById("docGrid");
  if (!grid) return;
  grid.innerHTML = LIBRARY_DOCS.map(docCardHtml).join("");
}
renderLibrary();

document.querySelectorAll("#libChips .filter-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll("#libChips .filter-chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    applyLibraryFilter();
  });
});
document.getElementById("libSearch")?.addEventListener("input", applyLibraryFilter);

function applyLibraryFilter() {
  const activeCat = document.querySelector("#libChips .filter-chip.active")?.dataset.cat || "all";
  const q = (document.getElementById("libSearch")?.value || "").trim().toLowerCase();
  document.querySelectorAll("#docGrid .doc-card").forEach((card) => {
    const matchesCat = activeCat === "all" || card.dataset.cat === activeCat;
    const matchesSearch = !q || card.dataset.search.includes(q);
    card.style.display = matchesCat && matchesSearch ? "" : "none";
  });
}

// ---------------------------------------------------------------
// SUPPORT TAB
// ---------------------------------------------------------------
document.getElementById("supportForm")?.addEventListener("submit", (e) => {
  e.preventDefault();
  const msg = document.getElementById("supportMsg");
  const ticketId = "TCK-" + Math.random().toString(36).slice(2, 8).toUpperCase();
  msg.textContent = `Ticket ${ticketId} submitted. Our team will reach out via support@trapwire.co.in.`;
  msg.className = "msg";
  e.target.reset();
  showToast(`Support ticket ${ticketId} created.`);
});

document.querySelectorAll(".faq-q").forEach((btn) => {
  btn.addEventListener("click", () => {
    btn.parentElement.classList.toggle("open");
  });
});

// ---------------------------------------------------------------
// Modal overlay click-outside-to-close
// ---------------------------------------------------------------
document.querySelectorAll(".modal-overlay, .doc-reader-modal").forEach((overlay) => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.classList.add("hidden");
  });
});

// ---------------------------------------------------------------
// Init on load
// ---------------------------------------------------------------
initFinanceChart();
renderProjectsFromDb();
renderUsersFromDb();
