import json
import os
from typing import Any, Dict, Iterable, List

import requests


class NotificationChannel:
    def send(self, incident: Dict[str, Any]) -> bool:  # noqa: ARG002
        raise NotImplementedError


class EmailNotificationChannel(NotificationChannel):
    def __init__(self, gmail_service):
        self.gmail_service = gmail_service

    def send(self, incident: Dict[str, Any]) -> bool:
        if not self.gmail_service:
            return False
        try:
            email = incident.get("user_email") or os.getenv("NOTIFY_EMAIL", "")
            if not email:
                return False
            from src.infrastructure.google.gmail_gateway import _montar_mensagem

            subject = f"[Meet Bot] {incident['type']}"
            body = (
                f"Resumo: {incident.get('summary', '')}\n\n"
                f"Evento: {incident.get('event_id', '')}\n"
                f"Severidade: {incident.get('severity', '')}\n"
                f"Status: {incident.get('status', '')}\n"
            )
            payload = _montar_mensagem(email, subject, body)
            self.gmail_service.users().messages().send(userId="me", body=payload).execute()
            return True
        except Exception:
            return False


class WebhookNotificationChannel(NotificationChannel):
    def __init__(self, url: str):
        self.url = url

    def send(self, incident: Dict[str, Any]) -> bool:
        if not self.url:
            return False
        try:
            response = requests.post(
                self.url,
                data=json.dumps(incident),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return response.status_code in (200, 201, 202, 204)
        except Exception:
            return False


class GoogleChatNotificationChannel(NotificationChannel):
    def __init__(self, url: str):
        self.url = url

    @staticmethod
    def build_payload(incident: Dict[str, Any]) -> Dict[str, Any]:
        text = (
            f"⚠️ *{incident.get('type', 'INCIDENTE')}*\n"
            f"Severidade: {incident.get('severity', 'warning')}\n"
            f"Resumo: {incident.get('summary', '')}\n"
            f"Evento: {incident.get('event_id', '')}\n"
            f"Status: {incident.get('status', 'open')}"
        )
        return {"text": text}

    def send(self, incident: Dict[str, Any]) -> bool:
        if not self.url:
            return False
        try:
            response = requests.post(
                self.url,
                data=json.dumps(self.build_payload(incident)),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return response.status_code in (200, 201, 202, 204)
        except Exception:
            return False


class DiscordNotificationChannel(NotificationChannel):
    def __init__(self, url: str):
        self.url = url

    @staticmethod
    def build_payload(incident: Dict[str, Any]) -> Dict[str, Any]:
        icon = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "critical": "🛑"}.get(
            incident.get("severity", "warning"), "⚠️"
        )
        incident_type = incident.get("type", "")
        fields = [
            {"name": "Encontro", "value": incident.get("event_id", "-"), "inline": True},
            {"name": "Severidade", "value": incident.get("severity", "-"), "inline": True},
        ]

        if incident_type == "COHOST_ASSIGNMENT_FAILED":
            email = incident.get("user_email", "-")
            fields.append({
                "name": "E-mail externo",
                "value": f"`{email}`",
                "inline": False,
            })
            fields.append({
                "name": "O que fazer",
                "value": "Entre em contato com o professor e peça um e-mail Gmail ou Google Workspace. Após a troca, clique **Reprocessar** no dashboard.",
                "inline": False,
            })
            color = 16753920  # laranja
        elif incident_type == "MEET_SPACE_CONFIG_FAILED":
            fields.append({
                "name": "O que fazer",
                "value": "Verifique a reunião no Google Meet. Se o erro persistir, clique **Reprocessar** no dashboard.",
                "inline": False,
            })
            color = 15158332  # vermelho
        else:
            color = 15158332

        return {
            "content": f"{icon} **Atenção, equipe V-Lab**",
            "embeds": [
                {
                    "title": incident.get("summary", "Incidente sem resumo"),
                    "color": color,
                    "fields": fields,
                }
            ],
        }

    def send(self, incident: Dict[str, Any]) -> bool:
        if not self.url:
            return False
        try:
            response = requests.post(
                self.url,
                data=json.dumps(self.build_payload(incident)),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return response.status_code in (200, 201, 202, 204)
        except Exception:
            return False


class NotificationRouter:
    def __init__(self, channels: Iterable[NotificationChannel]):
        self.channels = list(channels)

    def send(self, incident: Dict[str, Any]) -> List[bool]:
        return [channel.send(incident) for channel in self.channels]
