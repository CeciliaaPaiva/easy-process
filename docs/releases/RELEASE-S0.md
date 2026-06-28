# Release Sprint 0 — Foundation e Setup

**Data:** 2026-06-28
**Sprint:** S0
**Status:** Concluído

---

## Resumo

Sprint de fundação do projeto Easy Process. Toda a infraestrutura de desenvolvimento foi configurada: monorepo organizado, Docker Compose com os três serviços (frontend, backend, banco), aplicação FastAPI funcional com endpoint de saúde, estrutura Next.js pronta, pipeline de migrations com Alembic e CI com GitHub Actions.

---

## Funcionalidades entregues

### Infraestrutura
- **[S0-01]** Monorepo criado com estrutura completa de diretórios — `frontend/`, `backend/`, `docs/`, `scripts/`, `.github/`
- **[S0-02]** Docker Compose configurado com 3 serviços (`frontend`, `backend`, `db`) — hot reload por volumes, health check no banco, rede interna nomeada
- **[S0-06]** Makefile com atalhos de desenvolvimento — `make up`, `make test`, `make lint`, `make migrate`, `make migration`, `make seed`, `make shell-backend`, `make shell-db`, `make reset-db`

### Backend (FastAPI)
- **[S0-03]** Setup completo do FastAPI com estrutura limpa:
  - `app/main.py` — App factory com CORS middleware
  - `app/core/config.py` — Pydantic Settings carregando variáveis do `.env`
  - `app/core/database.py` — SQLAlchemy async engine + `Base` para os models
  - `app/core/security.py` — placeholder para Sprint 1
  - `app/api/v1/health.py` — `GET /api/v1/health → {"status": "ok"}`
  - `app/models/`, `app/schemas/`, `app/services/`, `app/workers/` — estrutura pronta para as próximas sprints
- **[S0-05]** Alembic configurado com `alembic.ini` + `env.py` async (suporte a PostgreSQL async via `asyncpg`) — URL lida dinamicamente via `pydantic-settings`
- Ferramentas de qualidade configuradas: **Ruff**, **Black**, **mypy**, **pytest-asyncio**

### Frontend (Next.js)
- **[S0-04]** Setup Next.js 14 com App Router + TypeScript strict:
  - `src/app/layout.tsx` — Layout raiz com metadata PT-BR
  - `src/app/page.tsx` — Landing page com link para `/login`
  - `src/app/(auth)/login/page.tsx` — placeholder da página de login
  - `src/lib/api.ts` — cliente HTTP centralizado com injeção de token Bearer
  - `src/lib/utils.ts` — helper `cn()` (clsx + tailwind-merge)
  - `src/types/index.ts` — tipagens completas do domínio (User, Tenant, Project, Process, ChatMessage, etc.)
- Tailwind CSS + Prettier + ESLint configurados

### Documentação e CI
- **[S0-07]** README completo com pré-requisitos, como rodar, tabela de comandos, estrutura e roadmap
- `.env.example` documentado com todas as variáveis
- `.gitignore` cobrindo Python, Node.js e Docker
- **GitHub Actions** (`ci.yml`) — lint + testes do backend a cada push em `develop`/`main`; E2E (Playwright) no merge para `main`

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Pontos planejados | 16 |
| Pontos entregues | 16 |
| Testes passando | 2/2 |
| Lint (Ruff + Black) | ✅ zero erros |
| Cobertura de testes | N/A (Sprint 0 — apenas health check) |

---

## O que ficou para a próxima sprint

Nada. Todos os 7 itens da Sprint 0 foram entregues conforme o critério de aceite.

---

## Decisões técnicas tomadas nesta sprint

| Decisão | Justificativa |
|---------|--------------|
| `setuptools.build_meta` em vez de `setuptools.backends.legacy:build` | Compatibilidade com versão do setuptools disponível no ambiente (< 68.5) |
| `known-first-party = ["app"]` no Ruff | Separação correta de imports stdlib / third-party / first-party no isort |
| SQLite como banco de teste local | Permite rodar testes sem PostgreSQL no ambiente de desenvolvimento local; CI usa PostgreSQL real |
| Docker Compose sem `version:` field | Campo `version` é obsoleto no Compose v2+ |

---

## Como testar esta release

```bash
# 1. Clone e configure
git clone <repo>
cd easy-process
cp .env.example .env

# 2. Suba os serviços
make up

# 3. Verifique os serviços
curl http://localhost:8000/api/v1/health
# → {"status": "ok"}

# 4. Acesse o frontend
# Abrir http://localhost:3000 no browser

# 5. Acesse a documentação da API
# Abrir http://localhost:8000/docs no browser

# 6. Rode os testes (dentro do container)
make test

# 7. Aplique migrations (valida setup do Alembic)
make migrate
```

---

## Bugs conhecidos

Nenhum.

---

## Próxima sprint

**Sprint 1 — Autenticação e Multi-tenant**
- Models Tenant e User com migration Alembic
- JWT (access token 30min + refresh token 7 dias) com bcrypt
- Endpoints: `POST /register`, `POST /login`, `POST /refresh`, `GET /me`
- Middleware de isolamento por `tenant_id`
- Frontend: páginas de login e registro com shadcn/ui
- Frontend: layout autenticado com sidebar
- Seed script com dados de desenvolvimento
