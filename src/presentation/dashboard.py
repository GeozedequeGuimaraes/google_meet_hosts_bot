import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

_HERE = Path(__file__).parent
_STATIC_DIR = str(_HERE / "static")
_TEMPLATE_DIR = str(_HERE / "templates")

from src.infrastructure.google.auth import SCOPES
from src.application.incident_service import IncidentStore
from src.application.reprocessing_service import reprocessar_incidente
from src.presentation.api.schemas import (
    IncidentResponse,
    ReprocessJobResponse,
    SettingsRequest,
    SettingsResponse,
    TagsRequest,
)
from src.infrastructure.persistence.settings_repository import SettingsStore

security = HTTPBasic(auto_error=False)


def _verify_credentials(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    configured_username = os.getenv("DASHBOARD_USERNAME")
    configured_password = os.getenv("DASHBOARD_PASSWORD")
    allow_anonymous = os.getenv("DASHBOARD_ALLOW_ANONYMOUS", "").lower() in {"1", "true", "yes"}

    if not configured_username or not configured_password:
        if allow_anonymous:
            return credentials.username if credentials else "anonymous"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dashboard credentials are not configured",
        )

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if not (
        secrets.compare_digest(credentials.username, configured_username)
        and secrets.compare_digest(credentials.password, configured_password)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return credentials.username


def _get_or_404(store: IncidentStore, incident_id: str) -> dict:
    try:
        return store.get_by_id(incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Incidente não encontrado") from exc


def create_app(
    *,
    store: Optional[IncidentStore] = None,
    settings_store: Optional[SettingsStore] = None,
):
    _db = os.getenv("INCIDENTS_DB", "data/incidents.db")
    app = FastAPI(title="Meet Operations Dashboard")
    incident_store = store or IncidentStore(_db)
    _settings = settings_store or SettingsStore(_db)
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    from src.shared.config import load_config, apply_db_settings
    _base_config = load_config()

    @app.get("/")
    def index(request: Request, _: str = Depends(_verify_credentials)):
        return FileResponse(_TEMPLATE_DIR + "/index.html")

    @app.get("/health")
    def health(_: str = Depends(_verify_credentials)):
        return {"status": "ok"}

    # ── Incidentes ────────────────────────────────────────────────────────

    @app.get("/incidents", response_model=List[IncidentResponse])
    def list_incidents(
        severity: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
        event_id: Optional[str] = Query(default=None),
        tag: Optional[str] = Query(default=None),
        include_resolved: bool = Query(default=True),
        _: str = Depends(_verify_credentials),
    ):
        rows = incident_store.list_incidents(
            include_resolved=include_resolved,
            severity=severity,
            status=status,
            event_id=event_id,
            tag=tag,
        )
        return [IncidentResponse.from_dict(r) for r in rows]

    @app.get("/incidents/open", response_model=List[IncidentResponse])
    def list_open_incidents(_: str = Depends(_verify_credentials)):
        return [IncidentResponse.from_dict(r) for r in incident_store.list_open_incidents()]

    @app.get("/incidents/{incident_id}", response_model=IncidentResponse)
    def get_incident(incident_id: str, _: str = Depends(_verify_credentials)):
        return IncidentResponse.from_dict(_get_or_404(incident_store, incident_id))

    @app.post("/incidents/{incident_id}/reprocess", response_model=IncidentResponse)
    def reprocess_incident(
        incident_id: str,
        background_tasks: BackgroundTasks,
        _: str = Depends(_verify_credentials),
    ):
        incident = _get_or_404(incident_store, incident_id)
        event_id = incident.get("event_id")
        if event_id:
            current_config = apply_db_settings(_base_config, _settings.get_all())
            background_tasks.add_task(
                reprocessar_incidente,
                incident_id=incident_id,
                event_id=event_id,
                db_path=_db,
                credentials_path=_base_config.credentials_path,
                token_path=_base_config.token_path,
                config=current_config,
            )
        return IncidentResponse.from_dict(incident)

    @app.post("/incidents/{incident_id}/reopen")
    def reopen_incident(incident_id: str, _: str = Depends(_verify_credentials)):
        _get_or_404(incident_store, incident_id)
        updated = incident_store.reopen_incident(incident_id)
        return {"id": updated["id"], "status": updated["status"]}

    @app.post("/incidents/{incident_id}/resolve")
    @app.post("/incidents/{incident_id}/close")
    def resolve_incident(incident_id: str, _: str = Depends(_verify_credentials)):
        _get_or_404(incident_store, incident_id)
        updated = incident_store.resolve_incident(incident_id)
        return {
            "id": updated["id"],
            "status": updated["status"],
            "resolved_at": updated["resolved_at"],
            "summary": updated["summary"],
        }

    @app.post("/incidents/{incident_id}/tags")
    def add_tags(
        incident_id: str,
        body: TagsRequest,
        _: str = Depends(_verify_credentials),
    ):
        _get_or_404(incident_store, incident_id)
        updated = incident_store.add_tags(incident_id, body.tags)
        return {"id": updated["id"], "tags": updated["metadata"].get("tags", [])}

    # ── Reprocessamento ───────────────────────────────────────────────────

    @app.get("/reprocess-jobs", response_model=List[ReprocessJobResponse])
    def list_reprocess_jobs(
        job_status: Optional[str] = Query(default=None, alias="status"),
        _: str = Depends(_verify_credentials),
    ):
        return incident_store.list_reprocess_jobs(status=job_status)

    # ── Disparo manual do bot ─────────────────────────────────────────────

    _bot_state: dict = {"status": "idle", "message": "Aguardando disparo.", "last_run": None}
    _bot_lock = threading.Lock()

    @app.post("/run")
    def rodar_agora(_: str = Depends(_verify_credentials)):
        if not _bot_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Bot já está rodando.")

        def _executar():
            try:
                _bot_state["status"] = "running"
                _bot_state["message"] = "Autenticando com o Google..."
                from src.infrastructure.google.auth import construir_servicos
                from src.shared.config import apply_db_settings
                config = apply_db_settings(_base_config, _settings.get_all())
                cal_svc, meet_svc, gmail_svc, _drive_svc = construir_servicos(
                    config.credentials_path, config.token_path
                )
                _bot_state["message"] = "Processando eventos do calendário..."
                from src.application.orchestrator import rodar_bot
                rodar_bot(cal_svc, meet_svc, gmail_svc, config)
                _bot_state["status"] = "done"
                _bot_state["message"] = "Concluído com sucesso."
            except Exception as exc:
                _bot_state["status"] = "error"
                _bot_state["message"] = str(exc)
            finally:
                _bot_state["last_run"] = datetime.now(timezone.utc).isoformat()
                _bot_lock.release()

        threading.Thread(target=_executar, daemon=True).start()
        return {"status": "started"}

    @app.get("/run/status")
    def status_bot(_: str = Depends(_verify_credentials)):
        return _bot_state

    # ── Stats ─────────────────────────────────────────────────────────────

    @app.get("/stats")
    def get_stats(_: str = Depends(_verify_credentials)):
        return incident_store.get_stats()

    # ── Configurações ──────────────────────────────────────────────────────

    @app.get("/config", response_model=SettingsResponse)
    def get_config(_: str = Depends(_verify_credentials)):
        return _settings.get_all()

    @app.post("/config", response_model=SettingsResponse)
    def save_config(body: SettingsRequest, _: str = Depends(_verify_credentials)):
        return _settings.set_all(body.model_dump())

    # ── Setup de credenciais Google ────────────────────────────────────────

    _oauth_state: dict = {}

    @app.get("/setup/status")
    def setup_status(_: str = Depends(_verify_credentials)):
        return {
            "credentials": os.path.exists(_base_config.credentials_path),
            "token": os.path.exists(_base_config.token_path),
        }

    @app.post("/setup/credentials")
    async def upload_credentials(
        file: UploadFile = File(...),
        _: str = Depends(_verify_credentials),
    ):
        content = await file.read()
        try:
            data = json.loads(content)
        except Exception:
            raise HTTPException(status_code=400, detail="Arquivo inválido: não é um JSON válido.")
        if "installed" not in data and "web" not in data:
            raise HTTPException(status_code=400, detail="Arquivo inválido: não parece um credentials.json do Google.")
        path = _base_config.credentials_path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return {"ok": True}

    @app.get("/setup/authorize")
    def setup_authorize(request: Request, _: str = Depends(_verify_credentials)):
        from google_auth_oauthlib.flow import Flow
        if not os.path.exists(_base_config.credentials_path):
            raise HTTPException(status_code=400, detail="credentials.json não encontrado.")
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        redirect_uri = str(request.base_url).rstrip("/") + "/setup/callback"
        flow = Flow.from_client_secrets_file(
            _base_config.credentials_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
        _oauth_state.update({"state": state, "redirect_uri": redirect_uri})
        return RedirectResponse(auth_url)

    @app.get("/setup/callback")
    def setup_callback(
        request: Request,
        code: Optional[str] = Query(default=None),
        state: Optional[str] = Query(default=None),
        error: Optional[str] = Query(default=None),
    ):
        if error:
            return RedirectResponse(f"/?setup_error={error}")
        stored_state = _oauth_state.get("state")
        redirect_uri = _oauth_state.get("redirect_uri")
        if not stored_state or state != stored_state:
            raise HTTPException(status_code=400, detail="Estado OAuth inválido ou sessão expirada.")
        from google_auth_oauthlib.flow import Flow
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        flow = Flow.from_client_secrets_file(
            _base_config.credentials_path,
            scopes=SCOPES,
            state=stored_state,
            redirect_uri=redirect_uri,
        )
        flow.fetch_token(authorization_response=str(request.url))
        creds = flow.credentials
        token_path = _base_config.token_path
        os.makedirs(os.path.dirname(os.path.abspath(token_path)), exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        _oauth_state.clear()
        return RedirectResponse("/")

    return app


app = create_app()
