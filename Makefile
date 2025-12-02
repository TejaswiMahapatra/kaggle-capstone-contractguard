# ContractGuard AI - Makefile
# Common commands for development and deployment

.PHONY: help install dev run test lint format docker-build docker-up docker-down clean

# Default target
help:
	@echo "ContractGuard AI - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install       - Install dependencies"
	@echo "  make dev           - Run development server"
	@echo "  make run           - Start all services (Docker + API)"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linter"
	@echo "  make format        - Format code"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-up     - Start infrastructure services"
	@echo "  make docker-down   - Stop Docker services"
	@echo "  make docker-logs   - View Docker logs"
	@echo "  make docker-all    - Start all services including API"
	@echo "  make docker-tools  - Start with optional tools (pgAdmin, Redis Insight)"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate    - Run database migrations"
	@echo "  make db-upgrade    - Upgrade to latest migration"
	@echo "  make db-reset      - Reset database (DESTRUCTIVE)"
	@echo ""
	@echo "Testing:"
	@echo "  make test-quick    - Run quick evaluation suite"
	@echo "  make test-full     - Run full evaluation suite"
	@echo "  make health        - Check service health"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy        - Deploy to Cloud Run"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean         - Clean up generated files"
	@echo "  make shell         - Open Python shell"
	@echo "  make upload-sample - Upload sample contract"

# =============================================================================
# Development
# =============================================================================

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

run: docker-up
	@echo "Starting ContractGuard AI..."
	@echo "API will be available at http://localhost:8000"
	@echo "API docs at http://localhost:8000/docs"
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker build -t contractguard-ai:latest -f deploy/Dockerfile .

docker-up:
	docker-compose -f deploy/docker-compose.yml up -d weaviate redis minio postgres
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@echo "Infrastructure services started:"
	@echo "  - Weaviate:   http://localhost:8080"
	@echo "  - Redis:      localhost:6379"
	@echo "  - MinIO:      http://localhost:9000 (Console: http://localhost:9001)"
	@echo "  - PostgreSQL: localhost:5432"

docker-down:
	docker-compose -f deploy/docker-compose.yml down

docker-logs:
	docker-compose -f deploy/docker-compose.yml logs -f

docker-all:
	docker-compose -f deploy/docker-compose.yml up -d
	@echo ""
	@echo "All services started:"
	@echo "  - API:        http://localhost:8000"
	@echo "  - API Docs:   http://localhost:8000/docs"
	@echo "  - Weaviate:   http://localhost:8080"
	@echo "  - MinIO:      http://localhost:9001"
	@echo "  - PostgreSQL: localhost:5432"

docker-tools:
	docker-compose -f deploy/docker-compose.yml --profile tools up -d
	@echo ""
	@echo "All services with tools started:"
	@echo "  - pgAdmin:       http://localhost:5050 (admin@contractguard.ai / admin)"
	@echo "  - Redis Insight: http://localhost:8001"

# =============================================================================
# Deployment
# =============================================================================

deploy:
	gcloud builds submit --config=deploy/cloudbuild.yaml

deploy-local:
	@echo "Deploying to local Kubernetes..."
	kubectl apply -f deploy/k8s/

# =============================================================================
# Utilities
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/

shell:
	python -c "from src.agents import *; from src.services import *; import asyncio"

# =============================================================================
# Database
# =============================================================================

db-migrate:
	alembic revision --autogenerate -m "Auto migration"

db-upgrade:
	alembic upgrade head

db-reset:
	@echo "WARNING: This will delete all data in the database!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker-compose -f deploy/docker-compose.yml down -v postgres_data
	docker-compose -f deploy/docker-compose.yml up -d postgres
	@sleep 5
	alembic upgrade head

# =============================================================================
# Testing & Evaluation
# =============================================================================

test-quick:
	@echo "Running quick evaluation suite..."
	curl -X POST "http://localhost:8000/api/v1/evaluation/suite" \
		-H "Content-Type: application/json" \
		-d '{"suite_name": "quick"}'

test-full:
	@echo "Running full evaluation suite..."
	curl -X POST "http://localhost:8000/api/v1/evaluation/suite" \
		-H "Content-Type: application/json" \
		-d '{"suite_name": "standard"}'

health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API not responding"
	@echo ""
	@curl -s http://localhost:8080/v1/.well-known/ready && echo "Weaviate: OK" || echo "Weaviate: NOT READY"
	@docker compose -f deploy/docker-compose.yml exec -T redis redis-cli ping > /dev/null 2>&1 && echo "Redis: OK" || echo "Redis: NOT READY"

# =============================================================================
# Sample Data
# =============================================================================

upload-sample:
	@echo "Converting sample NDA to PDF..."
	python scripts/md_to_pdf.py examples/contracts/sample_nda.md examples/contracts/sample_nda.pdf
	@echo "Uploading sample NDA..."
	curl -X POST "http://localhost:8000/api/v1/documents/upload" \
		-F "file=@examples/contracts/sample_nda.pdf" \
		-F "collection_name=contracts"

# =============================================================================
# Quick Start
# =============================================================================

quickstart: install docker-up
	@echo ""
	@echo "============================================"
	@echo "ContractGuard AI is ready!"
	@echo "============================================"
	@echo ""
	@echo "1. Set your Google API key:"
	@echo "   export GOOGLE_API_KEY=your_key_here"
	@echo ""
	@echo "2. Start the API:"
	@echo "   make dev"
	@echo ""
	@echo "3. Open the docs:"
	@echo "   http://localhost:8000/docs"
	@echo ""
	@echo "4. Upload a sample contract:"
	@echo "   make upload-sample"
	@echo ""
	@echo "5. Test with a query:"
	@echo '   curl -X POST http://localhost:8000/api/v1/query \'
	@echo '     -H "Content-Type: application/json" \'
	@echo '     -d "{\"question\": \"What is the confidentiality period?\"}"'
	@echo ""
