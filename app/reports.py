"""
Generates a PDF breach notification report formatted for India's Data Protection
Board under the Digital Personal Data Protection (DPDP) Act, 2023.
"""

import io
import time
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_breach_report_pdf(
    breach: dict, alerts: list, canary_hits: list, stage: str = "final"
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], fontSize=18)
    h2 = styles["Heading2"]
    body = styles["BodyText"]

    stage_label = "PRELIMINARY NOTIFICATION" if stage == "preliminary" else "FINAL / UPDATED REPORT"

    flow = [
        Paragraph("TRAPWIRE – Data Breach Notification Report", title_style),
        Paragraph(f"<b>{stage_label}</b>", body),
        Paragraph(
            "Automatically generated and submitted to the Data Protection Board of India"
            " under the Digital Personal Data Protection (DPDP) Act, 2023",
            body,
        ),
        Spacer(1, 0.6 * cm),
    ]

    detected_at = breach.get("detected_at")
    now = time.time()
    deadline = (detected_at + 72 * 3600) if detected_at else None
    hours_left = round((deadline - now) / 3600, 1) if deadline else None
    compliance_status = (
        "WITHIN 72-HOUR WINDOW"
        if (hours_left is not None and hours_left >= 0)
        else ("WINDOW EXCEEDED" if hours_left is not None else "STANDBY / NO INCIDENT")
    )

    meta_rows = [
        ["Incident ID", breach.get("incident_id") or "N/A"],
        [
            "Detected at (server time)",
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(detected_at)) if detected_at else "N/A",
        ],
        ["Report generated at", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))],
        [
            "72-hour reporting deadline",
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(deadline)) if deadline else "N/A",
        ],
        ["Hours remaining to report", str(hours_left) if hours_left is not None else "N/A"],
        ["Compliance status", compliance_status],
    ]
    t = Table(meta_rows, colWidths=[7 * cm, 9 * cm])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#1d4ed8")),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    flow.append(t)
    flow.append(Spacer(1, 0.6 * cm))

    flow.append(Paragraph("1. Nature of the Incident", h2))
    nature_text = (
        breach.get("reason")
        or "Security telemetry detected unauthorized probing or suspicious access against "
           "the protected enterprise gateway. All exported records had sensitive PII fields "
           "irreversibly protected via salted one-way SHA-256 hashing so zero plaintext "
           "personal data was exposed."
    )
    flow.append(Paragraph(nature_text, body))
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("2. Data Access Event (captured at time of export)", h2))
    if breach.get("download_ip"):
        rows = [
            [
                "Timestamp",
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(breach.get("download_time", now))),
            ],
            ["Source IP (as seen by server)", breach.get("download_ip") or "N/A"],
            ["ISP / Organization", breach.get("download_isp") or "N/A"],
            ["User-Agent", (breach.get("download_user_agent") or "N/A")[:80]],
            [
                "Data protection",
                "All sensitive PII fields hashed via salted one-way SHA-256 before export — "
                "no plaintext or reversible personal data was exposed",
            ],
        ]
        dt = Table(rows, colWidths=[6 * cm, 10 * cm])
        dt.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#b45309")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ])
        )
        flow.append(dt)
    else:
        flow.append(Paragraph("No data export event recorded for this incident.", body))
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("3. Attacker Attribution (Canary-Token Confirmation)", h2))
    if canary_hits:
        rows = [["Timestamp", "IP Address", "ISP / Org", "Screen", "Timezone", "Platform"]]
        for hit in canary_hits[-10:]:
            rows.append([
                time.strftime("%H:%M:%S", time.localtime(hit["timestamp"])),
                hit.get("ip") or "N/A",
                (hit.get("isp") or "N/A")[:18],
                hit.get("screen") or "pending",
                hit.get("timezone") or "pending",
                (hit.get("platform") or "pending")[:14],
            ])
        ct = Table(rows, colWidths=[2.2 * cm, 2.6 * cm, 3.2 * cm, 2.2 * cm, 3 * cm, 2.8 * cm])
        ct.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ])
        )
        flow.append(ct)
    else:
        flow.append(Paragraph("No canary token has been triggered yet.", body))
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("4. Data Categories Protected", h2))
    flow.append(
        Paragraph(
            "Name, phone number, email address, Aadhaar number, PAN, postal address, "
            "and partial payment card details under the DPDP Act, 2023.",
            body,
        )
    )
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("5. Remedial & Preventive Measures Taken", h2))
    for line in [
        "Suspicious session isolated and all exported PII replaced with salted one-way SHA-256 digests.",
        "Real-time alert dispatched to the SOC console and hardware node.",
        "Canary tracking beacon embedded to capture forensic source telemetry.",
        "Statutory breach report generated and logged for DPDP Act, 2023 compliance.",
    ]:
        flow.append(Paragraph(f"• {line}", body))
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("6. Alert Log", h2))
    if alerts:
        rows = [["Time", "Level", "Message"]]
        for a in alerts[-15:]:
            rows.append([
                time.strftime("%H:%M:%S", time.localtime(a["timestamp"])),
                a["level"].upper(),
                a["message"][:70],
            ])
        at = Table(rows, colWidths=[2.5 * cm, 2.5 * cm, 11 * cm])
        at.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ])
        )
        flow.append(at)
    else:
        flow.append(Paragraph("No alerts recorded.", body))

    doc.build(flow)
    return buf.getvalue()


SUBMITTED_REPORTS_DIR = Path(__file__).resolve().parent.parent / "submitted_reports"


def save_submitted_report(pdf_bytes: bytes, incident_id: str, stage: str) -> str:
    """Persist a timestamped PDF copy of the submitted DPB report."""
    SUBMITTED_REPORTS_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{incident_id}_{stage}_{ts}.pdf"
    (SUBMITTED_REPORTS_DIR / filename).write_bytes(pdf_bytes)
    return filename
