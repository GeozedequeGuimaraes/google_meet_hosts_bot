from unittest.mock import MagicMock, patch
from src.shared.scheduler import iniciar_agendador


def test_scheduler_executa_ciclo_inicial_e_agenda_jobs():
    job_fn = MagicMock()

    scheduler_mock = MagicMock()
    with patch("src.shared.scheduler.BlockingScheduler", return_value=scheduler_mock):
        scheduler_mock.start.side_effect = KeyboardInterrupt
        try:
            iniciar_agendador(["07:00", "18:00"], job_fn, timezone="America/Recife")
        except KeyboardInterrupt:
            pass

    job_fn.assert_called_once()
    assert scheduler_mock.add_job.call_count == 2


def test_scheduler_horario_invalido_levanta_erro():
    import pytest
    with pytest.raises(ValueError):
        iniciar_agendador(["25:00"], lambda: None)
