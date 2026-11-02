from __future__ import annotations

import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ...schemas.job import (
    EvidenceDetailResponse,
    JobCreateResponse,
    JobSnapshotResponse,
)
from ...services.job_service import JobService
from ..deps import get_job_service

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("", response_model=JobCreateResponse)
async def create_job(
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    query: str = Form(...),
    job_service: JobService = Depends(get_job_service),
):
    """
    Main entry point to initiate a data analysis job.

    Accepts single or multiple dataset files and a natural language query,
    initializes an isolated workspace, and launches the autonomous agent pipeline.
    """
    incoming: list[UploadFile] = []
    if files:
        incoming.extend(files)
    if file and not any(f.filename == file.filename for f in incoming):
        incoming.append(file)

    job = await job_service.create_analysis_job(query=query, incoming_files=incoming)
    return JobCreateResponse(job_id=job.id)


@router.post("/{job_id}/messages", response_model=JobCreateResponse)
async def continue_job(
    job_id: str,
    request: Request,
    job_service: JobService = Depends(get_job_service),
):
    """
    Submit a follow-up query to an existing session.

    Re-uses existing datasets from prior turns and allows uploading additional
    datasets mid-conversation for comparative analysis.
    """
    content_type = request.headers.get("content-type", "")
    new_incoming: list[UploadFile] = []

    history_raw = None
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        query = (form.get("query") or "").strip()
        history_raw = form.get("history")
        for item in form.getlist("files"):
            if hasattr(item, "filename") and item.filename:
                new_incoming.append(item)
        single_file = form.get("file")
        if hasattr(single_file, "filename") and single_file.filename:
            if not any(getattr(f, "filename", None) == single_file.filename for f in new_incoming):
                new_incoming.append(single_file)
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        query = (body.get("query") or "").strip()
        history_raw = body.get("history")

    history_list = None
    if history_raw:
        if isinstance(history_raw, str):
            try:
                history_list = json.loads(history_raw)
            except Exception:
                pass
        elif isinstance(history_raw, list):
            history_list = history_raw

    job = await job_service.continue_analysis_job(
        job_id=job_id,
        query=query,
        new_files=new_incoming,
        history=history_list,
    )
    return JobCreateResponse(job_id=job.id)


@router.get("/{job_id}", response_model=JobSnapshotResponse)
def get_job(job_id: str, job_service: JobService = Depends(get_job_service)):
    """
    Retrieve current status, plan, report, artifacts, and evidence IDs for a job.
    """
    return job_service.get_job_snapshot(job_id)


@router.get("/{job_id}/events")
def job_events(
    job_id: str,
    request: Request,
    job_service: JobService = Depends(get_job_service),
):
    """
    Real-time event streaming via Server-Sent Events (SSE).

    Supports reconnection via Last-Event-ID header and periodic keep-alive heartbeats.
    """
    try:
        job = job_service.get_job_or_404(job_id)
    except HTTPException:
        # If job does not exist anymore (e.g. server restarted or job expired),
        # return HTTP 204 No Content so browser EventSource immediately halts reconnecting.
        return Response(status_code=204)

    last = request.headers.get("last-event-id", "")
    start = int(last) + 1 if last.isdigit() else 0

    # If the job is already finished and all events have been streamed, return 204 No Content.
    # Per W3C EventSource standard, HTTP 204 instructs the browser to permanently close the SSE connection without reconnecting.
    if job.done and start >= len(job.events):
        return Response(status_code=204)

    def gen():
        for item in job.iter_events(start):
            if item is None:
                yield ": keep-alive\n\n"
                continue
            idx, event = item
            yield f"id: {idx}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/files/{name}")
def get_file(
    job_id: str,
    name: str,
    job_service: JobService = Depends(get_job_service),
):
    """
    Download or serve an artifact file (chart image or cleaned CSV) produced by the agent.
    Secured with strict artifact whitelisting and nosniff header.
    """
    path, media_type = job_service.get_artifact_file(job_id, name)
    return FileResponse(path, media_type=media_type, headers={"X-Content-Type-Options": "nosniff"})


@router.get("/{job_id}/evidence/{eid}", response_model=EvidenceDetailResponse)
def get_evidence(
    job_id: str,
    eid: str,
    job_service: JobService = Depends(get_job_service),
):
    """
    Fetch exact code and sandbox execution output behind a cited claim.
    """
    return job_service.get_evidence_detail(job_id, eid)
