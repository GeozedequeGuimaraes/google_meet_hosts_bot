DB      ?= data/incidents.db
PORT    ?= 8765

.PHONY: install test dev bot verificar

install:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest tests/ -v

test-unit:
	.venv/bin/pytest tests/unit/ -v

test-integration:
	.venv/bin/pytest tests/integration/ -v

dev:
	DASHBOARD_ALLOW_ANONYMOUS=1 INCIDENTS_DB=$(DB) \
	.venv/bin/uvicorn src.presentation.dashboard:app --port $(PORT) --reload

bot:
	INCIDENTS_DB=$(DB) .venv/bin/python main.py

verificar:
	INCIDENTS_DB=$(DB) .venv/bin/python scripts/verificar_api.py
