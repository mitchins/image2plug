import json
import shutil
from pathlib import Path
import os
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from db.models import SessionLocal, Job, purge_old_jobs
from lib.jobs import generate_job_id, run_job, RESULTS_DIR

app = FastAPI(title="image2plug Web")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event():
    RESULTS_DIR.mkdir(exist_ok=True)
    session = SessionLocal()
    purge_old_jobs(session)
    session.close()


@app.post("/upload")
def upload_image(background_tasks: BackgroundTasks,
                 image: UploadFile = File(...),
                 smooth: bool = Form(False),
                 measure_error: bool = Form(False),
                 border_mode: str = Form("tight"),
                 cf_turnstile_response: str = Form(None)):
    if os.getenv("TURNSTILE_SITE_KEY") and os.getenv("TURNSTILE_SECRET_KEY"):
        if not cf_turnstile_response:
            raise HTTPException(status_code=400, detail="Turnstile token missing")
    job_id = generate_job_id()
    output_dir = RESULTS_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / image.filename
    with input_path.open("wb") as f:
        f.write(image.file.read())

    job = Job(id=job_id,
              status="queued",
              options=json.dumps({
                  "smooth": smooth,
                  "measure_error": measure_error,
                  "border_mode": border_mode,
              }),
              input_path=str(input_path),
              output_dir=str(output_dir))
    session = SessionLocal()
    session.add(job)
    session.commit()
    session.close()

    background_tasks.add_task(process_job, job_id)
    return JSONResponse({"job_id": job_id})


def process_job(job_id: str):
    session = SessionLocal()
    job = session.query(Job).get(job_id)
    if not job:
        session.close()
        return
    job.status = "running"
    session.commit()

    try:
        res = run_job(Path(job.input_path), Path(job.output_dir),
                       smooth=job.options_dict().get("smooth"),
                       measure_error=job.options_dict().get("measure_error"),
                       border_mode=job.options_dict().get("border_mode", "tight"))
        static_job = Path("app/static") / job_id
        if static_job.exists():
            shutil.rmtree(static_job)
        shutil.copytree(job.output_dir, static_job)
        job.status = "finished"
        job.result_json = json.dumps(res)
    except Exception as exc:  # pragma: no cover
        job.status = "error"
        job.result_json = json.dumps({"error": str(exc)})
    finally:
        session.commit()
        purge_old_jobs(session)
        session.close()


@app.get("/status/{job_id}")
def job_status(job_id: str):
    session = SessionLocal()
    job = session.query(Job).get(job_id)
    if not job:
        session.close()
        return JSONResponse({"error": "not found"}, status_code=404)
    data = {
        "job_id": job.id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
    }
    session.close()
    return JSONResponse(data)


@app.get("/results/{job_id}", response_class=HTMLResponse)
def job_results(request: Request, job_id: str):
    session = SessionLocal()
    job = session.query(Job).get(job_id)
    if not job or job.status != "finished":
        session.close()
        return HTMLResponse("Job not ready", status_code=404)
    result = json.loads(job.result_json)
    session.close()
    return templates.TemplateResponse("results.html", {
        "request": request,
        "job_id": job_id,
        "input_image": Path(job.input_path).name,
        "output_dir": job.output_dir,
        "result": result,
    })

