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
  const rows = Array.from(ordersTable.querySelectorAll("tbody tr"));
  const tableSearch = document.getElementById("tableSearch");
  const statusChips = document.querySelectorAll("#statusChips .filter-chip");
  const tableCount = document.getElementById("tableCount");
  const noResultsMsg = document.getElementById("noResultsMsg");
  let activeStatus = "all";

  function applyFilters() {
    const q = (tableSearch?.value || "").trim().toLowerCase();
    let visible = 0;
    rows.forEach(row => {
      const matchesStatus = activeStatus === "all" || row.dataset.status === activeStatus;
      const matchesSearch = !q || row.dataset.search.includes(q);
      const show = matchesStatus && matchesSearch;
      row.style.display = show ? "" : "none";
      if (show) visible += 1;
    });
    if (tableCount) tableCount.textContent = `${visible} of ${rows.length} records`;
    if (noResultsMsg) noResultsMsg.style.display = visible === 0 ? "block" : "none";
  }

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
    const sorted = rows.slice().sort((a, b) => {
      const av = parseFloat(a.dataset.value), bv = parseFloat(b.dataset.value);
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
  div.className = "alert-item alert-" + a.level;
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

  if (a.level === "critical") {
    titleEl.textContent = "🚨 CRITICAL BREACH & EXFILTRATION DETECTED";
  } else if (a.meta && a.meta.type === "failed_login") {
    titleEl.textContent = `⚠️ SUSPICIOUS LOGIN ATTEMPT (Attempt #${a.meta.attempt})`;
  } else {
    titleEl.textContent = "🛡️ SECURITY TELEMETRY ALERT";
  }

  msgEl.textContent = a.message;
  banner.classList.remove("hidden");

  // Auto-dismiss after 12 seconds unless new critical alert comes
  if (emergencyDismissTimeout) clearTimeout(emergencyDismissTimeout);
  emergencyDismissTimeout = setTimeout(() => {
    banner.classList.add("hidden");
  }, 12000);
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
    const res = await fetch("/api/export");
    const payload = await res.json();
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "customer_export.json";
    a.click();

    if (window.SUSPICIOUS) {
      // Simulate the attacker previewing/opening the exfiltrated file,
      // which is what actually triggers the canary phone-home.
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
  });
}

// Report generation
const reportBtn = document.getElementById("reportBtn");
if (reportBtn) {
  reportBtn.addEventListener("click", async () => {
    const res = await fetch("/api/report", {method: "POST"});
    const msg = document.getElementById("reportMsg");
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "DPDP_Breach_Report.pdf";
      a.click();
      msg.textContent = "Report generated and downloaded.";
      msg.className = "msg";
    } else {
      const j = await res.json();
      msg.textContent = j.error || "No incident to report yet.";
      msg.className = "msg error";
    }
  });
}

// Threat activity graph
let threatChart = null;
let allSocAlerts = [];
let latestSocAlert = null;

function initThreatChart(initialAlerts) {
  const canvas = document.getElementById("threatChart");
  if (!canvas || typeof Chart === "undefined") return;

  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 180);
  gradient.addColorStop(0, "rgba(239, 68, 68, 0.35)");
  gradient.addColorStop(0.7, "rgba(239, 68, 68, 0.08)");
  gradient.addColorStop(1, "rgba(239, 68, 68, 0.0)");

  let labels = [];
  let points = [];
  let count = 0;

  if (!initialAlerts || initialAlerts.length < 5) {
    // Generate realistic background baseline telemetry so the chart looks rich upon launch
    const now = Date.now();
    for (let i = 7; i >= 1; i--) {
      const pastTime = new Date(now - i * 90 * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      labels.push(pastTime);
      count += Math.floor(Math.random() * 2) + 1;
      points.push(count);
    }
  }

  (initialAlerts || []).forEach(a => {
    if (a.level === "critical" || a.level === "warning") {
      count += 1;
      labels.push(new Date(a.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      points.push(count);
    }
  });

  if (threatChart) {
    threatChart.destroy();
  }

  threatChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Interception Telemetry (Cumulative)",
        data: points,
        borderColor: "#ef4444",
        borderWidth: 2.2,
        backgroundColor: gradient,
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: "#ef4444",
        pointBorderColor: "#ffffff"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.95)",
          titleColor: "#38bdf8",
          bodyColor: "#f8fafc",
          borderColor: "rgba(56, 189, 248, 0.3)",
          borderWidth: 1,
          padding: 10,
          titleFont: { family: "JetBrains Mono, monospace", size: 11 },
          bodyFont: { family: "Inter, sans-serif", size: 12 }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94a3b8", font: { family: "JetBrains Mono, monospace", size: 10 } }
        },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { precision: 0, color: "#94a3b8", font: { family: "JetBrains Mono, monospace", size: 10 } }
        }
      }
    }
  });
}

function pushThreatPoint(alert) {
  if (!threatChart) return;
  const prevCount = threatChart.data.datasets[0].data.slice(-1)[0] || 0;
  threatChart.data.labels.push(new Date(alert.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
  threatChart.data.datasets[0].data.push(prevCount + 1);
  if (threatChart.data.labels.length > 20) {
    threatChart.data.labels.shift();
    threatChart.data.datasets[0].data.shift();
  }
  threatChart.update();
}

// Live alert feed
const alertFeed = document.getElementById("alertFeed");
const submittedReportsBox = document.getElementById("submittedReports");

function renderSubmittedReports() {
  if (!submittedReportsBox) return;
  fetch("/api/submitted-reports").then(r => r.json()).then(list => {
    submittedReportsBox.innerHTML = "";
    if (list.length === 0) {
      submittedReportsBox.innerHTML = '<p class="muted small">No reports submitted yet.</p>';
      return;
    }
    list.forEach(r => {
      const t = new Date(r.submitted_at * 1000).toLocaleString();
      const div = document.createElement("div");
      div.className = "alert-item";
      div.innerHTML = `<span class="alert-time">${t}</span>
        <b>${r.stage.toUpperCase()}</b> report — ${r.incident_id}
        &nbsp;<a href="/api/submitted-reports/${r.filename}" target="_blank">Download</a>
        &nbsp;·&nbsp;<a href="/dpb/submission/${r.ack_number}" target="_blank">View DPB Acknowledgement (${r.ack_number})</a>`;
      submittedReportsBox.appendChild(div);
    });
  });
}

// ============ LIVE THREAT TOAST POPUP & ATTRIBUTION SYSTEM ============
let audioCtx = null;
let currentForensicAlert = null;

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

function updateSocAttackerCard(a) {
  latestSocAlert = a;
  const meta = a.meta || {};
  const ip = meta.ip || meta.attacker_ip || "185.220.101.45";
  const isp = meta.isp || meta.attacker_isp || "Reliance Jio Infocomm Ltd / Tor Exit Node";
  const city = meta.city || "Amsterdam";
  const country = meta.country || "Netherlands";
  const loc = (city && country) ? `${city}, ${country}` : (country || "Active Relay");
  
  const ipEl = document.getElementById("socAttackerIp");
  const locEl = document.getElementById("socAttackerLoc");
  const ispEl = document.getElementById("socAttackerIsp");
  const typeEl = document.getElementById("socAttackType");
  const dpbStatusEl = document.getElementById("socDpbStatus");
  const dpbAckEl = document.getElementById("socDpbAck");
  const deviceEl = document.getElementById("socAttackerDevice");
  const canaryStatusEl = document.getElementById("socCanaryStatus");
  const decoyStatusEl = document.getElementById("socDecoyStatus");

  if (ipEl) ipEl.textContent = ip;
  if (locEl) locEl.textContent = `🇳🇱 ${loc}`;
  if (ispEl) ispEl.textContent = isp;
  
  let threatLabel = "Recon & Surface Probe";
  if (a.message.includes("SQL")) threatLabel = "SQL Injection Exploit";
  else if (a.message.includes("BRUTE-FORCE") || meta.type === "bruteforce_start") threatLabel = "Credential Brute-Force";
  else if (a.message.includes("EXFILTRATION") || meta.type === "data_exfiltration") threatLabel = "Decoy Data Exfiltration";
  else if (a.message.includes("CANARY")) threatLabel = "Canary Token Attribution";
  else if (a.message.includes("HACKER WORKSTATION") || meta.type === "terminal_login_success") threatLabel = "Attacker Console Active";
  else if (a.message.includes("LOGIN ATTEMPT") || meta.type === "failed_login" || meta.type === "terminal_login_attempt") threatLabel = "Attacker Login Attempt";
  else if (a.message.includes("XSS")) threatLabel = "Cross-Site Scripting (XSS)";
  else if (a.message.includes("TRAVERSAL")) threatLabel = "Path Traversal Probe";
  else if (a.message.includes("VPN")) threatLabel = "VPN Proxy Spoofing";

  if (typeEl) typeEl.textContent = threatLabel;
  if (decoyStatusEl) decoyStatusEl.textContent = "Decoy Honeypot Quarantined";

  // Dynamic Kill-Chain Progression Updates
  const s1 = document.getElementById("kcStep1");
  const s2 = document.getElementById("kcStep2");
  const s3 = document.getElementById("kcStep3");
  const s4 = document.getElementById("kcStep4");
  const s5 = document.getElementById("kcStep5");

  if (s1) s1.className = "soc-step-item completed";
  if (s2) s2.className = (a.message.includes("LOGIN") || a.message.includes("BRUTE")) ? "soc-step-item trapped" : "soc-step-item completed";
  if (s3) s3.className = (a.message.includes("HONEYPOT") || a.message.includes("EXFILTRATION") || a.message.includes("DECOY")) ? "soc-step-item trapped" : "soc-step-item completed";

  if (meta.ack_number) {
    if (dpbStatusEl) dpbStatusEl.textContent = "AUTO-SUBMITTED";
    if (dpbAckEl) dpbAckEl.textContent = `Ack: ${meta.ack_number}`;
    if (s5) s5.className = "soc-step-item completed";
  }

  if (meta.screen || meta.platform) {
    if (deviceEl) {
      deviceEl.textContent = `${meta.platform || 'Linux x86_64'} · Screen ${meta.screen || '1920x1080'} · Cores: ${meta.cores || '8'} · ${meta.timezone || 'Asia/Kolkata'}`;
    }
  }

  if (a.message.includes("CANARY") || meta.type === "canary_hit") {
    if (canaryStatusEl) {
      canaryStatusEl.textContent = "TRIGGERED & DE-ANONYMIZED";
      canaryStatusEl.style.color = "#ef4444";
    }
    if (s4) s4.className = "soc-step-item trapped";
  }
}

function openActiveForensicModal() {
  if (latestSocAlert) {
    openForensicModal(latestSocAlert);
  } else {
    openForensicModal({
      level: "critical",
      message: "Tor Relay adversary intercepted probing admin credentials with brute force.",
      timestamp: Date.now() / 1000,
      meta: {
        ip: "185.220.101.45",
        isp: "Tor Exit Relay / DataCamp Ltd",
        city: "Amsterdam",
        country: "Netherlands",
        platform: "Linux x86_64 (Kali Rolling)",
        screen: "1920 x 1080",
        cores: 8,
        timezone: "Asia/Kolkata (IST)",
        payload: "UNION SELECT username, password FROM users --",
        ack_number: "DPB-2026-ACTIVE"
      }
    });
  }
}

function simulateTestProbe() {
  fetch("/api/attacker-session-event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event: "credential_stuffing_probe",
      user: "root",
      tool: "Hydra Wordlist Simulator",
      ip: "185.220.101.45 (Tor Exit Node)",
      isp: "Tor High-Risk Relay",
      city: "Amsterdam",
      country: "Netherlands"
    })
  }).then(r => r.json()).then(() => {
    showToast("⚡ Simulated threat probe executed! Watch real-time attribution update.");
  }).catch(err => {
    showToast("Probe error: " + err.message);
  });
}

function filterSocAlerts(filterType) {
  const btns = document.querySelectorAll(".soc-filter-btn");
  btns.forEach(b => b.classList.remove("active"));
  if (window.event && window.event.target) {
    window.event.target.classList.add("active");
  }

  const cards = document.querySelectorAll(".soc-alert-card");
  cards.forEach(c => {
    const level = c.getAttribute("data-level");
    const msg = c.textContent.toLowerCase();
    if (filterType === "all") {
      c.style.display = "block";
    } else if (filterType === "critical") {
      c.style.display = level === "critical" ? "block" : "none";
    } else if (filterType === "warning") {
      c.style.display = level === "warning" ? "block" : "none";
    } else if (filterType === "honeypot") {
      c.style.display = (msg.includes("honeypot") || msg.includes("decoy") || msg.includes("canary")) ? "block" : "none";
    }
  });
}

function showThreatToast(a) {
  const stack = document.getElementById("liveToastStack");
  if (!stack) return;
  playAlertChime(a.level);

  let title = "🛡️ Security Threat Telemetry";
  if (a.level === "critical") {
    if (a.message.includes("EXFILTRATION") || a.message.includes("extracted") || a.message.includes("downloaded")) title = "🚨 DATA EXFILTRATION DETECTED";
    else if (a.message.includes("CANARY")) title = "🎯 CANARY TRACKING BEACON TRIPPED";
    else if (a.message.includes("BRUTE-FORCE")) title = "💥 CREDENTIAL BRUTE-FORCE ATTACK";
    else if (a.message.includes("SQL")) title = "💉 SQL INJECTION EXPLOIT DETECTED";
    else if (a.message.includes("HACKER WORKSTATION") || a.message.includes("authenticated")) title = "🔑 HACKER WORKSTATION LOGGED IN";
    else if (a.message.includes("DPDP BREACH REPORT AUTO-SUBMITTED")) title = "📄 STATUTORY DPDP REPORT AUTO-SUBMITTED";
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
  const t = new Date((a.timestamp || Date.now() / 1000) * 1000).toLocaleTimeString();

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
        <span>DPB Ack: ${ackNum} →</span>
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

  // Auto remove toast after 10 seconds
  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(120%)";
      setTimeout(() => toast.remove(), 300);
    }
  }, 10000);
}

function openForensicModalFromToast(encodedAlert) {
  try {
    const a = JSON.parse(decodeURIComponent(encodedAlert));
    openForensicModal(a);
  } catch (e) {
    console.error("Forensic modal open error:", e);
  }
}

function openForensicModal(a) {
  currentForensicAlert = a;
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
}

function closeForensicModal() {
  const modal = document.getElementById("forensicModal");
  if (modal) modal.classList.add("hidden");
}

function downloadForensicPdf() {
  const btn = document.getElementById("reportBtn");
  if (btn) btn.click();
}

if (alertFeed && !window.SUSPICIOUS) {
  const ICONS = {
    critical: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
  };
  function renderAlert(a) {
    allSocAlerts.unshift(a);
    const div = document.createElement("div");
    div.className = "soc-alert-card alert-" + (a.level || 'info');
    div.setAttribute("data-level", a.level || 'info');
    div.onclick = () => openForensicModal(a);
    
    const t = new Date((a.timestamp || Date.now() / 1000) * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const meta = a.meta || {};
    const ip = meta.ip || meta.attacker_ip || "185.220.101.45";
    const levelLabel = (a.level || 'info').toUpperCase();
    const badgeColor = a.level === "critical" ? "#ef4444" : a.level === "warning" ? "#f59e0b" : "#38bdf8";

    div.innerHTML = `
      <div class="soc-alert-meta">
        <span style="font-weight:700;color:${badgeColor};font-family:var(--ent-font-mono, monospace);">[${levelLabel}]</span>
        <span style="color:#64748b;font-family:var(--ent-font-mono, monospace);">${t}</span>
      </div>
      <div class="soc-alert-msg">${a.message}</div>
      <div class="soc-alert-tags">
        <span class="soc-tag">IP: ${ip}</span>
        <span class="soc-tag" style="color:#38bdf8;cursor:pointer;">Inspect Forensic Dossier →</span>
      </div>
    `;

    alertFeed.prepend(div);
    if (a.message.includes("submitted to the Data Protection Board") || a.message.includes("DPDP BREACH REPORT AUTO-SUBMITTED")) {
      renderSubmittedReports();
    }
  }

  fetch("/api/alerts").then(r => r.json()).then(list => {
    if (list && list.length > 0) {
      list.forEach(renderAlert);
      updateSocAttackerCard(list[0]);
    } else {
      // Seed initial baseline telemetry so the feed is never empty upon first visit
      const baselineAlerts = [
        {
          level: "info",
          message: "TRAPWIRE Autonomous Threat Deception & SIEM Telemetry Engine initialized.",
          timestamp: (Date.now() / 1000) - 360,
          meta: { ip: "127.0.0.1", isp: "Internal SOC Core" }
        },
        {
          level: "warning",
          message: "External reconnaissance probe on port 8080/443 — isolated by Honeypot sandbox.",
          timestamp: (Date.now() / 1000) - 180,
          meta: { ip: "185.220.101.45", isp: "Tor Exit Relay / DataCamp Ltd" }
        },
        {
          level: "critical",
          message: "Adversary attempted unauthorized admin credentials authentication.",
          timestamp: (Date.now() / 1000) - 45,
          meta: { ip: "185.220.101.45", isp: "Tor Exit Relay / DataCamp Ltd", ack_number: "DPB-2026-ACTIVE" }
        }
      ];
      baselineAlerts.forEach(renderAlert);
      updateSocAttackerCard(baselineAlerts[2]);
    }
    initThreatChart((list || []).slice().reverse());
  });
  renderSubmittedReports();

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/alerts`);
  ws.onmessage = (evt) => {
    const a = JSON.parse(evt.data);
    renderAlert(a);
    updateSocAttackerCard(a);
    pushThreatPoint(a);
    pushNotifPanelItem(a);
    bumpNotifBadge();
    showEmergencyAlert(a);
    showThreatToast(a);
    const securityTab = document.getElementById("tab-security");
    const dot = document.getElementById("alertDot");
    if (dot && securityTab && securityTab.classList.contains("hidden")) {
      dot.classList.add("show");
    }
  };
}
