"""
Simulated 'Data Protection Board of India' portal.

Educational simulation for the DPDP Act, 2023 breach notification workflow:
persists filings via `app/database.py` (`submitted_reports` table) and stores
generated PDF copies under `dpb_storage/`.
"""

import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app import database

router = APIRouter()
templates = Jinja2Templates(directory="templates")

DPB_STORAGE = Path(__file__).resolve().parent.parent / "dpb_storage"

# In-memory cache synced with database.submitted_reports
SUBMISSIONS: list[dict] = []


def load_from_db() -> None:
    SUBMISSIONS.clear()
    SUBMISSIONS.extend(database.db_get_submitted_reports(limit=100))


def receive_submission(pdf_bytes: bytes, meta: dict) -> dict:
    """Persist the breach PDF, issue an acknowledgement number, and record it in DB."""
    DPB_STORAGE.mkdir(exist_ok=True)
    ack_number = f"DPB-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    filename = f"{ack_number}.pdf"
    (DPB_STORAGE / filename).write_bytes(pdf_bytes)

    now = time.time()
    record = {
        "ack_number": ack_number,
        "filename": filename,
        "received_at": now,
        "submitted_at": now,
        "incident_id": meta.get("incident_id"),
        "stage": meta.get("stage", "preliminary"),
        "company_name": meta.get("company_name", "TrapWire Pvt Ltd"),
        "attacker_ip": meta.get("attacker_ip"),
        "attacker_isp": meta.get("attacker_isp"),
        "detected_at": meta.get("detected_at"),
        "ack_status": "ACKNOWLEDGED",
        "status": "ACKNOWLEDGED",
    }
    SUBMISSIONS.append(record)
    return record


def reset() -> None:
    SUBMISSIONS.clear()


@router.get("/dpb", response_class=HTMLResponse)
def dpb_registry(request: Request):
    if not SUBMISSIONS:
        load_from_db()
    return templates.TemplateResponse("dpb_index.html", {
        "request": request,
        "submissions": list(reversed(SUBMISSIONS)),
    })


@router.get("/dpb/submission/{ack_number}", response_class=HTMLResponse)
def dpb_detail(ack_number: str, request: Request):
    if not SUBMISSIONS:
        load_from_db()
    record = next((s for s in SUBMISSIONS if s["ack_number"] == ack_number), None)
    if not record:
        return HTMLResponse("<h1>No such acknowledgement number on record.</h1>", status_code=404)
    deadline = (record["detected_at"] + 72 * 3600) if record.get("detected_at") else None
    return templates.TemplateResponse("dpb_detail.html", {
        "request": request,
        "r": record,
        "deadline": deadline,
    })


@router.get("/dpb/download/{filename}")
def dpb_download(filename: str):
    storage_root = DPB_STORAGE.resolve()
    path = (storage_root / filename).resolve()
    if not path.is_file() or path.parent != storage_root:
        return JSONResponse({"error": "not found"}, status_code=404)
    return Response(
        content=path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={path.name}"},
    )
