.PHONY: up down build logs restart \
        test test-cov test-cov-html \
        lint lint-frontend lint-fix \
        migrate migration seed \
        shell-backend shell-db \
        reset-db \
        deploy deploy-migrate \
        prod-up prod-down prod-logs prod-migrate prod-shell-db

# ─── Serviços ──────────────────────────────────────────────────────────────────

up:
	docker compose up -d

ollama-pull:
	docker compose exec ollama ollama pull qwen2.5:14b

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

restart:
	docker compose restart

# ─── Testes ───────────────────────────────────────────────────────────────────

test:
	docker compose exec backend pytest -v

test-cov:
	docker compose exec backend pytest --cov=app --cov-report=term-missing --cov-fail-under=80

test-cov-html:
	docker compose exec backend pytest --cov=app --cov-report=html
	@echo "Relatório em backend/htmlcov/index.html"

# ─── Lint ─────────────────────────────────────────────────────────────────────

lint:
	docker compose exec backend ruff check .
	docker compose exec backend black --check .
	docker compose exec backend mypy app/

lint-fix:
	docker compose exec backend ruff check . --fix
	docker compose exec backend black .

lint-frontend:
	docker compose exec frontend npm run lint

# ─── Banco de dados ───────────────────────────────────────────────────────────

migrate:
	docker compose exec backend alembic upgrade head

# Uso: make migration MSG="create users table"
migration:
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

seed:
	docker compose exec backend python scripts/seed.py

reset-db:
	@echo "⚠️  Isso vai apagar todos os dados do banco. Confirme com Ctrl+C para cancelar."
	@sleep 3
	docker compose down -v
	docker compose up -d db
	@echo "Aguardando banco subir..."
	@sleep 5
	$(MAKE) migrate

# ─── Deploy (produção) ────────────────────────────────────────────────────────

deploy:
	@echo "Subindo em produção..."
	docker compose -f docker-compose.prod.yml --env-file .env.production pull
	docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
	docker compose -f docker-compose.prod.yml --env-file .env.production exec backend alembic upgrade head
	@echo "Deploy concluído. Verificando saúde..."
	@sleep 5
	docker compose -f docker-compose.prod.yml --env-file .env.production ps

deploy-migrate:
	docker compose -f docker-compose.prod.yml --env-file .env.production exec backend alembic upgrade head

# Operação do dia a dia da stack de produção (sem rebuild — use "deploy" pra isso)
prod-up:
	docker compose -f docker-compose.prod.yml --env-file .env.production up -d

prod-down:
	docker compose -f docker-compose.prod.yml --env-file .env.production down

prod-logs:
	docker compose -f docker-compose.prod.yml --env-file .env.production logs -f

prod-migrate:
	docker compose -f docker-compose.prod.yml --env-file .env.production exec backend alembic upgrade head

prod-shell-db:
	docker compose -f docker-compose.prod.yml --env-file .env.production exec db psql -U $${DB_USER:-easy_process_prod} -d $${DB_NAME:-easy_process_prod}

# ─── Shells ───────────────────────────────────────────────────────────────────

shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec db psql -U user -d bpmn_platform
