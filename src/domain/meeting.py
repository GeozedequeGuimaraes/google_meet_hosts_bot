"""
Modelo de domínio para reuniões/eventos do Meet.

Representa um evento do Google Calendar que tem link de Meet e precisa
ser configurado pelo bot. Zero dependências externas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Attendee:
    email: str
    name: str
    is_organizer: bool = False

    @classmethod
    def from_dict(cls, d: Dict) -> "Attendee":
        email = (d.get("email") or "").strip()
        return cls(
            email=email,
            name=d.get("displayName") or (email.split("@")[0] if email else ""),
            is_organizer=bool(d.get("organizer")),
        )


@dataclass
class Meeting:
    event_id: str
    title: str
    meet_url: str
    calendar_color_id: Optional[str] = None
    attendees: List[Attendee] = field(default_factory=list)
    description: str = ""

    @property
    def guests(self) -> List[Attendee]:
        """Retorna apenas os convidados (exclui o organizador)."""
        return [a for a in self.attendees if not a.is_organizer]

    @property
    def meet_code(self) -> str:
        """Extrai o código da reunião da URL (ex: abc-defg-hij)."""
        return self.meet_url.rstrip("/").split("/")[-1]
