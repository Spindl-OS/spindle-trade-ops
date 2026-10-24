.PHONY: install lint fmt type test check api

ENGINE ?= ../spindle-agents-bootstrap

install:          ## Sync deps (engine from ../spindle-agents-bootstrap, editable) into .venv
	uv sync --all-extras

lint:             ## Ruff lint
	uv run ruff check .

fmt:              ## Ruff format
	uv run ruff format .

type:             ## mypy strict
	uv run mypy src

test:             ## pytest
	uv run pytest -q

check: lint type test  ## Everything CI runs

api:              ## Run the engine API WITH this module installed (reads the engine's .env)
	cd $(ENGINE) && uv run --project $(CURDIR) uvicorn spindle_agents.api.main:app --reload --port 8000
