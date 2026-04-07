PYTHON := .venv/bin/python
STREAMLIT := .venv/bin/streamlit
UVICORN := .venv/bin/uvicorn

.PHONY: test daily weekly dashboard api bootstrap

bootstrap:
	bash scripts/bootstrap_local.sh

test:
	$(PYTHON) -m pytest

daily:
	$(PYTHON) -m src.main --mode daily --project-root $(CURDIR)

weekly:
	$(PYTHON) -m src.main --mode weekly --project-root $(CURDIR)

dashboard:
	$(STREAMLIT) run app/dashboard.py

api:
	$(UVICORN) app_api.main:app --reload
