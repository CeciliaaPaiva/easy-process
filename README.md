# Easy Process — Plataforma BPMN com IA

Plataforma SaaS B2B que transforma entrevistas em áudio em diagramas BPMN completos usando IA.

**Fluxo:** Upload de áudio → Transcrição (Gemini) → Geração de BPMN (Gemini) → Refinamento via chat

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/install/) v2+
- Chave da [Gemini API](https://aistudio.google.com/app/apikey) (para transcrição, geração de BPMN e chat)

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

## Login de teste

Após rodar `make seed` (passo 5 acima), os seguintes usuários ficam disponíveis para login em http://localhost:3000 — cada um em um tenant isolado:

| Empresa (tenant) | Email | Senha | Role |
|-------------------|-------|-------|------|
| Demo Corp | `admin@demo.com` | `demo123` | admin (+ platform admin) |
| Acme Inc | `user@acme.com` | `acme123` | analyst |

`admin@demo.com` também é **platform admin** (`is_platform_admin=True`), então é o único dos dois que enxerga a aba "Uso de IA" (restrita a admins da plataforma, não só admins do tenant — ver `CLAUDE.md`).

Credenciais definidas em [`scripts/seed.py`](./scripts/seed.py) — apenas para ambiente de desenvolvimento, nunca usar em produção.

> Já rodou `make seed` antes desta atualização? Rode `make seed` de novo — o script agora é idempotente também para `is_platform_admin` e atualiza o usuário existente.

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
| `GEMINI_API_KEY` | Chave da API do Gemini | — (obrigatório) |
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
│   │   ├── services/  # Lógica de negócio (transcrição, Gemini, BPMN)
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

| Sprint | Entregável | Status |
|--------|-----------|--------|
| Sprint 0 | Monorepo + Docker + estrutura + CI | ✅ Concluído |
| Sprint 1 | Autenticação JWT + multi-tenant | ✅ Concluído |
| Sprint 2 | Upload de áudio → transcrição → BPMN | ✅ Concluído |
| Sprint 3 | Visualizador BPMN + chat + exportação | ✅ Concluído |
| Sprint 4 | Documentação automática + deploy produção | ✅ Concluído |
| Sprint 5–8 | Hardening, correções e ajustes pós-MVP | ✅ Concluído |
| Sprint 9 | Migração da IA para Gemini (transcrição, geração, refino) | ✅ Concluído |
| Sprint 10 | Correções de modelagem BPMN (gateways combinados) | ✅ Concluído |
| Sprint 11 | Painel "Uso de IA" (custo por chamada, restrito a platform admin) | ✅ Concluído |
| Sprint 12 | Pipeline em estágios: análise separada da modelagem | ✅ Concluído |
| Sprint 13 | Edição manual do diagrama (kickoff) | 🔜 Próxima |

> Release notes detalhadas de cada sprint em [`docs/releases/`](./docs/releases/). Este roadmap é atualizado a cada entrega — ver a release mais recente para o resumo completo: [`RELEASE-S12.md`](./docs/releases/RELEASE-S12.md).

---

## Arquitetura

Ver [`arquitetura-mvp-bpmn-ai.md`](./arquitetura-mvp-bpmn-ai.md) para a documentação técnica completa.

Ver [`CLAUDE.md`](./CLAUDE.md) para guias de desenvolvimento e boas práticas.
