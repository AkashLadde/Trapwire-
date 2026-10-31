/**
 * TRAPWIRE — Attacker Workstation Command Interpreter & Simulation Engine
 * Kali Linux / Pentest Console Experience (Purely Simulated & Safe)
 * Targets Defender Server at http://127.0.0.1:8080
 */

(function () {
  "use strict";

  const API_BASE = window.TARGET_API_BASE || "http://127.0.0.1:8080";

  // --- Virtual Filesystem Model ---
  const VIRTUAL_FS = {
    "shadow_vault": {
      "leak_database.enc": {
        size: "12.4 MB",
        type: "encrypted",
        content: `╔══════════════════════════════════════════════════════════════════════╗
║                    SIMULATED ENCRYPTED DATABASE                      ║
╠══════════════════════════════════════════════════════════════════════╣
║ FILE: leak_database.enc                                              ║
║ SIZE: 12.4 MB                                                        ║
║ ENCRYPTION: AES-256 [SIMULATED]                                      ║
║ RECORDS: 14                                                          ║
║ CLASSIFICATION: HONEYPOT DECOY DATA                                  ║
║ STATUS: READY FOR EXPORT                                             ║
╚══════════════════════════════════════════════════════════════════════╝

Sample Record Preview (Decoy Synthetic Data):
+---------------+---------------------+-----------------------------+-------------------+
| Order ID      | Customer Name       | Email                       | Phone             |
+---------------+---------------------+-----------------------------+-------------------+
| ORD-749201    | Aarav Sharma        | aarav.s82@example.test      | +91-90000-00001   |
| ORD-839104    | Ananya Reddy        | ananya.r14@example.test     | +91-90000-00002   |
| ORD-194820    | Kabir Verma         | kabir.v55@example.test      | +91-90000-00003   |
| ORD-402918    | Meera Iyer          | meera.i99@example.test      | +91-90000-00004   |
+---------------+---------------------+-----------------------------+-------------------+
[!] Sensitive fields (Aadhaar/PAN/Card) are isolated in honeypot vault.`
      },
      "client_records.enc": {
        size: "4.8 MB",
        type: "encrypted",
        content: `[ENCRYPTED CLIENT ARCHIVE]
FORMAT: JSON-LINES (GZIP/AES)
DATASET: E-Commerce Customer Profiles
TOTAL OBJECTS: 14 records
INTEGRITY HASH: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
USE 'export data' TO EXTRACT PAYLOAD.`
      },
      "master_keys.bak": {
        size: "1.2 KB",
        type: "key",
        content: `-----BEGIN SIMULATED RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0wJd8tQ4Wb5z9Q5vK9f2z7l0wY3k8J4m7p8q2r6t9u0v1w3x
y5z7a9b1c3d5e7f9g1h3j5k7m9n1p3q5r7s9t1u3v5w7x9y1z3a5b7c9d1e3f5g7
[SIMULATED RSA KEY - EDUCATIONAL CAPSTONE PURPOSES ONLY]
-----END SIMULATED RSA PRIVATE KEY-----`
      }
    },
    "onion_links": {
      "hidden_markets.lst": {
        size: "840 B",
        type: "text",
        content: `[SIMULATED DARKNET REPOSITORIES]
http://trapwire2837492jsdflkjwoeir093284.onion/vault
http://shadowdump893472938472938472938.onion/intel
http://zerodaybroker998237492837492834.onion/exploits
[NOTE: Synthetic fictional URIs for educational UI realism]`
      }
    },
    "malware_kits": {
      "payloads.sh": {
        size: "2.1 KB",
        type: "script",
        content: `#!/bin/bash
# ==========================================================
# TRAPWIRE EDUCATIONAL LAB - BENIGN TEST PAYLOAD
# Safe demonstration wrapper for ethical intrusion testing
# ==========================================================
echo "[+] Initializing simulated breach testing agent..."
echo "[+] Target environment: Localhost Sandbox (127.0.0.1:8080)"
echo "[+] Mode: Intrusion Detection & DPDP Compliance Verification"`
      },
      "ransom_notes.txt": {
        size: "620 B",
        type: "text",
        content: `===============================================================
[SIMULATION NOTICE]
This system is protected by TRAPWIRE Autonomous Threat Deception.
All intrusion attempts are quarantined to decoy honeypot environments.
Canary tracking tokens auto-report breach telemetry to India's DPB.
===============================================================`
      }
    },
    "stolen_creds": {
      "hash_dump.txt": {
        size: "1.8 KB",
        type: "hashes",
        content: `[CAPTURED SHA-256 HASHES (SIMULATED)]
8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92 : 123456
5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8 : password
65e84be33532fb784c48129675f9eff3a682b27168c0ea744b2cf58ee02337c5 : qwerty123
a94a8fe5ccb19ba61c4c0873d391e987982fbbd3fc964b97a2243d578ee192b0 : letmein123
c897bf1277a06f34e6e66cf533b769ea8d407670733d3d622f6d2f36b6d51012 : Admin@2026!`
      }
    },
    "zero_logs": {
      "session_logs.log": {
        size: "5.1 KB",
        type: "log",
        content: `[SESSION LOGS — SIMULATED SECURITY AUDIT]
08:41:02 [AUTH] Authentication module initialized on :8080
08:41:08 [AUTH] Failed login attempt from 127.0.0.1 (user: admin)
08:41:11 [AUTH] Failed login attempt from 127.0.0.1 (user: admin)
08:41:14 [AUTH] Failed login attempt from 127.0.0.1 (user: admin)
08:41:16 [WARN] Anomaly detection threshold exceeded (>3 failed attempts)
08:41:20 [HONEYPOT] Deception engine armed for suspicious source
08:41:22 [CANARY] Canary token generator seeded`
      }
    }
  };

  // State Management
  const state = {
    currentDir: "root",
    history: [],
    historyIndex: -1,
    isAuthenticated: false,
    isSuspicious: false,
    vpnConnected: false,
    vpnNode: "Disconnected",
    apparentIp: "127.0.0.1 (Direct)",
    canaryArmed: true,
    honeypotActive: false,
    incidentId: "NONE",
    targetUser: window.TARGET_USERNAME || "admin",
    wordlist: window.WORDLIST || [
      "123456", "password", "admin123", "admin@123",
      "Welcome@123", "qwerty123", "Admin@2026!", "letmein123"
    ]
  };

  // DOM Elements
  const termOutput = document.getElementById("termOutput");
  const termInput = document.getElementById("termInput");
  const terminalBody = document.getElementById("terminalBody");
  const promptPath = document.getElementById("promptPath");

  // Topbar / Telemetry DOM elements
  const topVpnStatus = document.getElementById("topVpnStatus");
  const topSessionStatus = document.getElementById("topSessionStatus");
  const targetHostEl = document.getElementById("targetHostEl");
  const vpnStatusEl = document.getElementById("vpnStatusEl");
  const sessionStatusEl = document.getElementById("sessionStatusEl");
  const honeypotStatusEl = document.getElementById("honeypotStatusEl");
  const canaryStatusEl = document.getElementById("canaryStatusEl");
  const incidentIdEl = document.getElementById("incidentIdEl");

  // Step elements
  const stepVpn = document.getElementById("stepVpn");
  const stepScan = document.getElementById("stepScan");
  const stepAuth = document.getElementById("stepAuth");
  const stepHoneypot = document.getElementById("stepHoneypot");
  const stepExport = document.getElementById("stepExport");
  const stepCanary = document.getElementById("stepCanary");

  // Helper: Sleep
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // Helper: Scroll terminal to bottom
  function scrollToBottom() {
    if (terminalBody) {
      terminalBody.scrollTop = terminalBody.scrollHeight;
    }
  }

  // Print Line to Terminal
  function printLine(text, styleClass = "info") {
    const line = document.createElement("div");
    line.className = "term-line " + styleClass;
    line.innerHTML = text;
    termOutput.appendChild(line);
    scrollToBottom();
    return line;
  }

  // Print Raw HTML / Box to Terminal
  function printRaw(html) {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    termOutput.appendChild(wrapper);
    scrollToBottom();
  }

  // Initialize Welcome Banner
  function printWelcomeBanner() {
    printLine("┌────────────────────────────────────────────────────────────────────────┐", "cyan");
    printLine("│  OFFENSIVE SECURITY PENTEST WORKSTATION — TRAPWIRE 2026.4 (PORT 9000)  │", "error");
    printLine("│  Autonomous Exploit Lab, Vulnerability Assessment & Deception Research │", "dim");
    printLine("└────────────────────────────────────────────────────────────────────────┘", "cyan");
    printLine("Target Company Host: <b style='color:#00e5ff;'>" + API_BASE + "</b> (Admin Security Center)", "info");
    printLine("Type <b style='color:#ff003b;'>help</b> for offensive commands, or click any file/tool in the sidebar.", "cyan");
    printLine("");
  }

  // Update Status in Right & Top UI
  function updateUIState() {
    if (topVpnStatus) {
      topVpnStatus.textContent = state.vpnConnected ? `VPN: ${state.vpnNode}` : "VPN: OFF";
      topVpnStatus.parentElement.className = state.vpnConnected ? "atk-meta-pill vpn-active" : "atk-meta-pill";
    }
    if (topSessionStatus) {
      topSessionStatus.textContent = state.isAuthenticated
        ? (state.isSuspicious ? "SESSION: SUSPICIOUS [ISOLATED]" : "SESSION: AUTHENTICATED")
        : "SESSION: ANONYMOUS";
      topSessionStatus.parentElement.className = state.isSuspicious ? "atk-meta-pill suspicious-active" : "atk-meta-pill";
    }
    if (vpnStatusEl) {
      vpnStatusEl.textContent = state.vpnConnected ? state.vpnNode : "DISCONNECTED";
      vpnStatusEl.className = state.vpnConnected ? "spec-val-badge badge-success" : "spec-val-badge badge-standby";
    }
    if (sessionStatusEl) {
      sessionStatusEl.textContent = state.isAuthenticated ? (state.isSuspicious ? "SUSPICIOUS" : "NORMAL") : "ANONYMOUS";
      sessionStatusEl.className = state.isSuspicious ? "spec-val-badge badge-active" : (state.isAuthenticated ? "spec-val-badge badge-success" : "spec-val-badge badge-standby");
    }
    if (honeypotStatusEl) {
      honeypotStatusEl.textContent = state.honeypotActive ? "ACTIVE (DECOY)" : "ARMED";
      honeypotStatusEl.className = state.honeypotActive ? "spec-val-badge badge-active" : "spec-val-badge badge-armed";
    }
    if (canaryStatusEl) {
      canaryStatusEl.textContent = state.canaryArmed ? (state.honeypotActive ? "ARMED (BEACON READY)" : "ARMED") : "TRIGGERED";
      canaryStatusEl.className = state.canaryArmed ? "spec-val-badge badge-armed" : "spec-val-badge badge-active";
    }
    if (incidentIdEl) {
      incidentIdEl.textContent = state.incidentId;
      incidentIdEl.style.color = state.incidentId !== "NONE" ? "#ef4444" : "#94a3b8";
    }
    if (promptPath) {
      promptPath.textContent = state.currentDir === "root" ? "~/workspace" : `~/workspace/${state.currentDir}`;
    }
  }

  // --- Commands Implementation ---

  const COMMANDS = {
    help: async () => {
      if (typeof window.playBeepSound === "function") window.playBeepSound();
      printLine("<b style='color:#00e5ff;'>OFFSEC PENTEST COMMAND DIRECTORY — TRAPWIRE</b>", "cyan");
      printLine("─────────────────────────────────────────────────────────────────", "dim");
      
      printLine("<b style='color:#c084fc;'>[RECON & ANONYMITY]</b>", "purple");
      printLine("  <b>scan target</b>             Probe ports & endpoints on " + API_BASE, "info");
      printLine("  <b>vpn connect [node]</b>      Build multi-hop VPN circuit (Amsterdam/Tokyo/Singapore)", "info");
      printLine("  <b>vpn status</b>              Show active VPN node & apparent IP", "info");
      printLine("  <b>vpn disconnect</b>          Reset VPN connection back to local direct", "info");
      printLine("");

      printLine("<b style='color:#ff003b;'>[ATTACK SIMULATIONS]</b>", "error");
      printLine("  <b>auth test</b>               Probe target /api/login endpoint headers", "info");
      printLine("  <b>hydra -l test -P passwords.txt ssh://192.168.1.10</b>  Run THC-Hydra credential attack", "info");
      printLine("  <b>bruteforce --user admin</b>  Execute password dictionary attack against target", "info");
      printLine("  <b>sqli [payload]</b>            REAL SQL injection against the decoy lab DB (UNION extraction)", "info");
      printLine("  <b>xss [payload]</b>             REAL stored-XSS plant in the decoy shop reviews", "info");
      printLine("  <b>idor</b>                      REAL IDOR enumeration of decoy customer records", "info");
      printLine("  <b>ssrf [url]</b>                 REAL SSRF via the lab fetch endpoint (allow-listed decoy only)", "info");
      printLine("  <b>traversal [path]</b>          REAL path traversal into the decoy lab sandbox", "info");
      printLine("  <b>dictionary</b>              Walk rockyou wordlist preview", "info");
      printLine("  <b>hashlookup</b> / <b>rainbow</b>     Execute precomputed SHA-256 rainbow table matching", "info");
      printLine("");

      printLine("<b style='color:#10b981;'>[FILESYSTEM & EXFILTRATION]</b>", "success");
      printLine("  <b>ls</b> / <b>show files</b>          List files in current virtual filesystem", "info");
      printLine("  <b>cd &lt;dir&gt;</b>                 Change simulated directory (e.g. cd shadow_vault)", "info");
      printLine("  <b>cat &lt;file&gt;</b>               Inspect synthetic file / encrypted database payload", "info");
      printLine("  <b>show records</b>             Display preview of customer order records", "info");
      printLine("  <b>export data</b> / <b>fetch</b>      Exfiltrate database package (triggers honeypot & canary)", "info");
      printLine("");

      printLine("<b style='color:#f59e0b;'>[SYSTEM & AUDIT]</b>", "warning");
      printLine("  <b>status</b>                  Display full diagnostic state, incident ID & telemetry", "info");
      printLine("  <b>whoami</b>                  Display active Kali terminal identity & permissions", "info");
      printLine("  <b>clear</b> / <b>cls</b>             Clear terminal output console", "info");
      printLine("  <b>reset</b>                   Reset all backend alerts, incidents & honeypot state", "info");
      printLine("─────────────────────────────────────────────────────────────────", "dim");
    },

    clear: async () => {
      termOutput.innerHTML = "";
    },

    cls: async () => {
      termOutput.innerHTML = "";
    },

    status: async () => {
      printLine("<b style='color:#00e5ff;'>TRAPWIRE PENTEST CONSOLE STATUS & TELEMETRY</b>", "cyan");
      printLine("┌─────────────────────────────────────────────────────────────┐", "dim");
      printLine(`│ Target Host:        ${(API_BASE + " (TrapWire Admin)").padEnd(40)}│`, "info");
      printLine(`│ VPN Circuit:        ${(state.vpnConnected ? state.vpnNode + " [SPOOFED]" : "DISCONNECTED (Direct)").padEnd(40)}│`, state.vpnConnected ? "cyan" : "dim");
      printLine(`│ Apparent Source IP: ${state.apparentIp.padEnd(40)}│`, "info");
      printLine(`│ Authenticated:      ${(state.isAuthenticated ? "YES (admin)" : "NO (Anonymous)").padEnd(40)}│`, state.isAuthenticated ? "success" : "dim");
      printLine(`│ Session Security:   ${(state.isSuspicious ? "SUSPICIOUS [FLAGGED & ISOLATED]" : "STANDARD").padEnd(40)}│`, state.isSuspicious ? "error" : "info");
      printLine(`│ Honeypot Defense:   ${(state.honeypotActive ? "ACTIVE — DECOY DATASET SERVED" : "ARMED").padEnd(40)}│`, state.honeypotActive ? "error" : "warning");
      printLine(`│ Canary Tracking:    ${(state.canaryArmed ? "ARMED — BEACON READY" : "TRIGGERED / ATTRIBUTED").padEnd(40)}│`, state.canaryArmed ? "warning" : "error");
      printLine(`│ Active Incident ID: ${state.incidentId.padEnd(40)}│`, state.incidentId !== "NONE" ? "error" : "dim");
      printLine("└─────────────────────────────────────────────────────────────┘", "dim");
    },

    whoami: async () => {
      const user = sessionStorage.getItem("kali_user") || "root";
      printLine(`${user}@kali (uid=1000 gid=1000 groups=1000(kali),27(sudo))`, "info");
      printLine("Workstation: KALI-OFFSEC-WORKSTATION-01 [Simulation Sandbox]", "dim");
    },

    pwd: async () => {
      printLine(state.currentDir === "root" ? "/home/kali/workspace" : `/home/kali/workspace/${state.currentDir}`, "info");
    },

    ls: async () => {
      printLine("<b style='color:#00e5ff;'>total 48K</b>", "dim");
      if (state.currentDir === "root") {
        printLine("drwx------ 4 kali kali 4.0K Oct 02 21:00 <b style='color:#38bdf8;'>shadow_vault/</b>", "blue");
        printLine("drwx------ 2 kali kali 4.0K Oct 02 21:00 <b style='color:#38bdf8;'>onion_links/</b>", "blue");
        printLine("drwx------ 3 kali kali 4.0K Oct 02 21:00 <b style='color:#38bdf8;'>malware_kits/</b>", "blue");
        printLine("drwx------ 2 kali kali 4.0K Oct 02 21:00 <b style='color:#38bdf8;'>stolen_creds/</b>", "blue");
        printLine("drwx------ 2 kali kali 4.0K Oct 02 21:00 <b style='color:#38bdf8;'>zero_logs/</b>", "blue");
        printLine("-rw-r--r-- 1 kali kali 12.4M Oct 02 21:10 <b style='color:#ef4444;'>leak_database.enc</b>", "error");
        printLine("-rw-r--r-- 1 kali kali 5.1K  Oct 02 21:12 <b style='color:#e2e8f0;'>session_logs.log</b>", "info");
        printLine("-rw-r--r-- 1 kali kali 2.4K  Oct 02 21:05 <b style='color:#f59e0b;'>vpn_configs.zip</b>", "warning");
      } else {
        const files = VIRTUAL_FS[state.currentDir];
        if (files) {
          printLine("drwx------ 2 kali kali 4.0K Oct 02 21:00 <b style='color:#38bdf8;'>.</b>", "blue");
          printLine("drwx------ 4 kali kali 4.0K Oct 02 21:00 <b style='color:#38bdf8;'>..</b>", "blue");
          for (const [fname, meta] of Object.entries(files)) {
            const color = fname.endsWith(".enc") ? "#ef4444" : (fname.endsWith(".sh") ? "#10b981" : "#e2e8f0");
            printLine(`-rw-r--r-- 1 kali kali ${meta.size.padEnd(6)} Oct 02 21:00 <b style='color:${color};'>${fname}</b>`);
          }
        }
      }
    },

    "show files": async () => {
      await COMMANDS.ls();
    },

    cd: async (args) => {
      const target = args[0] ? args[0].trim().replace(/\/$/, "") : "";
      if (!target || target === "~" || target === "/") {
        state.currentDir = "root";
      } else if (target === "..") {
        state.currentDir = "root";
      } else if (VIRTUAL_FS[target]) {
        state.currentDir = target;
      } else {
        printLine(`bash: cd: ${target}: No such file or directory`, "error");
        return;
      }
      updateUIState();
    },

    cat: async (args) => {
      if (!args[0]) {
        printLine("usage: cat <filename>", "warning");
        return;
      }
      const filename = args[0].trim().replace(/^.*\//, "");
      
      let fileObj = null;
      if (state.currentDir !== "root" && VIRTUAL_FS[state.currentDir] && VIRTUAL_FS[state.currentDir][filename]) {
        fileObj = VIRTUAL_FS[state.currentDir][filename];
      } else {
        for (const dir in VIRTUAL_FS) {
          if (VIRTUAL_FS[dir][filename]) {
            fileObj = VIRTUAL_FS[dir][filename];
            break;
          }
        }
      }

      if (fileObj) {
        printLine(fileObj.content, fileObj.type === "encrypted" ? "error" : "info");
      } else {
        printLine(`cat: ${filename}: No such file or directory`, "error");
      }
    },

    scan: async () => {
      if (typeof window.playBeepSound === "function") window.playBeepSound();
      printLine("<span class='term-tag tag-scan'>[SCAN]</span> Initializing target reconnaissance on " + API_BASE + "...", "purple");
      
      // Send telemetry to company server
      if (typeof window.notifyCompanyServer === "function") {
        window.notifyCompanyServer("port_scan");
      }

      await sleep(300);
      printLine("<span class='term-tag tag-scan'>[SCAN]</span> Sending SYN probes to top service ports...", "dim");
      await sleep(350);

      printLine("PORT     STATE SERVICE      REASON", "cyan");
      printLine("80/tcp   open  http         uvicorn / FastAPI (Company Server)", "success");
      printLine("8080/tcp open  http-alt     TRAPWIRE Application Server", "success");
      printLine("9000/tcp open  http-alt     Kali Linux Pentest Console", "error");
      printLine("443/tcp  filt  https        simulated-waf", "dim");
      printLine("");

      printLine("<span class='term-tag tag-scan'>[SCAN]</span> Target surface discovery:", "info");
      printLine("  ├── <b>POST /api/login</b>       - Authentication Gateway (Form-based)", "cyan");
      printLine("  ├── <b>GET  /company/dashboard</b> - Secured Administration Console", "cyan");
      printLine("  ├── <b>GET  /api/export</b>        - Customer Order Data Exfiltration Endpoint", "cyan");
      printLine("  └── <b>GET  /canary/{token}</b>   - Dynamic Tracking Beacon Endpoint", "warning");
      printLine("<span class='term-tag tag-success'>[+]</span> Reconnaissance complete. Target is reachable and online.", "success");

      if (stepScan) {
        stepScan.className = "step-item completed";
        stepScan.querySelector(".step-circle").textContent = "✓";
      }
    },

    "scan target": async () => {
      await COMMANDS.scan();
    },

    vpn: async (args) => {
      const sub = args[0] ? args[0].toLowerCase() : "status";
      if (sub === "connect") {
        const node = args[1] || "Amsterdam";
        printLine("<span class='term-tag tag-vpn'>[VPN]</span> Initializing encrypted multi-hop tunnel...", "cyan");
        await sleep(200);

        const hops = [
          { name: "Frankfurt (Relay 1)", ip: "45.155.204.12" },
          { name: "Tokyo (Relay 2)", ip: "103.4.17.88" },
          { name: "Toronto (Relay 3)", ip: "162.219.176.5" },
          { name: `${node} (Exit Node)`, ip: "185.220.101.45" }
        ];

        for (let i = 0; i < hops.length; i++) {
          printLine(`  [${i + 1}/4] Relaying circuit via <b>${hops[i].name}</b> [${hops[i].ip}]...`, "dim");
          await sleep(200);
        }

        state.vpnConnected = true;
        state.vpnNode = node.toUpperCase();
        state.apparentIp = `185.220.101.45 (${node})`;

        printLine(`<span class='term-tag tag-success'>[+]</span> VPN Circuit established! Apparent IP: <b>${state.apparentIp}</b>`, "success");
        printLine("<span class='term-tag tag-warn'>[!]</span> NOTE: VPN spoofing is cosmetic only. Real connecting IP remains visible to server.", "warning");

        if (stepVpn) {
          stepVpn.className = "step-item completed";
          stepVpn.querySelector(".step-circle").textContent = "✓";
        }
        updateUIState();
      } else if (sub === "disconnect") {
        state.vpnConnected = false;
        state.vpnNode = "Disconnected";
        state.apparentIp = "127.0.0.1 (Direct)";
        printLine("<span class='term-tag tag-vpn'>[VPN]</span> Circuit dismantled. Connection reverted to direct local link.", "info");
        updateUIState();
      } else {
        printLine(`<span class='term-tag tag-vpn'>[VPN]</span> Status: ${state.vpnConnected ? "CONNECTED" : "DISCONNECTED"}`, "info");
        printLine(`  Relay: ${state.vpnNode}`, "dim");
        printLine(`  Apparent IP: ${state.apparentIp}`, "dim");
      }
    },

    "vpn connect": async (args) => {
      await COMMANDS.vpn(["connect", args[0] || "Amsterdam"]);
    },

    "vpn status": async () => {
      await COMMANDS.vpn(["status"]);
    },

    "vpn disconnect": async () => {
      await COMMANDS.vpn(["disconnect"]);
    },

    auth: async () => {
      printLine("<span class='term-tag tag-info'>[AUTH]</span> Testing endpoint reachability: <code>POST " + API_BASE + "/api/login</code>", "info");
      await sleep(200);
      try {
        const res = await fetch(`${API_BASE}/api/login`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ username: "probe", password: "invalid_probe" }),
          credentials: "include"
        });
        printLine(`[AUTH] Gateway response: HTTP ${res.status} Unauthorized`, "warning");
        printLine("[AUTH] Form parameters confirmed: 'username', 'password'", "success");
        printLine("[AUTH] Target authentication portal is ACTIVE and ready for brute-force attack.", "cyan");
      } catch (err) {
        printLine(`[AUTH] Error reaching gateway: ${err.message}`, "error");
      }
    },

    "auth test": async () => {
      await COMMANDS.auth();
    },

    bruteforce: async () => {
      const username = state.targetUser;
      if (typeof window.playAlarmSound === "function") window.playAlarmSound();

      printLine("<span class='term-tag tag-error'>[BRUTEFORCE]</span> Initializing automated credential attack module...", "error");
      printLine(`[+] Target: TRAPWIRE Admin Portal (${API_BASE})`, "cyan");
      printLine(`[+] Target Username: <b>${username}</b>`, "cyan");
      printLine(`[*] Loading attack candidate wordlist (${state.wordlist.length} entries)...`, "info");
      printLine("");

      // Notify company server of bruteforce event
      if (typeof window.notifyCompanyServer === "function") {
        window.notifyCompanyServer("bruteforce_start");
      }

      const decoyPool = ["dragon123", "shadow2024", "monkey99", "qwerty88", "football7", "batman123"];
      const decoys = decoyPool.slice(0, 3 + Math.floor(Math.random() * 2));

      // 1. Rapid decoy attempts
      for (let i = 0; i < decoys.length; i++) {
        const pw = decoys[i];
        printLine(`  [${String(i + 1).padStart(2, '0')}] Trying: "${pw}" .................... <span style="color:#ef4444;">FAILED</span>`, "dim");
        if (typeof window.playKeyClickSound === "function") window.playKeyClickSound();
        await sleep(90);
      }

      // 2. Real attempts against /api/login on Company Server
      let cracked = false;
      let attemptNum = decoys.length;

      for (const pw of state.wordlist) {
        attemptNum++;
        printLine(`  [${String(attemptNum).padStart(2, '0')}] Testing candidate: "${pw}" ...`, "info");
        if (typeof window.playKeyClickSound === "function") window.playKeyClickSound();
        await sleep(220);

        try {
          const body = new URLSearchParams({ username: username, password: pw });
          const res = await fetch(`${API_BASE}/api/login`, {
            method: "POST",
            body: body,
            credentials: "include"
          });
          const data = await res.json().catch(() => ({}));

          if (res.ok && data.ok) {
            cracked = true;
            state.isAuthenticated = true;
            state.isSuspicious = !!data.suspicious;
            state.honeypotActive = state.isSuspicious;
            state.canaryArmed = true;
            state.incidentId = data.incident_id || ("INC-" + Math.random().toString(16).substring(2, 10).toUpperCase());

            if (typeof window.playSuccessSound === "function") window.playSuccessSound();

            printLine("");
            printLine("╔═══════════════════════════════════════════════════════════════╗", "success");
            printLine("║                CRITICAL CREDENTIAL MATCH FOUND                ║", "success");
            printLine("╠═══════════════════════════════════════════════════════════════╣", "success");
            printLine(`║  USERNAME: ${username.padEnd(49)}║`, "success");
            printLine(`║  PASSWORD: ${pw.padEnd(49)}║`, "success");
            printLine(`║  STATUS:   AUTHENTICATION GRANTED                            ║`, "success");
            printLine("╚═══════════════════════════════════════════════════════════════╝", "success");
            printLine("");

            if (state.isSuspicious) {
              printLine("<span class='term-tag tag-warn'>[!]</span> <b>INTRUSION DETECTION ALERT TRIGGERED:</b>", "warning");
              printLine("  [!] Failed login threshold exceeded (>3 failed attempts).", "warning");
              printLine("  [!] Session classified as: <b style='color:#ef4444;'>SUSPICIOUS (ISOLATED)</b>", "error");
              printLine("  [+] Honeypot Deception Engine activated: Decoy customer dataset deployed.", "cyan");
              printLine("  [+] Embedded Canary Tracking Tokens ARMED.", "cyan");
              printLine(`  [!] Incident recorded on company defender console: <b>${state.incidentId}</b>`, "error");
            }

            if (stepAuth) {
              stepAuth.className = "step-item completed";
              stepAuth.querySelector(".step-circle").textContent = "✓";
            }
            if (stepHoneypot) {
              stepHoneypot.className = "step-item completed";
              stepHoneypot.querySelector(".step-circle").textContent = "✓";
            }
            updateUIState();
            break;
          } else {
            printLine(`  └─> Result: <span style="color:#ef4444;">AUTHENTICATION FAILED</span> (HTTP 401)`, "error");
          }
        } catch (err) {
          printLine(`  └─> Network Error: ${err.message}`, "error");
        }
      }

      if (!cracked) {
        printLine("[!] Wordlist exhausted without matching credentials.", "warning");
      }
    },

    // THC-Hydra themed wrapper. Cosmetic only: it parses the typed hydra
    // command line purely for realistic display, then delegates to the exact
    // same self-contained bruteforce routine above, which only ever hits this
    // app's own /api/login endpoint. No real hydra binary runs and no real
    // host (e.g. ssh://192.168.1.10) is ever contacted.
    hydra: async (args) => {
      // Parse hydra-style flags for display realism.
      let login = "admin";
      let passSource = "passwords.txt";
      let target = "ssh://192.168.1.10";
      for (let i = 0; i < args.length; i++) {
        const a = args[i];
        if (a === "-l" || a === "-L") { login = args[i + 1] || login; i++; }
        else if (a === "-p" || a === "-P") { passSource = args[i + 1] || passSource; i++; }
        else if (a.includes("://") || /^\d{1,3}(\.\d{1,3}){3}$/.test(a)) { target = a; }
      }
      const service = target.includes("://") ? target.split("://")[0] : "ssh";
      const host = target.replace(/^[a-z]+:\/\//i, "");

      if (typeof window.playAlarmSound === "function") window.playAlarmSound();

      printLine("<span class='term-tag tag-error'>[HYDRA]</span> Hydra v9.5 (c) 2026 by van Hauser/THC &amp; David Maciejak - Pentest Lab", "error");
      printLine(`[DATA] attacking <b>${service}://${host}</b> - login "<b>${login}</b>" - pass source "<b>${passSource}</b>"`, "cyan");
      printLine("<span class='term-tag tag-warn'>[*]</span> Lab routing note: engagement scoped to TRAPWIRE demo portal (" + API_BASE + "). No external host contacted.", "warning");
      await sleep(250);
      printLine("[DATA] max 8 tasks per 1 server, overall 8 tasks, 8 login tries, ~1 try per task", "dim");
      await sleep(200);

      // Delegate to the real (local, self-contained) brute-force engine.
      await COMMANDS.bruteforce();
    },

    sqli: async (args) => {
      // PHASE 2 (REAL): payload is really sent to the defender lab endpoint,
      // which concatenates it into an actual SQL query on the decoy DB.
      // Whatever prints below is the server's REAL response.
      const payload = args.length ? args.join(" ") : "-1 UNION SELECT id, username, password, role FROM lab_users-- ";
      if (typeof window.playAlarmSound === "function") window.playAlarmSound();
      printLine("<span class='term-tag tag-error'>[SQLi]</span> Launching REAL SQL Injection against the decoy lab DB...", "error");
      printLine(`[+] Target Endpoint: <code>GET ${API_BASE}/lab/shop/product?id=...</code>`, "cyan");
      printLine(`[+] Injection Payload: <b style="color:#f87171;">${payload}</b>`, "error");
      try {
        const res = await fetch(`${API_BASE}/lab/shop/product?id=${encodeURIComponent(payload)}`);
        const data = await res.json();
        printLine(`[*] Query the server really executed: <code>${data.executed_query}</code>`, "dim");
        if (data.error) printLine(`[!] Database error returned by the server: ${data.error}`, "warning");
        const rows = data.results || [];
        if (rows.length) {
          printLine(`<span class='term-tag tag-success'>[+]</span> <b>REAL EXTRACTION - ${rows.length} row(s) returned by the server:</b>`, "success");
          rows.forEach((r) => printLine(`    ${JSON.stringify(r)}`, "success"));
          printLine("<span class='term-tag tag-warn'>[!]</span> These are DECOY lab_users rows. The defender detected this extraction SERVER-SIDE - check the SOC dashboard (this console sent no announcement).", "warning");
        } else {
          printLine("[*] No rows returned. Tip: try <b>sqli 1 OR 1=1</b> or run plain <b>sqli</b> for the UNION extraction.", "info");
        }
      } catch (err) {
        printLine(`[!] Request failed: ${err}`, "error");
      }
    },

    "sql injection": async (args) => {
      await COMMANDS.sqli(args);
    },

    exploit: async (args) => {
      await COMMANDS.sqli(args);
    },

    xss: async (args) => {
      // PHASE 2 (REAL): plants a stored-XSS payload in the decoy shop via a
      // real POST. It executes in the browser of whoever opens the product
      // page - open the printed link to prove execution.
      const payload = args.length ? args.join(" ") : "<script>alert('TRAPWIRE-STORED-XSS')</script>";
      if (typeof window.playBeepSound === "function") window.playBeepSound();
      printLine("<span class='term-tag tag-warn'>[XSS]</span> Planting REAL Stored-XSS payload in the decoy shop reviews...", "warning");
      printLine(`[+] Payload: <b style="color:#f59e0b;">${payload}</b>`, "warning");
      try {
        const res = await fetch(`${API_BASE}/lab/shop/review`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_id: 1, author: "attacker", comment: payload })
        });
        const data = await res.json();
        if (data.ok) {
          printLine("<span class='term-tag tag-success'>[+]</span> Payload STORED on the server (decoy review DB).", "success");
          printLine(`[*] Now open this page - the payload executes there for real: <b>${API_BASE}${data.view_at}</b>`, "cyan");
          printLine(`[*] Reflected variant: <b>${API_BASE}/lab/shop/search-page?q=${encodeURIComponent(payload)}</b>`, "cyan");
          printLine("<span class='term-tag tag-warn'>[!]</span> The defender flagged the planting SERVER-SIDE - check the SOC dashboard.", "warning");
        } else {
          printLine(`[!] Server response: ${JSON.stringify(data)}`, "error");
        }
      } catch (err) {
        printLine(`[!] Request failed: ${err}`, "error");
      }
    },

    traversal: async (args) => {
      // PHASE 2 (REAL): really requests the file from the lab download
      // endpoint using path traversal and prints the server's real reply.
      // Traversal is clamped inside the decoy lab sandbox.
      const targetPath = args[0] || "../secrets/.env";
      const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (typeof window.playBeepSound === "function") window.playBeepSound();
      printLine("<span class='term-tag tag-warn'>[PATH-TRAVERSAL]</span> Sending REAL traversal request to the decoy lab...", "warning");
      printLine(`[+] Target: <code>GET ${API_BASE}/lab/files/download?name=${targetPath}</code>`, "cyan");
      try {
        const res = await fetch(`${API_BASE}/lab/files/download?name=${encodeURIComponent(targetPath)}`);
        const text = await res.text();
        printLine(`[*] Server responded HTTP ${res.status}:`, "info");
        printLine(`<pre>${esc(text.slice(0, 900))}</pre>`, res.ok ? "success" : "error");
        if (res.ok && targetPath.includes("secrets")) {
          printLine("<span class='term-tag tag-warn'>[!]</span> Decoy secret file served - it contains only planted honeytokens. Defender flagged this SERVER-SIDE.", "warning");
        }
      } catch (err) {
        printLine(`[!] Request failed: ${err}`, "error");
      }
    },

    idor: async () => {
      // PHASE 2 (REAL): reads other customers' decoy records by changing
      // the id - the lab API performs no authorisation check at all.
      if (typeof window.playBeepSound === "function") window.playBeepSound();
      printLine("<span class='term-tag tag-warn'>[IDOR]</span> Enumerating decoy customer records with NO authorisation...", "warning");
      for (let i = 1; i <= 3; i++) {
        try {
          const res = await fetch(`${API_BASE}/lab/api/customers/${i}`);
          const data = await res.json();
          printLine(`  [${i}] HTTP ${res.status} -> ${JSON.stringify(data)}`, "success");
        } catch (err) {
          printLine(`  [${i}] request failed: ${err}`, "error");
        }
        await sleep(150);
      }
      printLine("<span class='term-tag tag-warn'>[!]</span> 3+ ids from one source = the defender raises a CONFIRMED IDOR alert - check the SOC dashboard.", "warning");
    },

    ssrf: async (args) => {
      // PHASE 2 (REAL): asks the lab server to fetch a URL server-side.
      // Only the internal decoy metadata endpoint is allow-listed; real
      // cloud metadata addresses are blocked and logged.
      const target = args[0] || `${API_BASE}/lab/internal/metadata`;
      const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (typeof window.playBeepSound === "function") window.playBeepSound();
      printLine("<span class='term-tag tag-warn'>[SSRF]</span> Asking the server to fetch a URL on our behalf...", "warning");
      printLine(`[+] URL: <code>${target}</code>`, "cyan");
      try {
        const res = await fetch(`${API_BASE}/lab/fetch?url=${encodeURIComponent(target)}`);
        const text = await res.text();
        printLine(`[*] Server responded HTTP ${res.status}:`, "info");
        printLine(`<pre>${esc(text.slice(0, 900))}</pre>`, res.ok ? "success" : "error");
      } catch (err) {
        printLine(`[!] Request failed: ${err}`, "error");
      }
    },

    nmap: async () => {
      await COMMANDS.scan();
    },

    dictionary: async () => {
      printLine("<span class='term-tag tag-purple'>[DICTIONARY]</span> Launching dictionary attack simulation...", "purple");
      printLine("[*] Source: rockyou-sample.txt (Top Common Passwords)", "dim");
      await sleep(200);

      const dictWords = ["letmein", "welcome1", "qwertyuiop", "admin2023", "password1", "changeme", "guest123", "root1234"];
      for (let i = 0; i < dictWords.length; i++) {
        printLine(`  [${i + 1}/${dictWords.length}] Dictionary word "${dictWords[i]}" ... <span style="color:#ef4444;">failed (no match)</span>`, "dim");
        await sleep(120);
      }
      printLine("[*] Dictionary space scanned. Real-world systems enforce rate-limiting against dictionary attacks.", "warning");
    },

    hashlookup: async () => {
      printLine("<span class='term-tag tag-warn'>[RAINBOW]</span> Initializing precomputed SHA-256 rainbow table matching...", "warning");
      await sleep(200);

      const hashes = [
        { plain: "123456", hash: "8d969eef6ecad3c29a3a..." },
        { plain: "password", hash: "5e884898da28047151d0..." },
        { plain: "qwerty123", hash: "65e84be33532fb784c48..." },
        { plain: "letmein123", hash: "a94a8fe5ccb19ba61c4c..." },
        { plain: "Admin@2026!", hash: "c897bf1277a06f34e6e6..." }
      ];

      for (const h of hashes) {
        printLine(`  [LOOKUP] ${h.hash}  ==>  <span style="color:#10b981;font-weight:700;">MATCH: "${h.plain}"</span>`, "success");
        await sleep(150);
      }
      printLine("<span class='term-tag tag-success'>[+]</span> Rainbow table reverse resolution complete.", "success");
    },

    rainbow: async () => {
      await COMMANDS.hashlookup();
    },

    "show records": async () => {
      printLine("<b style='color:#00e5ff;'>CURRENTLY AVAILABLE CUSTOMER RECORDS (HONEYPOT VAULT)</b>", "cyan");
      printLine("─────────────────────────────────────────────────────────────────────────────", "dim");
      printLine("Order ID    Customer Name       City        Status       Phone", "cyan");
      printLine("─────────────────────────────────────────────────────────────────────────────", "dim");
      printLine("ORD-749201  Aarav Sharma        Bengaluru   Delivered    +91 90000-00001", "info");
      printLine("ORD-839104  Ananya Reddy        Mumbai      Shipped      +91 90000-00002", "info");
      printLine("ORD-194820  Kabir Verma         Delhi       Processing   +91 90000-00003", "info");
      printLine("ORD-402918  Meera Iyer          Hyderabad   Delivered    +91 90000-00004", "info");
      printLine("ORD-592817  Vivaan Nair         Pune        Delivered    +91 90000-00005", "info");
      printLine("─────────────────────────────────────────────────────────────────────────────", "dim");
      printLine("Use <b>export data</b> to dump full cryptographic export package.", "warning");
    },

    records: async () => {
      await COMMANDS["show records"]();
    },

    export: async () => {
      if (!state.isAuthenticated) {
        printLine("<span class='term-tag tag-error'>[ERROR]</span> Authentication required.", "error");
        printLine("[!] You must authenticate before attempting data export.", "warning");
        printLine("[*] Tip: Run <b>bruteforce --user admin</b> first to crack target credentials.", "cyan");
        return;
      }

      printLine("<span class='term-tag tag-info'>[+]</span> Preparing data export from " + API_BASE + "...", "cyan");
      await sleep(250);
      printLine("<span class='term-tag tag-info'>[+]</span> Enumerating records...", "cyan");
      await sleep(250);
      printLine("<span class='term-tag tag-info'>[+]</span> Encrypting transfer channel...", "cyan");
      await sleep(350);

      // Progressive progress bar animation
      const progressSteps = [
        "▌▌▌▌................",
        "▌▌▌▌▌▌▌▌............",
        "▌▌▌▌▌▌▌▌▌▌▌▌........",
        "▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌....",
        "▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌"
      ];

      const progBox = document.createElement("div");
      progBox.className = "term-progress-box";
      progBox.innerHTML = `<div class="term-progress-bar">${progressSteps[0]}</div><div class="term-progress-status">→ EXFILTRATING DATA (0%)</div>`;
      termOutput.appendChild(progBox);
      scrollToBottom();

      for (let i = 0; i < progressSteps.length; i++) {
        await sleep(250);
        const pct = ((i + 1) / progressSteps.length * 100).toFixed(0);
        progBox.innerHTML = `<div class="term-progress-bar">${progressSteps[i]}</div><div class="term-progress-status">→ EXFILTRATING DATA (${pct}%)</div>`;
        scrollToBottom();
      }

      await sleep(300);
      printLine("<span class='term-tag tag-success'>[+]</span> Records discovered: 14", "success");
      await sleep(200);
      printLine("<span class='term-tag tag-success'>[+]</span> Export package generated: <code>customer_export.json</code>", "success");
      await sleep(200);

      // Fetch actual backend export
      let payload = null;
      try {
        const res = await fetch(`${API_BASE}/api/export`, { credentials: "include" });
        payload = await res.json();

        // Download JSON file locally
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "customer_export.json";
        a.click();
      } catch (err) {
        console.error("Export fetch error:", err);
      }

      // ASCII SUCCESS BANNER
      const asciiBanner = `
<div class="term-success-banner">
<pre>
███████╗██╗   ██╗ ██████╗ ██████╗███████╗███████╗███████╗
██╔════╝██║   ██║██╔════╝██╔════╝██╔════╝██╔════╝██╔════╝
███████╗██║   ██║██║     ██║     █████╗  █████╗  ███████╗
╚════██║██║   ██║██║     ██║     ██╔══╝  ██╔══╝  ╚════██║
███████║╚██████╔╝╚██████╗╚██████╗███████╗███████╗███████║
╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝╚══════╝╚══════╝╚══════╝

                DATA EXPORT SUCCESSFUL
</pre>
</div>`;
      printRaw(asciiBanner);

      printLine("<span class='term-tag tag-success'>[+]</span> <b>SIMULATED DATA ACQUIRED</b>", "success");
      printLine("<span class='term-tag tag-info'>[+]</span> RECORDS: 14", "info");
      printLine("<span class='term-tag tag-honey'>[+]</span> <b>HONEYPOT TRIGGER: ACTIVE</b> (All personal data SHA-256 hashed & synthetic)", "error");
      printLine(`<span class='term-tag tag-warn'>[+]</span> INCIDENT ID: <b>${state.incidentId}</b>`, "warning");
      printLine("<span class='term-tag tag-error'>[!]</span> <b>DEFENDER ALERT: GENERATED</b> (Logged to Company Security Center & DPB Registry)", "error");
      printLine("");

      if (stepExport) {
        stepExport.className = "step-item completed";
        stepExport.querySelector(".step-circle").textContent = "✓";
      }

      // Trigger Canary Token phone-home beacon
      if (payload && Array.isArray(payload) && payload[0] && payload[0]._tracking_invoice_url) {
        const trackingUrl = payload[0]._tracking_invoice_url;
        printLine("<span class='term-tag tag-warn'>[*]</span> Opening simulated invoice preview...", "dim");
        
        setTimeout(() => {
          const iframe = document.createElement("iframe");
          iframe.style.display = "none";
          iframe.src = trackingUrl;
          document.body.appendChild(iframe);
          
          state.canaryArmed = false;
          if (stepCanary) {
            stepCanary.className = "step-item completed";
            stepCanary.querySelector(".step-circle").textContent = "✓";
          }
          updateUIState();
          printLine("<span class='term-tag tag-error'>[CANARY BEACON]</span> <b>Canary tracking token triggered!</b>", "error");
          printLine("  [!] Attacker de-anonymized via honeypot invoice tracking link.", "warning");
          printLine("  [!] Device fingerprint captured -> Submitted to simulated Data Protection Board.", "info");
        }, 1000);
      }
    },

    "export data": async () => {
      await COMMANDS.export();
    },

    "fetch records": async () => {
      await COMMANDS.export();
    },

    exfiltrate: async () => {
      await COMMANDS.export();
    }
  };

  // --- Input Command Handling ---

  async function handleCommand(cmdRaw) {
    const cmd = cmdRaw.trim();
    if (!cmd) return;

    // Echo input prompt
    const promptUser = sessionStorage.getItem("kali_user") || "root";
    const promptPathStr = state.currentDir === "root" ? "~/workspace" : `~/workspace/${state.currentDir}`;
    printLine(`<span style="color:#10b981;">${promptUser}</span><span style="color:#94a3b8;">@</span><span style="color:#ef4444;">kali</span>:<span style="color:#818cf8;">${promptPathStr}</span><span style="color:#ff003b;">#</span> ${cmd}`);

    // Add to history
    state.history.push(cmd);
    state.historyIndex = state.history.length;

    const parts = cmd.split(/\s+/);
    const primary = parts[0].toLowerCase();
    const args = parts.slice(1);

    // Multi-word matches
    const twoWord = (parts[0] + " " + (parts[1] || "")).toLowerCase();

    if (COMMANDS[cmd.toLowerCase()]) {
      await COMMANDS[cmd.toLowerCase()](args);
    } else if (COMMANDS[twoWord]) {
      await COMMANDS[twoWord](parts.slice(2));
    } else if (COMMANDS[primary]) {
      await COMMANDS[primary](args);
    } else {
      printLine(`bash: command not found: ${primary}. Type <b style="color:#00e5ff;">help</b> for available commands.`, "error");
    }
  }

  // --- Event Listeners ---

  if (termInput) {
    termInput.addEventListener("keydown", async (e) => {
      if (e.key === "Enter") {
        const val = termInput.value;
        termInput.value = "";
        await handleCommand(val);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (state.historyIndex > 0) {
          state.historyIndex--;
          termInput.value = state.history[state.historyIndex];
        }
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (state.historyIndex < state.history.length - 1) {
          state.historyIndex++;
          termInput.value = state.history[state.historyIndex];
        } else {
          state.historyIndex = state.history.length;
          termInput.value = "";
        }
      } else if (e.key === "l" && e.ctrlKey) {
        e.preventDefault();
        await COMMANDS.clear();
      }
    });
  }

  // Terminal tool buttons
  document.getElementById("termClearBtn")?.addEventListener("click", () => COMMANDS.clear());
  document.getElementById("termHelpBtn")?.addEventListener("click", () => COMMANDS.help());

  // Quick suggestion chips
  document.querySelectorAll(".sugg-chip, .atk-quick-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cmd = btn.dataset.cmd;
      if (cmd) {
        handleCommand(cmd);
      }
    });
  });

  // Filesystem click-to-view
  document.querySelectorAll(".fs-file-item").forEach((item) => {
    item.addEventListener("click", () => {
      const fname = item.dataset.file;
      if (fname) {
        handleCommand(`cat ${fname}`);
      }
    });
  });

  document.querySelectorAll(".fs-dir-title").forEach((dir) => {
    dir.addEventListener("click", () => {
      const dname = dir.dataset.dir;
      if (dname) {
        handleCommand(`cd ${dname}`);
      }
    });
  });

  // Auto-focus input on click anywhere in terminal
  terminalBody?.addEventListener("click", () => {
    termInput?.focus();
  });

  // Init
  printWelcomeBanner();
  updateUIState();

})();
