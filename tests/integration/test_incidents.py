import os

from src.application.incident_service import IncidentStore, create_incident


def test_incident_is_deduplicated(tmp_path):
    db_path = tmp_path / "incidents.db"
    store = IncidentStore(str(db_path))

    incident_a = create_incident(
        store=store,
        event_id="evt-1",
        incident_type="COHOST_ASSIGNMENT_FAILED",
        summary="Não foi possível adicionar usuário",
        severity="warning",
        user_email="joao@example.com",
    )
    incident_b = create_incident(
        store=store,
        event_id="evt-1",
        incident_type="COHOST_ASSIGNMENT_FAILED",
        summary="Não foi possível adicionar usuário",
        severity="warning",
        user_email="joao@example.com",
    )

    assert incident_a["id"] == incident_b["id"]
    assert incident_b["retries"] >= 1
    assert len(store.list_open_incidents()) == 1


def test_incident_keeps_metadata():
    db_path = tmp_path = os.path.join(os.getcwd(), "test_incidents_metadata.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    store = IncidentStore(db_path)
    incident = create_incident(
        store=store,
        event_id="evt-2",
        incident_type="MEET_SPACE_CONFIG_FAILED",
        summary="Configuração do espaço falhou",
        severity="error",
        metadata={"meeting": "Aula de Matemática", "reason": "permission_error"},
    )

    assert incident["metadata"]["meeting"] == "Aula de Matemática"
    assert incident["metadata"]["reason"] == "permission_error"
    os.remove(db_path)


def test_incident_can_be_marked_for_manual_reprocess():
    db_path = os.path.join(os.getcwd(), "test_incidents_reprocess.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    store = IncidentStore(db_path)
    incident = create_incident(
        store=store,
        event_id="evt-3",
        incident_type="COHOST_ASSIGNMENT_FAILED",
        summary="Falha ao adicionar usuário",
        severity="warning",
        user_email="ana@example.com",
    )

    updated = store.request_manual_reprocess(incident["id"])
    assert updated["status"] == "reprocessing"
    assert updated["metadata"]["reprocess_requested"] is True
    assert updated["metadata"]["reprocess_jobs"]

    jobs = store.list_reprocess_jobs()
    assert len(jobs) == 1
    assert jobs[0]["incident_id"] == incident["id"]
    assert jobs[0]["status"] == "queued"

    listed = store.list_incidents(include_resolved=True)
    assert any(item["id"] == incident["id"] for item in listed)
    os.remove(db_path)
