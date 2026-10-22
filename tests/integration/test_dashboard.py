import os

from fastapi.testclient import TestClient

from src.presentation.dashboard import create_app
from src.application.incident_service import IncidentStore, create_incident


def test_dashboard_lists_incidents_and_reprocesses_manual():
    os.environ["DASHBOARD_ALLOW_ANONYMOUS"] = "true"
    db_path = os.path.join(os.getcwd(), "test_dashboard_incidents.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    store = IncidentStore(db_path)
    incident = create_incident(
        store=store,
        event_id="evt-dashboard",
        incident_type="COHOST_ASSIGNMENT_FAILED",
        summary="Falha ao adicionar usuário",
        severity="warning",
        user_email="joao@example.com",
    )

    app = create_app(store=store)
    client = TestClient(app)

    response = client.get("/incidents")
    assert response.status_code == 200
    data = response.json()
    assert any(item["id"] == incident["id"] for item in data)

    reprocess = client.post(f"/incidents/{incident['id']}/reprocess")
    assert reprocess.status_code == 200
    payload = reprocess.json()
    assert payload["status"] == "reprocessing"
    assert payload["metadata"]["reprocess_requested"] is True

    jobs = client.get("/reprocess-jobs")
    assert jobs.status_code == 200
    assert jobs.json()[0]["incident_id"] == incident["id"]

    os.remove(db_path)
    os.environ.pop("DASHBOARD_ALLOW_ANONYMOUS", None)


def test_dashboard_requires_auth_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHBOARD_ALLOW_ANONYMOUS", raising=False)
    monkeypatch.delenv("DASHBOARD_USERNAME", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)

    app = create_app(store=IncidentStore(str(tmp_path / "incidents.db")))
    client = TestClient(app)

    response = client.get("/incidents")
    assert response.status_code == 401


def test_dashboard_accepts_configured_basic_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("DASHBOARD_USERNAME", "vlab")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")
    monkeypatch.delenv("DASHBOARD_ALLOW_ANONYMOUS", raising=False)

    app = create_app(store=IncidentStore(str(tmp_path / "incidents.db")))
    client = TestClient(app)

    assert client.get("/incidents").status_code == 401
    assert client.get("/incidents", auth=("vlab", "secret")).status_code == 200


def test_dashboard_template_uses_safe_dom_methods():
    template_path = os.path.join(os.getcwd(), "src", "presentation", "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as file:
        html = file.read()

    # Dados dinâmicos de incidentes devem usar textContent (não innerHTML)
    assert "textContent" in html
    # innerHTML só deve ser usado para SVG estático de ícones, não para dados do usuário
    if "innerHTML" in html:
        inner_uses = [part.strip()[:60] for part in html.split("innerHTML")[1:]]
        for use in inner_uses:
            assert "item." not in use, f"innerHTML usado com dado dinâmico: {use}"
