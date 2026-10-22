from src.shared.notifications import DiscordNotificationChannel, GoogleChatNotificationChannel


def test_google_chat_payload_includes_summary_and_severity():
    incident = {
        "type": "COHOST_ASSIGNMENT_FAILED",
        "severity": "warning",
        "summary": "Não foi possível adicionar usuário como coorganizador",
        "event_id": "evt-42",
        "status": "open",
        "user_email": "joao@example.com",
    }

    payload = GoogleChatNotificationChannel.build_payload(incident)
    assert "COHOST_ASSIGNMENT_FAILED" in payload["text"]
    assert "evt-42" in payload["text"]
    assert "warning" in payload["text"]


def test_discord_payload_includes_embed_fields_and_message():
    incident = {
        "type": "MEET_SPACE_CONFIG_FAILED",
        "severity": "error",
        "summary": "Configuração do espaço falhou",
        "event_id": "evt-99",
        "status": "open",
        "user_email": "maria@example.com",
    }

    payload = DiscordNotificationChannel.build_payload(incident)
    assert payload["content"] == "🚨 **Atenção, equipe V-Lab**"
    assert payload["embeds"][0]["fields"][0]["name"] == "Encontro"
    assert payload["embeds"][0]["fields"][0]["value"] == "evt-99"
