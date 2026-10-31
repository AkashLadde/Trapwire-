"""
Simulated 'Data Protection Board of India' portal.

IMPORTANT: This is an educational simulation for a college capstone project.
It is NOT an official government website, does not use any official
government emblem/seal, and every page carries a visible disclaimer.
It exists purely so the company-side app has something realistic to
submit breach reports to and receive an acknowledgement from, entirely
on localhost.

Design note: rather than running this as a second server process (which
would mean juggling a second uvicorn instance, a second port, and a
second firewall prompt on the presenter's machine), it's mounted as a
separate router inside the same app. It has its own storage, its own
templates, and its own look-and-feel, so functionally and visually it
reads as an independent system -- the seam is just an implementation
convenience for the demo.
"""
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

DPB_STORAGE = Path(__file__).resolve().parent.parent / "dpb_storage"

# in-memory register of every submission received
SUBMISSIONS: list[dict] = []


def receive_submission(pdf_bytes: bytes, meta: dict) -> dict:
    """Called (in-process) by the company backend when it 'submits' a
    breach report. Stores the PDF, issues an acknowledgement number, and
    returns the acknowledgement record."""
    DPB_STORAGE.mkdir(exist_ok=True)
    ack_number = f"DPB-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    filename = f"{ack_number}.pdf"
    (DPB_STORAGE / filename).write_bytes(pdf_bytes)

    record = {
        "ack_number": ack_number,
        "filename": filename,
        "received_at": time.time(),
        "incident_id": meta.get("incident_id"),
        "stage": meta.get("stage"),
        "company_name": meta.get("company_name", "TrapWire Pvt Ltd"),
        "attacker_ip": meta.get("attacker_ip"),
        "attacker_isp": meta.get("attacker_isp"),
        "detected_at": meta.get("detected_at"),
        "status": "ACKNOWLEDGED",
    }
    SUBMISSIONS.append(record)
    return record


def reset():
    SUBMISSIONS.clear()


@router.get("/dpb", response_class=HTMLResponse)
def dpb_registry(request: Request):
    return templates.TemplateResponse("dpb_index.html", {
        "request": request,
        "submissions": list(reversed(SUBMISSIONS)),
    })


@router.get("/dpb/submission/{ack_number}", response_class=HTMLResponse)
def dpb_detail(ack_number: str, request: Request):
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
    path = DPB_STORAGE / filename
    if not path.exists() or path.parent != DPB_STORAGE:
        return JSONResponse({"error": "not found"}, status_code=404)
    return Response(content=path.read_bytes(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={filename}"})
