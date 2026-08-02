.PHONY: install run test lint format eval docker

install:
	python -m pip install -e ".[dev]"

run:
	uvicorn resolveai.api.main:app --reload

test:
	pytest --cov=resolveai --cov-report=term-missing

lint:
	ruff check .
	mypy src

format:
	ruff format .

eval:
	python -m evals.run_evals

docker:
	docker compose up --build
