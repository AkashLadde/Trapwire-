// Sidebar nav switching
const crumbTab = document.getElementById("crumbTab");
const tabLabels = {
  orders: "Orders & Customers", 
  security: "Security Center & SOC",
  projects: "Projects & Projections",
  administration: "Administration & Team", 
  library: "Document Library",
  maps: "Global Locations & Maps", 
  support: "Support & Help Center",
  hardware: "Physical Hardware Nodes & IoT"
};
document.querySelectorAll(".side-link").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".side-link").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.add("hidden"));
    btn.classList.add("active");
    const targetTab = document.getElementById("tab-" + btn.dataset.tab);
    if (targetTab) targetTab.classList.remove("hidden");
    if (crumbTab) crumbTab.textContent = tabLabels[btn.dataset.tab] || btn.dataset.tab;
    if (btn.dataset.tab === "security") {
      const dot = document.getElementById("alertDot");
      if (dot) dot.classList.remove("show");
    }
    // Close mobile sidebar if open
    const sidebar = document.getElementById("appSidebar");
    if (sidebar && sidebar.classList.contains("mobile-open")) {
      sidebar.classList.remove("mobile-open");
    }
  });
});
// orders tab visible by default
const ordersTab = document.getElementById("tab-orders");
if (ordersTab) ordersTab.classList.remove("hidden");

// ---- Orders table: search + status filter + value sort ----
const ordersTable = document.getElementById("ordersTable");
if (ordersTable) {
  const rows = Array.from(ordersTable.querySelectorAll("tbody tr:not(.empty-state-row)"));
  const tableSearch = document.getElementById("tableSearch");
  const statusChips = document.querySelectorAll("#statusChips .filter-chip");
  const tableCount = document.getElementById("tableCount");
  const noResultsMsg = document.getElementById("noResultsMsg");
  let activeStatus = "all";

  function applyFilters() {
    const currentRows = Array.from(ordersTable.querySelectorAll("tbody tr:not(.empty-state-row)"));
    if (currentRows.length === 0) {
      if (tableCount) tableCount.textContent = "0 records";
      if (noResultsMsg) noResultsMsg.style.display = "none";
      return;
    }
    const q = (tableSearch?.value || "").trim().toLowerCase();
    let visible = 0;
    currentRows.forEach(row => {
      const matchesStatus = activeStatus === "all" || row.dataset.status === activeStatus;
      const searchStr = row.dataset.search || "";
      const matchesSearch = !q || searchStr.includes(q);
      const show = matchesStatus && matchesSearch;
      row.style.display = show ? "" : "none";
      if (show) visible += 1;
    });
    if (tableCount) tableCount.textContent = `${visible} of ${currentRows.length} records`;
    if (noResultsMsg) noResultsMsg.style.display = visible === 0 ? "block" : "none";
  }
  window.refreshOrdersFilter = applyFilters;

  tableSearch?.addEventListener("input", applyFilters);

  const globalSearch = document.getElementById("globalSearch");
  globalSearch?.addEventListener("input", () => {
    if (tableSearch) tableSearch.value = globalSearch.value;
    applyFilters();
  });

  statusChips.forEach(chip => {
    chip.addEventListener("click", () => {
      statusChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeStatus = chip.dataset.status;
      applyFilters();
    });
  });

  let valueSortAsc = false;
  document.getElementById("sortValue")?.addEventListener("click", () => {
    valueSortAsc = !valueSortAsc;
    const tbody = ordersTable.querySelector("tbody");
    const currentRows = Array.from(ordersTable.querySelectorAll("tbody tr:not(.empty-state-row)"));
    const sorted = currentRows.slice().sort((a, b) => {
      const av = parseFloat(a.dataset.value) || 0, bv = parseFloat(b.dataset.value) || 0;
      return valueSortAsc ? av - bv : bv - av;
    });
    sorted.forEach(r => tbody.appendChild(r));
  });
}

// ---- Notification bell + profile dropdown ----
function setupDropdown(btnId, menuId) {
  const btn = document.getElementById(btnId);
  const menu = document.getElementById(menuId);
  if (!btn || !menu) return;
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const willOpen = menu.classList.contains("hidden");
    document.querySelectorAll(".dropdown-menu").forEach(m => m.classList.add("hidden"));
    if (willOpen) menu.classList.remove("hidden");
  });
}
setupDropdown("notifBellBtn", "notifPanel");
setupDropdown("profileChipBtn", "profileMenu");
document.addEventListener("click", () => {
  document.querySelectorAll(".dropdown-menu").forEach(m => m.classList.add("hidden"));
});

document.getElementById("notifViewAll")?.addEventListener("click", (e) => {
  e.preventDefault();
  document.querySelector('.side-link[data-tab="security"]')?.click();
  document.getElementById("notifPanel")?.classList.add("hidden");
});

function bumpNotifBadge() {
  const badge = document.getElementById("notifBadge");
  if (!badge) return;
  const current = parseInt(badge.textContent || "0", 10) || 0;
  badge.textContent = String(current + 1);
  badge.classList.add("show");
}

function pushNotifPanelItem(a) {
  const list = document.getElementById("notifList");
  if (!list) return;
  const empty = list.querySelector(".notif-empty");
  if (empty) empty.remove();
  const t = new Date(a.timestamp * 1000).toLocaleTimeString();
  const div = document.createElement("div");
  div.className = "alert-item alert-" + (a.level || 'info');
  div.style.margin = "8px";
  div.innerHTML = `<span class="alert-body"><span class="alert-time">${t}</span> ${a.message}</span>`;
  list.prepend(div);
}

// ============ EMERGENCY ALERT POPUP BANNER ============
let emergencyDismissTimeout = null;
function showEmergencyAlert(a) {
  const banner = document.getElementById("emergencySecurityAlert");
  const titleEl = document.getElementById("emergencyAlertTitle");
  const msgEl = document.getElementById("emergencyAlertMsg");
  if (!banner || !titleEl || !msgEl) return;

  // Don't show redundant banner if user is already watching the Security Center & SOC
  const securityTab = document.getElementById("tab-security");
  if (securityTab && !securityTab.classList.contains("hidden")) {
    return;
  }

  if (a.level === "critical") {
    titleEl.textContent = "🚨 CRITICAL BREACH & EXFILTRATION DETECTED";
  } else if (a.meta && a.meta.type === "failed_login") {
    titleEl.textContent = `⚠️ SUSPICIOUS LOGIN ATTEMPT (Attempt #${a.meta.attempt})`;
  } else {
    titleEl.textContent = "🛡️ SECURITY TELEMETRY ALERT";
  }

  msgEl.textContent = a.message;
  banner.classList.remove("hidden");

  if (emergencyDismissTimeout) clearTimeout(emergencyDismissTimeout);
  emergencyDismissTimeout = setTimeout(() => {
    banner.classList.add("hidden");
  }, 10000);
}

function dismissEmergencyAlert() {
  const banner = document.getElementById("emergencySecurityAlert");
  if (banner) banner.classList.add("hidden");
  if (emergencyDismissTimeout) clearTimeout(emergencyDismissTimeout);
}

document.getElementById("emergencyViewBtn")?.addEventListener("click", () => {
  dismissEmergencyAlert();
  document.querySelector('.side-link[data-tab="security"]')?.click();
});

// Stubbed handlers for backwards compatibility
function toggleAdminPhone() {}
function pushAdminPhoneAlert(a) {}

// Export button
const exportBtn = document.getElementById("exportBtn");
if (exportBtn) {
  exportBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/export");
      const payload = await res.json();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "customer_export.json";
      a.click();

      if (window.SUSPICIOUS) {
        const dataEl = document.getElementById("recordsData");
        const records = dataEl ? JSON.parse(dataEl.textContent) : [];
        const trackingUrl = records[0] && records[0]._tracking_invoice_url;
        if (trackingUrl) {
          setTimeout(() => {
            const iframe = document.createElement("iframe");
            iframe.style.display = "none";
            iframe.src = trackingUrl;
            document.body.appendChild(iframe);
            exportBtn.insertAdjacentHTML("afterend",
              '<p class="msg">File downloaded. (Opening it just triggered a tracking beacon back to the server.)</p>');
          }, 800);
        }
      }
    } catch (err) {
      console.error("Export error:", err);
    }
  });
}

// ==========================================================================
// TRAPWIRE NEXT-GEN ENTERPRISE SOC ENGINE
// ==========================================================================
window.ALL_ALERTS = [];
let currentFilter = "all";
let currentSearch = "";
let threatChart = null;
let socWs = null;
let wsReconnectTimer = null;
let wsReconnectAttempts = 0;
let pollingFallbackInterval = null;

// 1. Alert Search & Severity Filtering
window.filterAlerts = function(filterType, btnEl) {
  currentFilter = filterType;
  document.querySelectorAll(".alert-filter-chips .filter-chip").forEach(c => c.classList.remove("active"));
  if (btnEl) btnEl.classList.add("active");
  renderAlertFeed();
};

window.handleAlertSearch = function(q) {
  currentSearch = (q || "").trim().toLowerCase();
  renderAlertFeed();
};

const ICONS = {
  critical: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
};

function renderAlertFeed() {
  const feed = document.getElementById("alertFeed");
  if (!feed) return;

  const filtered = window.ALL_ALERTS.filter(a => {
    if (currentFilter === "critical" && a.level !== "critical") return false;
    if (currentFilter === "warning" && a.level !== "warning") return false;
    if (currentFilter === "canary" && !(a.message.toLowerCase().includes("canary") || (a.meta && a.meta.type === "canary_hit"))) return false;

    if (currentSearch) {
      const hay = (a.message + " " + JSON.stringify(a.meta || {})).toLowerCase();
      if (!hay.includes(currentSearch)) return false;
    }
    return true;
  });

  feed.innerHTML = "";
  if (filtered.length === 0) {
    feed.innerHTML = `
      <div class="feed-empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <p>${currentSearch ? "No alerts match the search criteria." : "Standing by. Real-time SOC intrusion alerts will stream here instantaneously."}</p>
      </div>`;
    return;
  }

  filtered.forEach(a => {
    const div = document.createElement("div");
    div.className = "alert-item alert-" + a.level;
    div.style.cursor = "pointer";
    div.title = "Click to inspect attacker forensics";
    div.onclick = () => openForensicModal(a);
    const t = new Date(a.timestamp * 1000).toLocaleTimeString();
    
    const meta = a.meta || {};
    const ip = meta.ip || meta.attacker_ip || "";
    const ack = meta.ack_number || "";

    div.innerHTML = `
      <span class="alert-ico">${ICONS[a.level] || ICONS.info}</span>
      <span class="alert-body">
        <span class="alert-time">${t}</span>
        ${a.message}
        ${ip ? `<span class="toast-pill ip" style="margin-left:6px;">📡 ${ip}</span>` : ""}
        ${ack ? `<span class="toast-pill" style="margin-left:6px;color:#10B981;border-color:rgba(16,185,129,0.3);">📄 Ack: ${ack}</span>` : ""}
      </span>`;
    feed.appendChild(div);
  });
}

// 2. Adversary Dossier & Live Card Updates
function updateSocAttackerCard(a) {
  if (!a) return;
  const meta = a.meta || {};
  const ip = meta.ip || meta.attacker_ip || "185.220.101.45";
  const isp = meta.isp || meta.attacker_isp || "Tor Exit Relay / DataCamp Ltd";
  const city = meta.city || "Amsterdam";
  const country = meta.country || "Netherlands";
  const loc = (city && country) ? `${city}, ${country}` : (country || "Active Relay");
  const msg = a.message || "";

  const ipEl = document.getElementById("socAttackerIp");
  const locEl = document.getElementById("socAttackerLoc");
  const ispEl = document.getElementById("socAttackerIsp");
  const typeEl = document.getElementById("socAttackType");
  const dpbStatusEl = document.getElementById("socDpbStatus");
  const dpbAckEl = document.getElementById("socDpbAck");
  const decoyStatusEl = document.getElementById("socDecoyStatus");
  const defconBadge = document.getElementById("socDefconBadge");

  const dossierIp = document.getElementById("dossierIp");
  const dossierIsp = document.getElementById("dossierIsp");
  const dossierLoc = document.getElementById("dossierLoc");
  const socAttackerOs = document.getElementById("socAttackerOs");
  const socAttackerScreen = document.getElementById("socAttackerScreen");
  const socAttackerSpecs = document.getElementById("socAttackerSpecs");
  const socCanaryStatus = document.getElementById("socCanaryStatus");
  const socPayloadCode = document.getElementById("socPayloadCode");
  const socTargetEndpoint = document.getElementById("socTargetEndpoint");

  if (ipEl) ipEl.textContent = ip;
  if (dossierIp) dossierIp.textContent = ip;
  if (locEl) locEl.innerHTML = `<span class="geo-flag">🇳🇱</span> ${loc}`;
  if (dossierLoc) dossierLoc.textContent = loc;
  if (ispEl) ispEl.textContent = isp;
  if (dossierIsp) dossierIsp.textContent = isp;

  let threatLabel = "Recon & Surface Probe";
  let defcon = "DEFCON 2 · ELEVATED INTEL";
  let defconClass = "defcon-2";

  if (msg.includes("SQL")) {
    threatLabel = "SQL Injection Exploit";
    defcon = "DEFCON 1 · CRITICAL INTRUSION";
    defconClass = "defcon-1";
    if (socPayloadCode) socPayloadCode.textContent = meta.payload || "UNION SELECT username, password_hash FROM admin_users --";
    if (socTargetEndpoint) socTargetEndpoint.textContent = "/api/orders (SQLi Intercepted)";
  } else if (msg.includes("BRUTE-FORCE") || meta.type === "bruteforce_start") {
    threatLabel = "Credential Brute-Force";
    defcon = "DEFCON 1 · ACTIVE CRACKING";
    defconClass = "defcon-1";
    if (socPayloadCode) socPayloadCode.textContent = "DICTIONARY CANDIDATES: admin@123, Welcome@123, Admin@2026!";
    if (socTargetEndpoint) socTargetEndpoint.textContent = "/company/login (Rate Threshold Exceeded)";
  } else if (msg.includes("EXFILTRATION") || meta.type === "data_exfiltration") {
    threatLabel = "Decoy Data Exfiltration";
    defcon = "DEFCON 1 · STATUTORY BREACH";
    defconClass = "defcon-1";
    if (socPayloadCode) socPayloadCode.textContent = "GET /api/export -> customer_export.json (14 PII Decoy Records)";
    if (socTargetEndpoint) socTargetEndpoint.textContent = "/api/export (Decoy Honeypot Quarantined)";
  } else if (msg.includes("CANARY") || meta.type === "canary_hit") {
    threatLabel = "Canary Token Attribution";
    defcon = "DEFCON 1 · ATTRIBUTED THREAT";
    defconClass = "defcon-1";
    if (socCanaryStatus) {
      socCanaryStatus.textContent = "TRIGGERED & DE-ANONYMIZED";
      socCanaryStatus.style.color = "#EF4444";
    }
  }

  if (typeEl) typeEl.textContent = threatLabel;
  if (decoyStatusEl) decoyStatusEl.innerHTML = '<span class="kpi-tag amber">HONEYPOT QUARANTINED</span>';
  if (defconBadge) {
    defconBadge.textContent = defcon;
    defconBadge.className = `defcon-badge ${defconClass}`;
  }

  if (meta.ack_number) {
    if (dpbStatusEl) dpbStatusEl.textContent = "AUTO-SUBMITTED";
    if (dpbAckEl) dpbAckEl.innerHTML = `Ack: <b style="color:#F8FAFC;">${meta.ack_number}</b>`;
  }

  if (meta.screen || meta.platform) {
    if (socAttackerOs) socAttackerOs.textContent = meta.platform || "Linux x86_64 (Kali Rolling)";
    if (socAttackerScreen) socAttackerScreen.textContent = `${meta.screen || '1920x1080'} (Canvas Captured)`;
    if (socAttackerSpecs) socAttackerSpecs.textContent = `${meta.cores || 8} Cores · ${meta.timezone || 'Asia/Kolkata (IST)'}`;
  }
}

// 3. Chart.js Threat Activity Timeline Engine
function initThreatChart(initialAlerts) {
  const canvas = document.getElementById("threatChart");
  if (!canvas || typeof Chart === "undefined") return;

  if (threatChart) {
    try { threatChart.destroy(); } catch (e) {}
    threatChart = null;
  }

  const labels = [];
  const points = [];
  const now = Date.now();

  const threatAlerts = (initialAlerts || []).filter(a => a.level === "critical" || a.level === "warning");
  
  if (threatAlerts.length >= 2) {
    let running = 0;
    threatAlerts.forEach(a => {
      running += 1;
      labels.push(new Date(a.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      points.push(running);
    });
  } else {
    for (let i = 8; i >= 1; i--) {
      const t = new Date(now - i * 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      labels.push(t);
      points.push(Math.max(1, 4 - Math.floor(i / 2)));
    }
    labels.push(new Date(now).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    points.push(points[points.length - 1] + (threatAlerts.length > 0 ? 2 : 1));
  }

  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 120);
  gradient.addColorStop(0, "rgba(239, 68, 68, 0.35)");
  gradient.addColorStop(1, "rgba(239, 68, 68, 0.0)");

  threatChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Intrusion Frequency & Velocity",
        data: points,
        borderColor: "#EF4444",
        borderWidth: 2.2,
        backgroundColor: gradient,
        fill: true,
        tension: 0.38,
        pointRadius: 3.5,
        pointBackgroundColor: "#EF4444",
        pointBorderColor: "#FFFFFF",
        pointBorderWidth: 1.5,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0B1120",
          titleColor: "#38BDF8",
          bodyColor: "#F8FAFC",
          borderColor: "rgba(239, 68, 68, 0.4)",
          borderWidth: 1,
          padding: 10,
          displayColors: false,
          callbacks: {
            label: (ctx) => ` Threat Velocity: ${ctx.parsed.y} detections`
          }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { font: { family: "JetBrains Mono, monospace", size: 10 }, color: "#64748B" }
        },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { precision: 0, font: { family: "JetBrains Mono, monospace", size: 10 }, color: "#64748B" }
        }
      }
    }
  });
}

function pushThreatPoint(alert) {
  if (!threatChart) return;
  try {
    const prev = threatChart.data.datasets[0].data.slice(-1)[0] || 0;
    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    threatChart.data.labels.push(nowStr);
    threatChart.data.datasets[0].data.push(prev + (alert.level === "critical" ? 2 : 1));
    if (threatChart.data.labels.length > 15) {
      threatChart.data.labels.shift();
      threatChart.data.datasets[0].data.shift();
    }
    threatChart.update("none");
  } catch (err) {
    console.warn("Chart point push error:", err);
  }
}

// 4. Auto-Reconnecting WebSocket Stream with Heartbeat
function setupAlertWebSocket() {
  const badge = document.getElementById("socStreamBadge");
  const textEl = document.getElementById("socStreamText");

  function setBadge(state) {
    if (!badge || !textEl) return;
    badge.className = `soc-stream-pill ${state}`;
    if (state === "online") textEl.textContent = "LIVE WSS STREAMING";
    else if (state === "reconnecting") textEl.textContent = "RECONNECTING WSS…";
    else textEl.textContent = "WSS DISCONNECTED";
  }

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${proto}://${location.host}/ws/alerts`;

  try {
    socWs = new WebSocket(wsUrl);
  } catch (err) {
    setBadge("reconnecting");
    scheduleWsReconnect();
    return;
  }

  socWs.onopen = () => {
    setBadge("online");
    wsReconnectAttempts = 0;
    if (pollingFallbackInterval) {
      clearInterval(pollingFallbackInterval);
      pollingFallbackInterval = null;
    }
  };

  socWs.onmessage = (evt) => {
    try {
      const a = JSON.parse(evt.data);
      handleIncomingAlert(a);
    } catch (e) {
      console.error("Alert parse error:", e);
    }
  };

  socWs.onerror = () => {
    setBadge("reconnecting");
  };

  socWs.onclose = () => {
    setBadge("reconnecting");
    scheduleWsReconnect();
  };
}

function scheduleWsReconnect() {
  if (wsReconnectTimer) return;
  wsReconnectAttempts++;
  const delay = Math.min(2000 * wsReconnectAttempts, 10000);
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    setupAlertWebSocket();
  }, delay);

  if (!pollingFallbackInterval) {
    pollingFallbackInterval = setInterval(refreshAlertsHttp, 3500);
  }
}

function refreshAlertsHttp() {
  fetch("/api/alerts").then(r => r.json()).then(list => {
    if (Array.isArray(list) && list.length > window.ALL_ALERTS.length) {
      const newItems = list.slice(0, list.length - window.ALL_ALERTS.length);
      newItems.reverse().forEach(handleIncomingAlert);
    }
  }).catch(() => {});
}

function handleIncomingAlert(a) {
  if (a.id && window.ALL_ALERTS.some(x => x.id === a.id)) return;

  window.ALL_ALERTS.unshift(a);
  const totalCountEl = document.getElementById("totalAlertsCount");
  if (totalCountEl) totalCountEl.textContent = String(window.ALL_ALERTS.length);

  renderAlertFeed();
  try { updateSocAttackerCard(a); } catch (e) {}
  try { pushThreatPoint(a); } catch (e) {}
  try { pushNotifPanelItem(a); } catch (e) {}
  try { bumpNotifBadge(); } catch (e) {}
  try { showEmergencyAlert(a); } catch (e) {}
  try { showThreatToast(a); } catch (e) {}

  const securityTab = document.getElementById("tab-security");
  const dot = document.getElementById("alertDot");
  if (dot && securityTab && securityTab.classList.contains("hidden")) {
    dot.classList.add("show");
  }

  if (a.message && (a.message.includes("submitted to the Data Protection Board") || a.message.includes("DPDP BREACH REPORT AUTO-SUBMITTED"))) {
    renderSubmittedReports();
  }
}

// 5. Submitted DPB Reports Feed
function renderSubmittedReports() {
  const box = document.getElementById("submittedReports");
  if (!box) return;

  fetch("/api/submitted-reports")
    .then(r => r.json())
    .then(list => {
      box.innerHTML = "";
      if (!list || list.length === 0) {
        box.innerHTML = '<p class="muted small" style="text-align:center;padding:20px 0;">No filings submitted yet. Trigger an attack to file automatically.</p>';
        return;
      }
      list.forEach(r => {
        const t = new Date(r.submitted_at * 1000).toLocaleString();
        const stage = (r.stage || "statutory").toUpperCase();
        const div = document.createElement("div");
        div.className = "alert-item alert-critical";
        div.style.marginBottom = "8px";
        div.innerHTML = `
          <span class="alert-ico">📄</span>
          <span class="alert-body">
            <span class="alert-time">${t}</span>
            <b>${stage} NOTIFICATION</b> · Incident <code>${r.incident_id}</code>
            <div style="margin-top:6px;display:flex;gap:8px;align-items:center;">
              <a href="/api/submitted-reports/${r.filename}" target="_blank" class="btn btn-outline btn-sm" style="padding:3px 8px;font-size:0.75rem;">Download PDF ↗</a>
              <a href="/dpb/submission/${r.ack_number}" target="_blank" class="btn btn-dark btn-sm" style="padding:3px 8px;font-size:0.75rem;">DPB Ack: ${r.ack_number} ↗</a>
            </div>
          </span>`;
        box.appendChild(div);
      });
    })
    .catch(() => {});
}

// 6. Interactive Threat Vector Triggers
window.toggleSimDropdown = function(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById("socSimMenu");
  if (menu) menu.classList.toggle("hidden");
};
document.addEventListener("click", () => {
  const menu = document.getElementById("socSimMenu");
  if (menu) menu.classList.add("hidden");
});

window.triggerSimEvent = async function(type) {
  const menu = document.getElementById("socSimMenu");
  if (menu) menu.classList.add("hidden");

  let payload = "";
  let target = "/api/orders";

  if (type === "sqli_attack") {
    payload = "' UNION SELECT id, username, password_hash, email FROM admin_users --";
    target = "/api/orders?filter=category";
  } else if (type === "bruteforce_start") {
    payload = "DICTIONARY_CRACK: Candidate wordlist loaded (123456...Admin@2026!)";
    target = "/company/login";
  } else if (type === "data_exfiltration") {
    payload = "EXFIL_PII: 14 customer records extracted to customer_export.json";
    target = "/api/export";
  } else if (type === "canary_hit") {
    payload = "CANARY_BEACON: tracking_invoice_90412.pdf phoned home";
    target = "/canary/token-canary-demo-90412";
  }

  showToast(`⚡ Threat Vector Executed: ${type.toUpperCase()}`);

  try {
    const res = await fetch("/api/attacker-session-event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event: type,
        user: "adversary_operator",
        ip: "185.220.101.45 (Tor Relay Amsterdam)",
        tool: "TrapWire Threat Engine",
        payload: payload,
        target: target
      })
    });
    const data = await res.json();
    if (data.dpb_ack) {
      showToast(`📄 DPB Statutory Ack Received: ${data.dpb_ack}`);
    }
  } catch (err) {
    showToast("Attack execution error: " + err.message);
  }
};

window.resetSocDemo = async function() {
  if (!confirm("Reset all SOC incident records, threat timeline points, and alert telemetry?")) return;
  try {
    await fetch("/api/reset-demo");
    window.ALL_ALERTS = [];
    renderAlertFeed();
    renderSubmittedReports();
    if (threatChart) {
      initThreatChart([]);
    }
    const defconBadge = document.getElementById("socDefconBadge");
    if (defconBadge) {
      defconBadge.textContent = "DEFCON 5 · GUARDED";
      defconBadge.className = "defcon-badge defcon-5";
    }
    showToast("Threat matrix state reset successfully.");
  } catch (err) {
    showToast("Reset error: " + err.message);
  }
};

// 7. Statutory 72-Hour Compliance Countdown Clock
function init72HourClock() {
  const hEl = document.getElementById("clockHours");
  const mEl = document.getElementById("clockMins");
  const sEl = document.getElementById("clockSecs");
  if (!hEl || !mEl || !sEl) return;

  let totalSeconds = 72 * 3600 - 45;
  setInterval(() => {
    if (totalSeconds > 0) totalSeconds--;
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    hEl.textContent = String(hrs).padStart(2, "0");
    mEl.textContent = String(mins).padStart(2, "0");
    sEl.textContent = String(secs).padStart(2, "0");
  }, 1000);
}

// 8. Threat Toast Popups
let audioCtx = null;
function playAlertChime(level) {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = level === 'critical' ? 'sawtooth' : 'sine';
    const freq = level === 'critical' ? 880 : 587.33;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    if (level === 'critical') {
      osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.35);
    }
    gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.45);
  } catch (e) {}
}

function showThreatToast(a) {
  const stack = document.getElementById("liveToastStack");
  if (!stack) return;
  playAlertChime(a.level);

  let title = "🛡️ Security Threat Telemetry";
  if (a.level === "critical") {
    if (a.message.includes("EXFILTRATION")) title = "🚨 DATA EXFILTRATION DETECTED";
    else if (a.message.includes("CANARY")) title = "🎯 CANARY TRACKING BEACON TRIPPED";
    else if (a.message.includes("BRUTE-FORCE")) title = "💥 CREDENTIAL BRUTE-FORCE ATTACK";
    else if (a.message.includes("SQL")) title = "💉 SQL INJECTION EXPLOIT DETECTED";
    else if (a.message.includes("HACKER WORKSTATION")) title = "🚨 HACKER WORKSTATION ACTIVE";
    else if (a.message.includes("DPDP BREACH REPORT AUTO-SUBMITTED")) title = "📄 STATUTORY DPDP REPORT FILED";
    else title = "🚨 CRITICAL INTRUSION DETECTED";
  } else if (a.level === "warning") {
    if (a.message.includes("LOGIN ATTEMPT")) title = "⚠️ ATTACKER LOGIN ATTEMPT";
    else if (a.message.includes("PORT")) title = "🔍 PORT RECONNAISSANCE PROBE";
    else if (a.message.includes("VPN")) title = "🌐 VPN PROXY HOPPING DETECTED";
    else if (a.message.includes("XSS")) title = "⚡ XSS EXPLOIT INTERCEPTED";
    else if (a.message.includes("TRAVERSAL")) title = "📂 PATH TRAVERSAL INTERCEPTED";
    else title = "⚠️ ANOMALOUS ACTIVITY OBSERVED";
  }

  const toast = document.createElement("div");
  toast.className = `threat-toast toast-${a.level || 'info'}`;
  
  const meta = a.meta || {};
  const ip = meta.ip || meta.attacker_ip || "185.220.101.45";
  const isp = meta.isp || meta.attacker_isp || "Reliance Jio / Tor Relay";
  const ackNum = meta.ack_number || null;

  let actionButtonsHtml = `
    <div style="display:flex;gap:8px;margin-top:6px;align-items:center;">
      <button class="emergency-btn-view" style="padding:4px 10px;font-size:0.72rem;" onclick="openForensicModalFromToast('${encodeURIComponent(JSON.stringify(a))}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z"/></svg>
        Inspect Forensics
      </button>
  `;

  if (ackNum) {
    actionButtonsHtml += `
      <a href="/dpb/submission/${ackNum}" target="_blank" class="emergency-btn-dismiss" style="padding:4px 10px;font-size:0.72rem;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
        <span>DPB Ack: ${ackNum} ↗</span>
      </a>
    `;
  }
  actionButtonsHtml += `</div>`;

  toast.innerHTML = `
    <div class="toast-head">
      <div class="toast-title-wrap">
        <span class="toast-dot"></span>
        <span class="toast-title">${title}</span>
      </div>
      <button class="toast-close" onclick="this.closest('.threat-toast').remove()">&times;</button>
    </div>
    <div class="toast-msg">${a.message}</div>
    <div class="toast-meta-pills">
      <span class="toast-pill ip">📡 IP: ${ip}</span>
      <span class="toast-pill isp">🏢 ISP: ${isp}</span>
      ${ackNum ? `<span class="toast-pill" style="color:#10B981;border-color:rgba(16,185,129,0.3);">📄 DPB: ${ackNum}</span>` : ''}
    </div>
    ${actionButtonsHtml}
    <div class="toast-progress"></div>
  `;

  stack.prepend(toast);

  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(120%)";
      setTimeout(() => toast.remove(), 300);
    }
  }, 10000);
}

window.openForensicModalFromToast = function(encodedAlert) {
  try {
    const a = JSON.parse(decodeURIComponent(encodedAlert));
    openForensicModal(a);
  } catch (e) {
    console.error("Forensic modal open error:", e);
  }
};

// 9. Forensic Dossier Modal
window.openForensicModal = function(a) {
  const modal = document.getElementById("forensicModal");
  if (!modal) return;

  const meta = a.meta || {};
  const ip = meta.ip || meta.attacker_ip || "185.220.101.45";
  const isp = meta.isp || meta.attacker_isp || "Tor Exit Relay / DataCamp Ltd";
  const city = meta.city || "Amsterdam";
  const country = meta.country || "Netherlands";
  const loc = `${city}, ${country}`;
  const t = new Date((a.timestamp || Date.now() / 1000) * 1000).toLocaleString();

  const fmThreatLevel = document.getElementById("fmThreatLevel");
  const fmIp = document.getElementById("fmIp");
  const fmIsp = document.getElementById("fmIsp");
  const fmLoc = document.getElementById("fmLoc");
  const fmTime = document.getElementById("fmTime");
  const fmOs = document.getElementById("fmOs");
  const fmScreen = document.getElementById("fmScreen");
  const fmCores = document.getElementById("fmCores");
  const fmTimezone = document.getElementById("fmTimezone");
  const fmPayload = document.getElementById("fmPayload");
  const fmAckId = document.getElementById("fmAckId");
  const fmDpbLink = document.getElementById("fmDpbLink");

  if (fmThreatLevel) {
    fmThreatLevel.textContent = a.level === "critical" ? "CRITICAL THREAT" : "SUSPICIOUS INTRUSION";
    fmThreatLevel.className = a.level === "critical" ? "status-pill status-cancelled" : "status-pill status-shipped";
  }
  if (fmIp) fmIp.textContent = ip;
  if (fmIsp) fmIsp.textContent = isp;
  if (fmLoc) fmLoc.textContent = loc;
  if (fmTime) fmTime.textContent = t;

  if (fmOs) fmOs.textContent = meta.platform || "Linux x86_64 (Kali Rolling)";
  if (fmScreen) fmScreen.textContent = meta.screen || "1920 x 1080";
  if (fmCores) fmCores.textContent = meta.cores ? `${meta.cores} Cores` : "8 Cores";
  if (fmTimezone) fmTimezone.textContent = meta.timezone || "Asia/Kolkata (IST)";

  if (fmPayload) {
    fmPayload.textContent = meta.payload || a.message;
  }

  const ack = meta.ack_number || "DPB-2026-ACTIVE";
  if (fmAckId) fmAckId.textContent = ack;
  if (fmDpbLink) {
    fmDpbLink.href = meta.ack_number ? `/dpb/submission/${meta.ack_number}` : "/dpb";
  }

  modal.classList.remove("hidden");
};

window.closeForensicModal = function() {
  const modal = document.getElementById("forensicModal");
  if (modal) modal.classList.add("hidden");
};

window.downloadForensicPdf = function() {
  const btn = document.getElementById("reportBtn");
  if (btn) btn.click();
};

window.showToast = function(msg) {
  const stack = document.getElementById("liveToastStack");
  if (!stack) return;
  const toast = document.createElement("div");
  toast.className = "threat-toast toast-info";
  toast.innerHTML = `<div class="toast-head"><span class="toast-title">🛡️ TRAPWIRE SOC</span><button class="toast-close" onclick="this.closest('.threat-toast').remove()">&times;</button></div><div class="toast-msg">${msg}</div><div class="toast-progress"></div>`;
  stack.prepend(toast);
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 6000);
};

// 10. Report button handler
const reportBtn = document.getElementById("reportBtn");
if (reportBtn) {
  reportBtn.addEventListener("click", async () => {
    const msg = document.getElementById("reportMsg");
    if (msg) {
      msg.textContent = "Generating official DPDP breach notification PDF…";
      msg.className = "msg";
    }
    try {
      const res = await fetch("/api/report", { method: "POST" });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "DPDP_Breach_Notification_Report.pdf";
        a.click();
        if (msg) {
          msg.textContent = "Report generated and downloaded.";
          msg.className = "msg";
        }
      } else {
        const j = await res.json().catch(() => ({}));
        if (msg) {
          msg.textContent = j.error || "Unable to generate report.";
          msg.className = "msg error";
        }
      }
    } catch (e) {
      if (msg) {
        msg.textContent = "Download failed: " + e.message;
        msg.className = "msg error";
      }
    }
  });
}

// 11. Bootstrapping on Page Load
document.addEventListener("DOMContentLoaded", () => {
  init72HourClock();

  if (!window.SUSPICIOUS) {
    fetch("/api/alerts")
      .then(r => r.json())
      .then(list => {
        if (Array.isArray(list)) {
          window.ALL_ALERTS = list.slice();
          const totalCountEl = document.getElementById("totalAlertsCount");
          if (totalCountEl) totalCountEl.textContent = String(window.ALL_ALERTS.length);
          renderAlertFeed();
          if (list.length > 0) {
            updateSocAttackerCard(list[0]);
          }
          initThreatChart(list.slice().reverse());
        }
      })
      .catch(err => {
        console.warn("Failed to load initial alerts:", err);
        initThreatChart([]);
      });

    renderSubmittedReports();
    setupAlertWebSocket();
  }
});

// ==========================================================================
// ADMIN PRIVILEGE: ADD & DELETE CUSTOMER ORDERS
// ==========================================================================
window.openOrderModal = function() {
  const modal = document.getElementById("addOrderModal");
  if (modal) {
    modal.classList.remove("hidden");
    modal.style.setProperty("display", "flex", "important");
    setTimeout(() => document.getElementById("ordCustomer")?.focus(), 100);
  }
};

window.closeOrderModal = function() {
  const modal = document.getElementById("addOrderModal");
  if (modal) {
    modal.classList.add("hidden");
    modal.style.setProperty("display", "none", "important");
  }
};

window.handleOrderFormSubmit = async function(e) {
  if (e) e.preventDefault();
  const saveBtn = document.getElementById("saveAddOrderBtn");
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving Order...";
  }

  const custName = (document.getElementById("ordCustomer")?.value || "").trim();
  if (!custName) {
    alert("Please enter customer full name.");
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = "Save Customer Order";
    }
    return;
  }

  const cleanName = custName.toLowerCase().replace(/[^a-z0-9]/g, "");
  const randNum = Math.floor(1000 + Math.random() * 9000);
  const email = (document.getElementById("ordEmail")?.value || "").trim() || `${cleanName || "user"}${randNum}@customer.in`;
  const phone = (document.getElementById("ordPhone")?.value || "").trim() || `+91 98${Math.floor(10000000 + Math.random() * 90000000)}`;
  const item = (document.getElementById("ordItem")?.value || "").trim() || "Enterprise Secure Token";
  const valRaw = parseFloat(document.getElementById("ordValue")?.value);
  const orderValue = isNaN(valRaw) || valRaw <= 0 ? 12500 : valRaw;
  const status = document.getElementById("ordStatus")?.value || "Delivered";
  const cardLast4 = (document.getElementById("ordCard")?.value || "").trim() || String(randNum);
  const aadhaar = (document.getElementById("ordAadhaar")?.value || "").trim();
  const pan = (document.getElementById("ordPan")?.value || "").trim();
  const address = (document.getElementById("ordAddress")?.value || "").trim() || "Cyber Defense Center, Bengaluru";

  const payload = {
    customer_name: custName,
    email: email,
    phone: phone,
    item: item,
    order_value: orderValue,
    status: status,
    card_last4: cardLast4,
    aadhaar: aadhaar,
    pan: pan,
    address: address
  };

  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (data.ok && data.record) {
      window.insertOrderRowToTable(data.record);
      window.closeOrderModal();
      document.getElementById("addOrderForm")?.reset();
      if (typeof showToast === "function") {
        showToast(`Order ${data.record.order_id} added successfully!`);
      } else {
        alert(`Order ${data.record.order_id} added successfully!`);
      }
    } else {
      alert("Failed to add order: " + (data.error || "Server rejected request."));
    }
  } catch (err) {
    console.error("Error creating order:", err);
    alert("Network error creating order: " + err.message);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = "Save Customer Order";
    }
  }
};

window.insertOrderRowToTable = function(r) {
  const table = document.getElementById("ordersTable");
  const tbody = table ? table.querySelector("tbody") : null;
  if (!tbody) return;

  const emptyRow = tbody.querySelector(".empty-state-row");
  if (emptyRow) emptyRow.remove();

  const initial = (r.customer_name || "?").trim()[0]?.toUpperCase() || "?";
  const statusLower = (r.status || "processing").toLowerCase();
  const valFormatted = Number(r.order_value || 0).toLocaleString("en-IN");

  const tr = document.createElement("tr");
  tr.dataset.status = r.status;
  tr.dataset.search = `${(r.customer_name || "").toLowerCase()} ${(r.order_id || "").toLowerCase()}`;
  tr.dataset.value = r.order_value;

  tr.innerHTML = `
    <td class="mono">${r.order_id}</td>
    <td>
      <div class="cust-cell">
        <span class="cust-avatar">${initial}</span>
        ${r.customer_name}
      </div>
    </td>
    <td class="mono">${r.phone_display || r.phone || "—"}</td>
    <td>${r.email_display || r.email || "—"}</td>
    <td class="mono">${r.aadhaar_display || "—"}</td>
    <td class="mono">${r.pan_display || "—"}</td>
    <td class="mono">${r.card_display || "—"}</td>
    <td>${r.address || "—"}</td>
    <td>${r.item}</td>
    <td><span class="status-pill status-${statusLower}">${r.status}</span></td>
    <td class="mono">₹${valFormatted}</td>
    <td style="text-align:right;">
      <button class="btn-delete-order" data-order-id="${r.order_id}" onclick="window.handleDeleteOrder('${r.order_id}', this)" title="Delete Order" style="background:none; border:none; color:var(--text-muted); cursor:pointer; padding:4px 8px; border-radius:4px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
      </button>
    </td>
  `;

  tbody.insertBefore(tr, tbody.firstChild);
  window.updateOrderStatsDisplay();
  if (typeof window.refreshOrdersFilter === "function") window.refreshOrdersFilter();
};

window.handleDeleteOrder = async function(orderId, btn) {
  if (!confirm(`Are you sure you want to delete order ${orderId}?`)) return;
  try {
    const res = await fetch(`/api/orders/${orderId}`, { method: "DELETE" });
    const data = await res.json();
    if (data.ok) {
      const row = btn.closest("tr");
      row?.remove();
      window.updateOrderStatsDisplay();
      if (typeof window.refreshOrdersFilter === "function") window.refreshOrdersFilter();
      if (typeof showToast === "function") showToast(`Order ${orderId} deleted.`);
    }
  } catch (err) {
    console.error("Error deleting order:", err);
  }
};

window.updateOrderStatsDisplay = function() {
  const table = document.getElementById("ordersTable");
  const tbody = table ? table.querySelector("tbody") : null;
  const rows = Array.from(tbody ? tbody.querySelectorAll("tr:not(.empty-state-row)") : []);
  const count = rows.length;

  const tableCount = document.getElementById("tableCount");
  if (tableCount) tableCount.textContent = `${count} records`;

  const statCards = document.querySelectorAll("#tab-orders .stats-row .stat-card");
  if (statCards[0]) {
    const numEl = statCards[0].querySelector(".stat-num");
    if (numEl) numEl.textContent = count;
  }

  let totalVal = 0;
  let deliveredCount = 0;
  rows.forEach(r => {
    const v = parseFloat(r.dataset.value) || 0;
    totalVal += v;
    if (r.dataset.status === "Delivered") deliveredCount++;
  });

  if (statCards[1]) {
    const valEl = statCards[1].querySelector(".stat-num");
    if (valEl) valEl.textContent = `₹${totalVal.toLocaleString("en-IN")}`;
  }

  if (statCards[2]) {
    const rateEl = statCards[2].querySelector(".stat-num");
    const rate = count > 0 ? ((deliveredCount / count) * 100).toFixed(1) : "0";
    if (rateEl) rateEl.textContent = `${rate}%`;
    const trendEl = statCards[2].querySelector(".stat-trend");
    if (trendEl) trendEl.textContent = `${deliveredCount} of ${count} delivered`;
  }

  if (count === 0 && tbody && !tbody.querySelector(".empty-state-row")) {
    tbody.innerHTML = `
      <tr class="empty-state-row">
        <td colspan="12" style="text-align: center; padding: 48px 16px; color: var(--text-muted);">
          <div style="font-size: 32px; margin-bottom: 12px; opacity: 0.7;">📦</div>
          <div style="font-weight: 600; font-size: 15px; color: var(--text-primary); margin-bottom: 6px;">No Customer Order Data on Record</div>
          <div style="font-size: 13px; max-width: 480px; margin: 0 auto 16px; line-height: 1.5; color: var(--text-muted);">
            All synthetic customer records have been purged. As an administrator, you have full privilege to add authentic orders to this production database.
          </div>
          <button class="btn btn-primary" id="emptyAddOrderBtn" onclick="openOrderModal()" style="display:inline-flex; align-items:center; gap:6px; font-size:13px; padding:7px 18px; background:#2563eb; color:#fff; border-radius:6px; font-weight:600; cursor:pointer; border:none;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:14px;height:14px;"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            + Add Customer Order
          </button>
        </td>
      </tr>
    `;
  }
};

function setupOrderAdminControls() {
  const modal = document.getElementById("addOrderModal");
  modal?.addEventListener("click", (e) => {
    if (e.target === modal) window.closeOrderModal();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", setupOrderAdminControls);
} else {
  setupOrderAdminControls();
}
