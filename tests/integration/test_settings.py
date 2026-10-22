import pytest
from src.infrastructure.persistence.settings_repository import SettingsStore, DEFAULTS


@pytest.fixture
def store(tmp_path):
    return SettingsStore(str(tmp_path / "test.db"))


def test_get_all_retorna_defaults_quando_banco_vazio(store):
    settings = store.get_all()
    assert settings["schedule"] == []
    assert settings["timezone"] == "America/Recife"
    assert settings["days_ahead"] == 1
    assert settings["calendar_id"] == "primary"


def test_set_all_persiste_e_retorna_valores(store):
    result = store.set_all({"schedule": ["07:00", "18:00"], "days_ahead": 2})
    assert result["schedule"] == ["07:00", "18:00"]
    assert result["days_ahead"] == 2


def test_set_all_ignora_chaves_nao_editaveis(store):
    store.set_all({"credentials_path": "/hack", "schedule": ["10:00"]})
    settings = store.get_all()
    assert "credentials_path" not in settings
    assert settings["schedule"] == ["10:00"]


def test_set_all_sobrescreve_valor_existente(store):
    store.set_all({"discord_webhook_url": "https://old"})
    store.set_all({"discord_webhook_url": "https://new"})
    assert store.get_all()["discord_webhook_url"] == "https://new"


def test_defaults_completos(store):
    settings = store.get_all()
    for key in DEFAULTS:
        assert key in settings
