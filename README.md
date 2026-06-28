# Easy Process — Plataforma BPMN com IA

Plataforma SaaS B2B que transforma entrevistas em áudio em diagramas BPMN completos usando IA.

**Fluxo:** Upload de áudio → Transcrição (Whisper) → Geração de BPMN (Claude API) → Refinamento via chat

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/install/) v2+
- Chave da [Anthropic API](https://console.anthropic.com/) (para geração de BPMN)

---

## Como rodar

```bash
# 1. Clone o repositório
git clone <url-do-repo>
cd easy-process

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env e preencha ANTHROPIC_API_KEY

# 3. Suba todos os serviços
make up

# 4. Aplique as migrations do banco
make migrate

# 5. (Opcional) Popule com dados de desenvolvimento
make seed
```

Serviços disponíveis:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **Swagger (docs):** http://localhost:8000/docs
- **Banco PostgreSQL:** localhost:5432

---

## Comandos úteis

| Comando | Descrição |
|---------|-----------|
| `make up` | Sobe todos os serviços em background |
| `make down` | Para todos os serviços |
| `make logs` | Acompanha logs em tempo real |
| `make test` | Roda a suite de testes do backend |
| `make test-cov` | Testes com relatório de cobertura |
| `make lint` | Linting completo do backend (Ruff + Black + mypy) |
| `make lint-frontend` | Linting do frontend (ESLint) |
| `make migrate` | Aplica migrations pendentes |
| `make migration MSG="desc"` | Cria nova migration |
| `make seed` | Popula banco com dados de dev |
| `make shell-backend` | Shell bash no container backend |
| `make shell-db` | psql no container do banco |
| `make reset-db` | Apaga e recria o banco (⚠️ destrutivo) |

---

## Como rodar os testes

```bash
# Todos os testes
make test

# Com cobertura (mínimo 80%)
make test-cov

# Relatório HTML de cobertura
make test-cov-html
# Abre backend/htmlcov/index.html no browser
```

---

## Variáveis de ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `DATABASE_URL` | URL de conexão com PostgreSQL | `postgresql+asyncpg://user:pass@db:5432/bpmn_platform` |
| `JWT_SECRET` | Chave secreta para assinar tokens JWT | — (obrigatório) |
| `ANTHROPIC_API_KEY` | Chave da API da Anthropic | — (obrigatório) |
| `WHISPER_MODEL` | Modelo Whisper (`tiny`, `base`, `small`) | `base` |
| `UPLOAD_DIR` | Diretório de uploads de áudio | `/data/uploads` |
| `MAX_UPLOAD_SIZE_MB` | Tamanho máximo do áudio em MB | `100` |
| `CORS_ORIGINS` | Origens permitidas pelo CORS | `["http://localhost:3000"]` |
| `ENVIRONMENT` | Ambiente (`development`, `production`) | `development` |

---

## Estrutura do projeto

```
easy-process/
├── frontend/          # Next.js 14 + TypeScript + Tailwind
├── backend/           # FastAPI + Python 3.11 + SQLAlchemy
│   ├── app/
│   │   ├── core/      # config, database, security
│   │   ├── models/    # SQLAlchemy ORM
│   │   ├── schemas/   # Pydantic request/response
│   │   ├── api/v1/    # Endpoints
│   │   ├── services/  # Lógica de negócio (Whisper, Claude, BPMN)
│   │   └── workers/   # Pipeline assíncrono
│   ├── alembic/       # Migrations versionadas
│   └── tests/         # pytest (unit, integration, e2e)
├── docs/releases/     # Release notes por sprint
├── scripts/           # seed.py e utilitários
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Roadmap

| Sprint | Semanas | Entregável |
|--------|---------|-----------|
| ✅ Sprint 0 | 1-2 | Monorepo + Docker + estrutura + CI |
| Sprint 1 | 3-4 | Autenticação JWT + multi-tenant |
| Sprint 2 | 5-6 | Upload de áudio → transcrição → BPMN |
| Sprint 3 | 7-8 | Visualizador BPMN + chat + exportação |
| Sprint 4 | 9-10 | Documentação automática + deploy produção |

---

## Arquitetura

Ver [`arquitetura-mvp-bpmn-ai.md`](./arquitetura-mvp-bpmn-ai.md) para a documentação técnica completa.

Ver [`CLAUDE.md`](./CLAUDE.md) para guias de desenvolvimento e boas práticas.
