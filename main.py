"""
Ponto de entrada do bot.

Autentica uma vez com o Google, depois delega ao orquestrador.
Se `config.schedule` estiver preenchido, vira serviço contínuo via APScheduler;
caso contrário executa uma vez e encerra.
"""

from src.shared.config import apply_db_settings, load_config
from src.shared.logging import configurar_logging
from src.infrastructure.google.auth import construir_servicos
from src.application.orchestrator import rodar_bot
from src.application.recording_service import rodar_gravacoes
from src.infrastructure.persistence.settings_repository import SettingsStore


def main():
    config = load_config()
    logger = configurar_logging(config.log_level)
    settings_store = SettingsStore(config.incidents_db_path)

    logger.info("Autenticando com o Google (Calendar, Meet, Gmail e Drive)...")
    calendar_service, meet_service, gmail_service, drive_service = construir_servicos(
        config.credentials_path, config.token_path
    )
    logger.info("Autenticado com sucesso.")

    def executar():
        current_config = apply_db_settings(config, settings_store.get_all())
        rodar_bot(calendar_service, meet_service, gmail_service, current_config)

    def executar_gravacoes():
        current_config = apply_db_settings(config, settings_store.get_all())
        rodar_gravacoes(drive_service, gmail_service, current_config)

    startup_settings = settings_store.get_all()
    schedule = startup_settings.get("schedule") or config.schedule
    recording_schedule = startup_settings.get("recording_schedule") or config.recording_schedule
    timezone = startup_settings.get("timezone") or config.timezone

    jobs = []
    if schedule:
        jobs.append((schedule, executar, "principal"))
    if recording_schedule:
        jobs.append((recording_schedule, executar_gravacoes, "gravacoes"))

    if jobs:
        from src.shared.scheduler import iniciar_agendador
        logger.info("Modo agendado. Alteracoes no dashboard entram em vigor apos reiniciar o bot.")
        iniciar_agendador(jobs, timezone=timezone)
    else:
        logger.info("Modo avulso: executando uma vez.")
        executar()


if __name__ == "__main__":
    main()
