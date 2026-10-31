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

// ============ SIMULATED ADMIN SMARTPHONE WIDGET ============
let phoneAlertCount = 0;

function updatePhoneClock() {
  const clockEl = document.getElementById("phoneClock");
  if (clockEl) {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}
setInterval(updatePhoneClock, 10000);
updatePhoneClock();

function toggleAdminPhone() {
  const phone = document.getElementById("adminPhoneWidget");
  if (!phone) return;
  phone.classList.toggle("hidden");
  if (!phone.classList.contains("hidden")) {
    const list = document.getElementById("phoneSmsList");
    if (list) list.scrollTop = list.scrollHeight;
  }
}

function pushAdminPhoneAlert(a) {
  phoneAlertCount++;
  const countEl = document.getElementById("phoneAlertCount");
  if (countEl) countEl.textContent = String(phoneAlertCount);

  const pulse = document.getElementById("phoneBadgePulse");
  if (pulse) pulse.classList.add("alerting");

  // Vibrate phone UI
  const phone = document.getElementById("adminPhoneWidget");
  if (phone) {
    phone.classList.add("vibrating");
    setTimeout(() => phone.classList.remove("vibrating"), 1800);
  }

  // Update push notification banner on phone lockscreen
  const banner = document.getElementById("phonePushBanner");
  const pushBody = document.getElementById("pushBodyText");
  const pushTime = document.getElementById("pushTime");
  if (banner && pushBody) {
    banner.style.display = "block";
    pushBody.textContent = a.message;
    if (pushTime) pushTime.textContent = new Date(a.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // Append SMS record to phone messages
  const smsList = document.getElementById("phoneSmsList");
  if (smsList) {
    const bubble = document.createElement("div");
    bubble.className = `sms-bubble alert-${a.level || 'info'}`;
    const t = new Date(a.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const sender = a.level === "critical" ? "🚨 DPDP ALERT" : a.level === "warning" ? "⚠️ AUTH GUARD" : "🛡️ SOC MONITOR";
    bubble.innerHTML = `<div><b>${sender}:</b> ${a.message}</div><div class="sms-time">${t}</div>`;
    smsList.appendChild(bubble);
    smsList.scrollTop = smsList.scrollHeight;
  }
}

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
function initThreatChart(initialAlerts) {
  const canvas = document.getElementById("threatChart");
  if (!canvas || typeof Chart === "undefined") return;

  // initialAlerts is chronological (oldest first); build a running
  // cumulative count of "threat-worthy" (critical or warning) events over time.
  let count = 0;
  const labels = [];
  const points = [];
  initialAlerts.forEach(a => {
    if (a.level === "critical" || a.level === "warning") {
      count += 1;
      labels.push(new Date(a.timestamp * 1000).toLocaleTimeString());
      points.push(count);
    }
  });

  threatChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Threats Detected (cumulative)",
        data: points,
        borderColor: "#DC2626",
        backgroundColor: "rgba(220,38,38,0.08)",
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: "#DC2626",
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { font: { family: "JetBrains Mono", size: 10 } } },
        y: { beginAtZero: true, ticks: { precision: 0 } }
      }
    }
  });
}

function pushThreatPoint(alert) {
  if (!threatChart || (alert.level !== "critical" && alert.level !== "warning")) return;
  const prevCount = threatChart.data.datasets[0].data.slice(-1)[0] || 0;
  threatChart.data.labels.push(new Date(alert.timestamp * 1000).toLocaleTimeString());
  threatChart.data.datasets[0].data.push(prevCount + 1);
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
  if (locEl) locEl.textContent = loc;
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

  if (meta.ack_number) {
    if (dpbStatusEl) dpbStatusEl.textContent = "AUTO-SUBMITTED";
    if (dpbAckEl) dpbAckEl.textContent = `Ack: ${meta.ack_number}`;
  }

  if (meta.screen || meta.platform) {
    if (deviceEl) {
      deviceEl.textContent = `${meta.platform || 'Linux x86_64'} · Screen ${meta.screen || '1920x1080'} · Cores: ${meta.cores || '8'} · ${meta.timezone || 'Asia/Kolkata'}`;
    }
  }

  if (a.message.includes("CANARY") || meta.type === "canary_hit") {
    if (canaryStatusEl) {
      canaryStatusEl.textContent = "TRIGGERED & DE-ANONYMIZED";
      canaryStatusEl.style.color = "#EF4444";
    }
  }
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
      <span class="toast-pill sms">📲 SMS: +91 99016 25399</span>
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
    const div = document.createElement("div");
    div.className = "alert-item alert-" + a.level;
    div.style.cursor = "pointer";
    div.title = "Click to inspect attacker forensics";
    div.onclick = () => openForensicModal(a);
    const t = new Date(a.timestamp * 1000).toLocaleTimeString();
    div.innerHTML = `<span class="alert-ico">${ICONS[a.level] || ICONS.info}</span>
      <span class="alert-body"><span class="alert-time">${t}</span> ${a.message}</span>`;
    alertFeed.prepend(div);
    if (a.message.includes("submitted to the Data Protection Board") || a.message.includes("DPDP BREACH REPORT AUTO-SUBMITTED")) {
      renderSubmittedReports();
    }
  }

  fetch("/api/alerts").then(r => r.json()).then(list => {
    list.forEach(renderAlert);
    if (list.length > 0) {
      updateSocAttackerCard(list[0]);
    }
    // /api/alerts returns newest-first; reverse for chronological chart init
    initThreatChart(list.slice().reverse());
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
    pushAdminPhoneAlert(a);
    const securityTab = document.getElementById("tab-security");
    const dot = document.getElementById("alertDot");
    if (dot && securityTab && securityTab.classList.contains("hidden")) {
      dot.classList.add("show");
    }
  };
}
