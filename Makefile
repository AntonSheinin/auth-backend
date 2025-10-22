.PHONY: help install dev clean test lint format run docker-build docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies with uv"
	@echo "  make dev          - Install development dependencies with uv"
	@echo "  make clean        - Remove cache and build artifacts"
	@echo "  make test         - Run tests with pytest"
	@echo "  make lint         - Run ruff linter"
	@echo "  make format       - Format code with ruff"
	@echo "  make run          - Run the application locally"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"
	pre-commit install

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

test:
	pytest -v --cov=app --cov-report=term-missing

lint:
	ruff check app/
	mypy app/

format:
	ruff format app/
	ruff check --fix app/

run:
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f
