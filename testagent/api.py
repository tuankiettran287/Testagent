from __future__ import annotations

import json
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from .automation import checked_url, validate_automation
from .ai_providers import provider_manager
from .cli_transport import CliError
from .browser_bridge import BrowserRunnerError, browser_runner_available, invoke_browser
from .config import settings
from .db import connection, decode_case, init_db, many, now, one, uid
from .ingest import ingest_document, ingest_openapi, ingest_repository, ingest_zip
from .knowledge import add_source, coverage, retrieve
from .planner import run_task
from .runner import execute_run, prepare_run
from .readiness import case_readiness
from .schemas import AiLogin, AiSelection, Automation, ProjectCreate, ProjectUpdate, RepositoryImport, RunCreate, TaskCreate, UiInspectRequest
from .skills import compose_skill, get_skill, list_skills, read_skill


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        yield
    finally:
        provider_manager.close()


app = FastAPI(title="TestAgent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin], allow_methods=["*"], allow_headers=["*"])


def project_or_404(project_id: str) -> dict:
    project = one("SELECT * FROM projects WHERE id=?", (project_id,))
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def case_or_404(case_id: str) -> dict:
    case = one("SELECT * FROM test_cases WHERE id=?", (case_id,))
    if not case:
        raise HTTPException(404, "Test case not found")
    return decode_case(case)


@app.get("/api/health")
def health():
    ai = provider_manager.overview()
    return {
        "status": "ok",
        "model_configured": ai["ready"],
        "ai_selection": ai["selection"],
        "browser_runner_ready": browser_runner_available(),
    }


def check_ai_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in {settings.web_origin.rstrip("/"), str(request.base_url).rstrip("/")}:
        raise HTTPException(403, "AI connection actions must originate from the configured application.")


@app.get("/api/ai/providers")
def get_ai_providers(refresh: bool = False):
    return provider_manager.overview(refresh)


@app.put("/api/ai/selection", dependencies=[Depends(check_ai_origin)])
def select_ai(payload: AiSelection):
    try:
        return provider_manager.select(payload.provider, payload.model, payload.effort)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except CliError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/ai/providers/{provider}/login", dependencies=[Depends(check_ai_origin)])
def login_ai(provider: str, payload: AiLogin):
    try:
        return provider_manager.start_login(provider, payload.device_code)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (CliError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/ai/providers/{provider}/login/cancel", dependencies=[Depends(check_ai_origin)])
def cancel_ai_login(provider: str):
    try:
        provider_manager.cancel_login(provider)
        return {"message": "Đã hủy đăng nhập."}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except CliError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/ai/providers/{provider}/logout", dependencies=[Depends(check_ai_origin)])
def logout_ai(provider: str):
    try:
        return provider_manager.logout(provider)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (CliError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate):
    base_url = payload.base_url.strip().rstrip("/")
    if base_url and (urlparse(base_url).scheme not in {"http", "https"} or not urlparse(base_url).hostname):
        raise HTTPException(422, "base_url must be an HTTP(S) URL")
    project_id = uid()
    with connection() as db:
        db.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
            (project_id, payload.name.strip(), base_url, payload.environment, now()),
        )
    return project_or_404(project_id)


@app.get("/api/projects")
def list_projects():
    return many("SELECT * FROM projects ORDER BY created_at DESC")


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return project_or_404(project_id)


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate):
    project_or_404(project_id)
    base_url = payload.base_url.strip().rstrip("/")
    if base_url and (urlparse(base_url).scheme not in {"http", "https"} or not urlparse(base_url).hostname):
        raise HTTPException(422, "base_url must be an HTTP(S) URL")
    with connection() as db:
        db.execute("UPDATE projects SET base_url=?, environment=? WHERE id=?", (base_url, payload.environment, project_id))
    return project_or_404(project_id)


@app.post("/api/projects/{project_id}/documents", status_code=201)
async def upload_document(project_id: str, file: UploadFile = File(...)):
    project_or_404(project_id)
    try:
        source_id = ingest_document(project_id, file.filename or "document.txt", await file.read(8 * 1024 * 1024 + 1))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"source_id": source_id}


@app.post("/api/projects/{project_id}/repositories", status_code=201)
def import_repository(project_id: str, payload: RepositoryImport):
    project_or_404(project_id)
    try:
        return ingest_repository(project_id, payload.location)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/projects/{project_id}/repositories/zip", status_code=201)
async def upload_repository(project_id: str, file: UploadFile = File(...)):
    project_or_404(project_id)
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(422, "A .zip file is required")
    try:
        return ingest_zip(project_id, file.filename or "source.zip", await file.read(50 * 1024 * 1024 + 1))
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/projects/{project_id}/openapi", status_code=201)
async def upload_openapi(project_id: str, file: UploadFile = File(...)):
    project_or_404(project_id)
    try:
        source_id = ingest_openapi(project_id, file.filename or "openapi.yaml", await file.read(8 * 1024 * 1024 + 1))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"source_id": source_id}


@app.get("/api/projects/{project_id}/sources")
def list_sources(project_id: str):
    project_or_404(project_id)
    return many("SELECT id, kind, name, origin, created_at FROM sources WHERE project_id=? ORDER BY created_at DESC", (project_id,))


@app.get("/api/projects/{project_id}/knowledge")
def search_knowledge(project_id: str, q: str):
    project_or_404(project_id)
    return retrieve(project_id, q)


@app.get("/api/projects/{project_id}/coverage")
def get_coverage(project_id: str):
    project_or_404(project_id)
    return coverage(project_id)


@app.post("/api/projects/{project_id}/inspect-ui", status_code=201)
def inspect_ui(project_id: str, payload: UiInspectRequest):
    project = project_or_404(project_id)
    try:
        url = checked_url(project["base_url"], payload.path)
        snapshot = invoke_browser("inspect", {"baseUrl": project["base_url"], "path": payload.path}, timeout=45)
        source_id = add_source(project_id, "ui", f"UI: {payload.path}", f"ui:{url}", json.dumps(snapshot, ensure_ascii=False, indent=2))
        return {"source_id": source_id, "elements": len(snapshot["elements"])}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except BrowserRunnerError as exc:
        raise HTTPException(502, str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(504, str(exc)) from exc


@app.post("/api/agent/tasks", status_code=202)
def create_task(payload: TaskCreate, background_tasks: BackgroundTasks):
    project = project_or_404(payload.project_id)
    try:
        function = payload.function or 'orchestrator'
        skill = get_skill('orchestrator' if function == 'auto' else function)
        if skill.mode == 'execution':
            read_skill(skill.id)
        else:
            compose_skill(skill.id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if skill.workflow == 'browser' and project['base_url']:
        if project['environment'] == 'production' and not settings.allow_production_execution:
            raise HTTPException(403, 'Execution in production is disabled')
        if not browser_runner_available():
            raise HTTPException(503, 'Build browser_runner and install Chromium before running website automation')
    automatic = skill.mode == 'orchestration'
    if payload.run_id and skill.requires != "run" and not automatic:
        raise HTTPException(422, "run_id is only valid for run-based functions")
    if payload.run_id and not one(
        "SELECT id FROM runs WHERE id=? AND project_id=?", (payload.run_id, payload.project_id)
    ):
        raise HTTPException(422, "Selected run does not belong to this project")
    if skill.requires == 'cases' and not payload.case_ids:
        raise HTTPException(422, 'Select test cases for this agent')
    if skill.requires == 'cases' and len(set(payload.case_ids)) > skill.max_cases:
        raise HTTPException(422, f'{skill.label} supports at most {skill.max_cases} cases per task')
    if payload.case_ids:
        if skill.requires != 'cases' and not automatic:
            raise HTTPException(422, 'This agent does not accept selected case IDs')
        placeholders = ','.join('?' for _ in payload.case_ids)
        owned = many(f'SELECT id FROM test_cases WHERE project_id=? AND id IN ({placeholders})', (payload.project_id, *payload.case_ids))
        if len(owned) != len(set(payload.case_ids)):
            raise HTTPException(422, 'Some selected cases do not belong to this project')
    try:
        selected = provider_manager.resolve(payload.provider, payload.model, payload.effort) if skill.mode != 'execution' else {}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except CliError as exc:
        raise HTTPException(409, str(exc)) from exc
    task_id = uid()
    with connection() as db:
        db.execute(
            "INSERT INTO tasks (id, project_id, prompt, intent, skill_file, status, created_at, ai_provider, ai_model, ai_effort) VALUES (?, ?, ?, ?, ?, 'CREATED', ?, ?, ?, ?)",
            (task_id, payload.project_id, payload.prompt, skill.id, skill.file, now(), selected.get("provider"), selected.get("model"), selected.get("effort")),
        )
    background_tasks.add_task(run_task, task_id, payload.project_id, payload.prompt, skill.id, payload.run_id,
                              selected.get("provider"), selected.get("model"), selected.get("effort"),
                              case_ids=payload.case_ids, execution_mode=payload.execution_mode,
                              run_mode=payload.run_mode, workers=payload.workers, agent_mode=payload.agent_mode)
    return _task_view(one("SELECT * FROM tasks WHERE id=?", (task_id,)))


@app.get("/api/agent/skills")
def get_agent_skills():
    return list_skills()


@app.get("/api/agent/skills/{skill_id}")
def get_agent_skill(skill_id: str):
    try:
        return {**get_skill(skill_id).public_dict(), "instructions": read_skill(skill_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


def _task_view(task: dict) -> dict:
    task['orchestration'] = json.loads(task.get('orchestration') or '{}')
    if not task.get("skill_file"):
        try:
            task["skill_file"] = get_skill(task["intent"]).file
        except ValueError:
            task["skill_file"] = None  # Tasks created before skill routing was introduced.
    return task


@app.get("/api/projects/{project_id}/tasks")
def list_tasks(project_id: str):
    project_or_404(project_id)
    rows = many("SELECT * FROM tasks WHERE project_id=? AND parent_task_id IS NULL ORDER BY created_at DESC LIMIT 50", (project_id,))
    children: dict[str, list[dict]] = {}
    if rows:
        placeholders = ','.join('?' for _ in rows)
        for child in many(f'SELECT * FROM tasks WHERE project_id=? AND parent_task_id IN ({placeholders}) ORDER BY created_at, id',
                          (project_id, *(row['id'] for row in rows))):
            children.setdefault(child['parent_task_id'], []).append(_task_view(child))
    return [{**_task_view(row), 'sub_tasks': children.get(row['id'], [])} for row in rows]


@app.get("/api/agent/tasks/{task_id}")
def get_task(task_id: str):
    task = one("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not task:
        raise HTTPException(404, "Task not found")
    return {**_task_view(task), 'sub_tasks': [_task_view(child) for child in many(
        'SELECT * FROM tasks WHERE parent_task_id=? AND project_id=? ORDER BY created_at, id', (task_id, task['project_id']))]}


@app.get("/api/agent/tasks/{task_id}/report", response_class=PlainTextResponse)
def download_agent_report(task_id: str):
    task = get_task(task_id)
    if task["intent"] != "report":
        raise HTTPException(422, "This task is not a report")
    if task["status"] != "COMPLETED":
        raise HTTPException(409, "Report is not ready")
    output = json.loads(task["summary"])
    lines = [
        "# QA Test Report", "", f"- Task: {task_id}",
        f"- Run: {output.get('run_id') or 'unknown'}", f"- Skill: {output['skill_file']}",
        "", "## Summary", "", output["summary"], "", "## Findings", "",
    ]
    for finding in output.get("findings", []):
        lines.extend([
            f"### {finding['title']} ({finding['severity']})", "", finding["detail"],
            "", f"Evidence IDs: {', '.join(finding.get('evidence_ids', [])) or 'none'}", "",
        ])
    lines.extend(["## Recommendations", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(output.get("recommendations", []), start=1))
    return PlainTextResponse(
        "\n".join(lines) + "\n",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="testagent-report-{task_id[:8]}.md"'},
    )


@app.get("/api/projects/{project_id}/tests")
def list_tests(project_id: str):
    project = project_or_404(project_id)
    rows = many('''SELECT tc.*,
        (SELECT rr.status FROM run_results rr JOIN runs r ON r.id=rr.run_id WHERE rr.test_case_id=tc.id ORDER BY r.requested_at DESC LIMIT 1) AS last_status,
        (SELECT rr.run_id FROM run_results rr JOIN runs r ON r.id=rr.run_id WHERE rr.test_case_id=tc.id ORDER BY r.requested_at DESC LIMIT 1) AS last_run_id
        FROM test_cases tc WHERE tc.project_id=? ORDER BY tc.created_at DESC LIMIT 200''', (project_id,))
    cases = [decode_case(row) for row in rows]
    for case in cases:
        case['readiness'] = case_readiness(case, project['base_url'])
    return cases


@app.get("/api/tests/{case_id}")
def get_test(case_id: str):
    case = case_or_404(case_id)
    case['readiness'] = case_readiness(case, project_or_404(case['project_id'])['base_url'])
    return case


@app.put("/api/tests/{case_id}/automation")
def update_automation(case_id: str, payload: Automation):
    case = case_or_404(case_id)
    project = project_or_404(case["project_id"])
    try:
        validate_automation(payload, project["base_url"])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with connection() as db:
        db.execute("UPDATE test_cases SET automation=? WHERE id=?", (payload.model_dump_json(exclude_none=True), case_id))
    return case_or_404(case_id)


@app.get("/api/tests/{case_id}/playwright", response_class=PlainTextResponse)
def get_playwright(case_id: str):
    case = case_or_404(case_id)
    if not case["automation"]:
        raise HTTPException(422, "This case has no browser automation DSL")
    project = project_or_404(case["project_id"])
    try:
        automation = Automation.model_validate(case["automation"])
        validate_automation(automation, project["base_url"])
        result = invoke_browser(
            "compile",
            {"baseUrl": project["base_url"], "title": case["title"], "automation": automation.model_dump(exclude_none=True)},
        )
        return result["source"]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except BrowserRunnerError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/tests/execute", status_code=202)
def create_run(payload: RunCreate, background_tasks: BackgroundTasks):
    project_or_404(payload.project_id)
    try:
        run_id = prepare_run(payload.project_id, payload.test_case_ids, payload.mode, payload.workers)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except BrowserRunnerError as exc:
        raise HTTPException(503, str(exc)) from exc
    background_tasks.add_task(execute_run, run_id)
    return one("SELECT * FROM runs WHERE id=?", (run_id,))


@app.get("/api/projects/{project_id}/runs")
def list_runs(project_id: str):
    project_or_404(project_id)
    return many("SELECT * FROM runs WHERE project_id=? ORDER BY requested_at DESC LIMIT 100", (project_id,))


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        raise HTTPException(404, "Run not found")
    run["summary"] = json.loads(run["summary"])
    results = many(
        """SELECT rr.*, tc.title, tc.level, tc.priority FROM run_results rr
           JOIN test_cases tc ON tc.id=rr.test_case_id WHERE rr.run_id=? ORDER BY tc.title""",
        (run_id,),
    )
    for result in results:
        result["artifacts"] = json.loads(result["artifacts"])
    run["results"] = results
    return run


@app.get("/api/reports/{run_id}")
def get_report(run_id: str):
    run = get_run(run_id)
    project = project_or_404(run["project_id"])
    return {
        "project": project["name"], "environment": project["environment"],
        "run_id": run_id, "status": run["status"], "started_at": run["started_at"],
        "finished_at": run["finished_at"], "summary": run["summary"],
        "results": run["results"], "coverage": coverage(project["id"]),
    }


@app.get("/api/runs/{run_id}/artifacts/{filename}")
def get_artifact(run_id: str, filename: str):
    if Path(filename).name != filename:
        raise HTTPException(400, "Invalid artifact name")
    if not one("SELECT id FROM runs WHERE id=?", (run_id,)):
        raise HTTPException(404, "Run not found")
    path = settings.data_dir / "artifacts" / run_id / filename
    if not path.is_file():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(path)

