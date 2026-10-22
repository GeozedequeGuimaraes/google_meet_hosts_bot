import logging
from typing import Callable, List, Tuple

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    class BlockingScheduler:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise RuntimeError("APScheduler não está instalado. Rode: pip install -r requirements.txt")

    class CronTrigger:  # type: ignore[no-redef]
        def __init__(self, *, hour: int, minute: int, timezone: str):
            self.hour = hour
            self.minute = minute
            self.timezone = timezone

logger = logging.getLogger(__name__)

# (horarios, função, nome legível para logs)
JobSpec = Tuple[List[str], Callable, str]


def _parse_horario(horario: str) -> tuple[int, int]:
    partes = horario.split(":")
    if len(partes) != 2:
        raise ValueError(f"Horário inválido: {horario}")
    hora, minuto = int(partes[0]), int(partes[1])
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        raise ValueError(f"Horário inválido: {horario}")
    return hora, minuto


def iniciar_agendador(jobs: List[JobSpec], timezone: str = "America/Recife") -> None:
    """Agenda múltiplos jobs e bloqueia até encerramento.

    Cada JobSpec é (horarios, fn, nome). Executa todos os jobs imediatamente
    na inicialização para não perder eventos criados antes do primeiro ciclo.
    """
    scheduler = BlockingScheduler(timezone=timezone)

    for horarios, job_fn, nome in jobs:
        for horario in horarios:
            hora, minuto = _parse_horario(horario)
            scheduler.add_job(
                job_fn,
                CronTrigger(hour=hora, minute=minuto, timezone=timezone),
                name=f"{nome}_{horario}",
                misfire_grace_time=300,
            )
            logger.info("Agendado '%s' para às %s (%s)", nome, horario, timezone)

    logger.info("Executando ciclos iniciais antes de iniciar o agendador...")
    for _horarios, job_fn, nome in jobs:
        try:
            job_fn()
        except Exception as e:
            logger.error("Erro no ciclo inicial de '%s': %s", nome, e)

    logger.info("Agendador ativo.")
    scheduler.start()
