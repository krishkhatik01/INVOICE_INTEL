import os
import json
import shutil
import tempfile
import threading
import uuid
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from dotenv import load_dotenv

from agent import InvoiceIntelAgent
from processor import DocumentProcessor
from pdf_generator import generate_pdf_from_json
from priority_calculator import recalculate_all_priorities

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="InvoiceIntel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store. For a multi-instance deployment, swap this for Redis
# or another shared store.
JOBS = {}
JOBS_LOCK = threading.Lock()

JOB_TTL = timedelta(hours=2)


def _cleanup_old_jobs():
    now = datetime.utcnow()
    with JOBS_LOCK:
        expired = [jid for jid, job in JOBS.items() if now - job["created_at"] > JOB_TTL]
        for jid in expired:
            job = JOBS.pop(jid, None)
            if job and os.path.isdir(job["work_dir"]):
                shutil.rmtree(job["work_dir"], ignore_errors=True)


def _run_job(job_id: str, work_dir: str):
    agent = InvoiceIntelAgent()

    def progress_callback(idx, total, filename):
        with JOBS_LOCK:
            JOBS[job_id].update({
                "status": "processing",
                "current_index": idx,
                "total_files": total,
                "current_file": filename,
            })

    try:
        report_json = agent.run_analysis(work_dir, progress_callback=progress_callback)
        report = json.loads(report_json)

        if "error" in report:
            with JOBS_LOCK:
                JOBS[job_id].update({"status": "error", "error": report["error"]})
            return

        # Recalculate priorities based on invoice characteristics
        report = recalculate_all_priorities(report)

        with JOBS_LOCK:
            JOBS[job_id].update({"status": "done", "result": report})

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        with JOBS_LOCK:
            JOBS[job_id].update({"status": "error", "error": str(e)})

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.post("/api/analyze")
async def analyze(files: list[UploadFile] = File(...)):
    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured on the server.")

    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    _cleanup_old_jobs()

    job_id = str(uuid.uuid4())
    work_dir = tempfile.mkdtemp(prefix=f"invoiceintel_{job_id}_")

    saved = []
    skipped = []

    for upload in files:
        filename = os.path.basename(upload.filename or "")
        if not filename:
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in DocumentProcessor.SUPPORTED_EXTENSIONS:
            skipped.append(filename)
            continue

        dest_path = os.path.join(work_dir, filename)
        # Avoid collisions if two uploaded files share a name
        counter = 1
        base, extension = os.path.splitext(dest_path)
        while os.path.exists(dest_path):
            dest_path = f"{base}_{counter}{extension}"
            counter += 1

        with open(dest_path, "wb") as f:
            shutil.copyfileobj(upload.file, f)
        saved.append(filename)

    if not saved:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"No supported files were uploaded. Supported types: {', '.join(sorted(DocumentProcessor.SUPPORTED_EXTENSIONS))}"
        )

    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "processing",
            "created_at": datetime.utcnow(),
            "work_dir": work_dir,
            "total_files": len(saved),
            "current_index": 0,
            "current_file": "",
            "skipped_files": skipped,
            "result": None,
            "error": None,
        }

    thread = threading.Thread(target=_run_job, args=(job_id, work_dir), daemon=True)
    thread.start()

    return {"job_id": job_id, "files_accepted": saved, "files_skipped": skipped}


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found or expired.")

        response = {
            "status": job["status"],
            "current_index": job["current_index"],
            "total_files": job["total_files"],
            "current_file": job["current_file"],
            "skipped_files": job["skipped_files"],
        }
        if job["status"] == "done":
            response["result"] = job["result"]
        elif job["status"] == "error":
            response["error"] = job["error"]

        return response


@app.get("/api/pdf/{job_id}")
async def get_pdf(job_id: str):
    """Generate and download PDF report for a completed job analysis."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found or expired.")
        
        if job["status"] != "done":
            raise HTTPException(
                status_code=400, 
                detail=f"Job is still {job['status']}. Wait for job to complete before generating PDF."
            )
        
        if not job["result"]:
            raise HTTPException(status_code=400, detail="No results available for PDF generation.")
    
    try:
        pdf_bytes = generate_pdf_from_json(job["result"])
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=invoice_report_{job_id}.pdf"}
        )
    except Exception as e:
        logger.exception(f"Failed to generate PDF for job {job_id}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@app.get("/api/supported-formats")
async def supported_formats():
    return {"extensions": sorted(DocumentProcessor.SUPPORTED_EXTENSIONS)}


@app.get("/api/demo")
async def demo():
    demo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_report.json")
    if os.path.exists(demo_path):
        with open(demo_path, "r") as f:
            data = json.load(f)
            # Recalculate priorities based on invoice characteristics
            data = recalculate_all_priorities(data)
            return JSONResponse(data)
    return JSONResponse({"summary": {"total_invoices": 0, "high_priority": 0, "flagged_for_review": 0, "total_amount_extracted": 0}, "invoices": []})


@app.get("/api/demo/pdf")
async def demo_pdf():
    """Generate and download a sample PDF report from demo data."""
    demo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_report.json")
    if not os.path.exists(demo_path):
        raise HTTPException(status_code=404, detail="Demo report not found.")
    
    try:
        with open(demo_path, "r") as f:
            demo_data = json.load(f)
        
        # Recalculate priorities based on invoice characteristics
        demo_data = recalculate_all_priorities(demo_data)
        
        pdf_bytes = generate_pdf_from_json(demo_data)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=invoice_report_demo.pdf"}
        )
    except Exception as e:
        logger.exception("Failed to generate demo PDF")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


# ── Serve frontend ──
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/")
async def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "InvoiceIntel API is running. Frontend not found in /static."})


if __name__ == "__main__":
    import uvicorn
    if not os.environ.get("GROQ_API_KEY"):
        print("CRITICAL: GROQ_API_KEY not found in .env file.")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
