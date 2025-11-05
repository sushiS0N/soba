"""
FastAPI server for solar analysis with job queue
Run with: python server.py
"""

from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import uuid
import os
from pathlib import Path
from typing import Dict
import shutil
from datetime import datetime
import importlib.util

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent  # Now just one level up!
sys.path.insert(0, str(PROJECT_ROOT))

import config

# Import pipeline using importlib (same as weather fix)
pipeline_path = Path(__file__).parent / "pipeline.py"
spec = importlib.util.spec_from_file_location("pipeline", pipeline_path)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


app = FastAPI(title="Solar Analysis Server")

# Job storage
JOBS_DIR = config.JOBS_DIR
JOBS_DIR.mkdir(exist_ok=True)

print(JOBS_DIR)
jobs: Dict[str, dict] = {}


def process_job(job_id: str, usd_path: str, epw_path: str):
    """Background task to run OptiX analysis"""
    try:
        print(f"[{job_id}] Starting analysis...")
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["started_at"] = datetime.now().isoformat()

        # Fix EPW path in USD to point to uploaded EPW
        from pxr import Usd

        stage = Usd.Stage.Open(usd_path)
        root = stage.GetDefaultPrim()
        root.SetCustomDataByKey("solar:epwFile", epw_path)
        stage.Save()
        print(f"[{job_id}] Updated EPW path in USD to: {epw_path}")

        # Import and run pipeline
        import sys

        sys.path.insert(0, str(Path(__file__).parent))

        from pipeline import analyze_solar_scene

        # Run analysis (this will create {usd_path}_results.usda)
        result_path = analyze_solar_scene(usd_path)

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["result_path"] = result_path
        jobs[job_id]["completed_at"] = datetime.now().isoformat()

        print(f"[{job_id}]  Complete!")

    except Exception as e:
        print(f"[{job_id}]  Error: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)

        import traceback

        jobs[job_id]["traceback"] = traceback.format_exc()


@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "running",
        "jobs": {
            "total": len(jobs),
            "queued": sum(1 for j in jobs.values() if j["status"] == "queued"),
            "processing": sum(1 for j in jobs.values() if j["status"] == "processing"),
            "complete": sum(1 for j in jobs.values() if j["status"] == "complete"),
            "error": sum(1 for j in jobs.values() if j["status"] == "error"),
        },
    }


@app.post("/submit")
async def submit_job(
    background_tasks: BackgroundTasks,
    usd_file: UploadFile = File(...),
    epw_file: UploadFile = File(...),
):
    """Submit a new solar analysis job"""
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir()

    print(f"[{job_id}] New job submitted")

    # Save uploaded files
    usd_path = job_dir / "scene.usda"
    epw_path = job_dir / "weather.epw"

    with open(usd_path, "wb") as f:
        f.write(await usd_file.read())
    with open(epw_path, "wb") as f:
        f.write(await epw_file.read())

    print(
        f"[{job_id}] Files saved: {usd_path.stat().st_size} bytes (USD), {epw_path.stat().st_size} bytes (EPW)"
    )

    # Initialize job
    jobs[job_id] = {
        "status": "queued",
        "result_path": None,
        "error": None,
        "submitted_at": datetime.now().isoformat(),
    }

    # Queue for processing
    background_tasks.add_task(process_job, job_id, str(usd_path), str(epw_path))

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job submitted successfully",
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Check job status"""
    if job_id not in jobs:
        return JSONResponse(
            {"error": "Job not found", "job_id": job_id}, status_code=404
        )

    job = jobs[job_id]
    response = {
        "job_id": job_id,
        "status": job["status"],
        "submitted_at": job.get("submitted_at"),
    }

    if job["status"] == "processing":
        response["started_at"] = job.get("started_at")

    if job["status"] == "complete":
        response["completed_at"] = job.get("completed_at")

    if job["status"] == "error":
        response["error"] = job.get("error")
        response["traceback"] = job.get("traceback")

    return response


@app.get("/result/{job_id}")
async def get_result(job_id: str):
    """Download completed result file"""
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    job = jobs[job_id]

    if job["status"] != "complete":
        return JSONResponse(
            {
                "error": "Job not ready",
                "status": job["status"],
                "message": "Wait for status to be 'complete'",
            },
            status_code=400,
        )

    result_path = job["result_path"]

    if not os.path.exists(result_path):
        return JSONResponse({"error": "Result file not found"}, status_code=500)

    return FileResponse(
        result_path,
        filename=f"solar_results_{job_id}.usda",
        media_type="application/octet-stream",
    )


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Clean up job files"""
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    # Remove job directory
    job_dir = JOBS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)

    # Remove from memory
    del jobs[job_id]

    return {"message": "Job deleted", "job_id": job_id}


if __name__ == "__main__":
    print("=" * 60)
    print(" Solar Analysis Server")
    print("=" * 60)
    print(f"Starting server on http://{config.SERVER_HOST}:{config.SERVER_PORT}")
    print(f"API docs: http://{config.SERVER_HOST}:{config.SERVER_PORT}/docs")
    print(f"Jobs directory: {JOBS_DIR}")
    print("=" * 60)

    uvicorn.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT)
