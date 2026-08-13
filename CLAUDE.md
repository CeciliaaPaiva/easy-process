# CLAUDE.md — Plataforma BPMN com IA (Easy Process)

> Guia técnico completo para desenvolvimento com Claude Code.
> Leia este documento antes de iniciar qualquer tarefa no projeto.

---

## Visão geral do produto

**Easy Process** é uma plataforma SaaS B2B que transforma entrevistas em áudio em diagramas BPMN completos usando IA. O fluxo principal é: upload de áudio → transcrição (Gemini) → geração de BPMN (Gemini) → refinamento via chat.

**Público-alvo:** Analistas de negócio que precisam acelerar a fase de modelagem de processos.

**Proposta de valor:**
- Upload de áudio → BPMN pronto em minutos
- Refinamento via chat em linguagem natural (sem precisar saber BPMN)
- Exportação para Camunda Modeler / qualquer ferramenta BPMN
- Multi-tenant: cada empresa completamente isolada

---

## Stack tecnológica

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Frontend | Next.js (App Router) + TypeScript | 14+ |
| Visualizador BPMN | bpmn-js (Camunda open-source) | latest |
| Backend / API | FastAPI | Python 3.11+ |
| Transcrição | Google Gemini API (`GEMINI_MODEL_TRANSCRIPTION`) | - |
| Geração BPMN | Google Gemini API (`GEMINI_MODEL_GENERATION`) | gemini-3.1-flash-lite |
| Banco de dados | PostgreSQL | 16 |
| ORM | SQLAlchemy (async) + Alembic | - |
| Armazenamento | Filesystem local (→ S3 no futuro) | - |
| Containerização | Docker + Docker Compose | - |
| Autenticação | JWT (python-jose) + bcrypt (passlib) | - |
| Estilização | Tailwind CSS + shadcn/ui | - |

---

## Estrutura do repositório

```
bpmn-ai-platform/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── app/
│       │   ├── (auth)/login/
│       │   ├── (auth)/register/
│       │   └── (dashboard)/projects/[id]/
│       ├── components/
│       │   ├── bpmn/         # BpmnViewer.tsx, BpmnToolbar.tsx
│       │   ├── chat/         # ChatWindow.tsx, ChatMessage.tsx
│       │   └── upload/       # AudioUploader.tsx
│       ├── lib/
│       │   ├── api.ts        # Cliente HTTP com token
│       │   └── auth.ts       # Gerenciamento JWT
│       └── types/index.ts
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py     # Pydantic Settings
│       │   ├── database.py   # Engine async + session
│       │   └── security.py   # JWT, hashing
│       ├── models/           # SQLAlchemy ORM
│       ├── schemas/          # Pydantic request/response
│       ├── api/v1/           # Endpoints
│       ├── services/         # Lógica de negócio
│       └── workers/          # Pipeline assíncrono
├── docs/
├── scripts/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── .env.example
└── CLAUDE.md
```

---

## Comandos do projeto

```bash
make up            # Sobe todos os serviços (docker compose up -d)
make down          # Para todos os serviços
make logs          # Acompanha logs em tempo real
make test          # Roda pytest no backend
make test-cov      # Roda testes com relatório de cobertura
make lint          # Ruff + Black no backend
make migrate       # Aplica migrations (alembic upgrade head)
make migration MSG="desc"  # Cria nova migration
make seed          # Popula banco com dados de desenvolvimento

make deploy        # Build + up -d + migrate da stack de produção
make prod-up       # Sobe a stack de produção sem rebuild
make prod-down     # Para a stack de produção
make prod-logs     # Acompanha logs da stack de produção
make prod-migrate  # Aplica migrations em produção
```

---

## Ambientes

Duas stacks Docker Compose completamente separadas rodam nesta máquina
("claudinha"), com nomes de projeto (`name:`) distintos para nunca colidir
em containers/volumes:

| | Dev (`docker-compose.yml`, projeto `easyprocess-dev`) | Produção (`docker-compose.prod.yml`, projeto `easyprocess-prod`) |
|---|---|---|
| Domínio | `http://easyprocess.claudinha.local` (interno, via Caddy do host) | `https://easyprocess.ceciliap.com` (público, via Cloudflare Tunnel) |
| Porta do frontend no host | `8104` | `8393` |
| Código | bind-mount, hot reload (`uvicorn --reload`, Next dev) | build (imagem), sem bind-mount — só reflete o que estiver commitado |
| Banco | `db` do próprio compose (porta `5433` no host) | `db` do compose de prod (sem porta publicada), dados nunca compartilhados com o dev |
| Segredos | `.env` | `.env.production` (não versionado; gerar a partir de `.env.production.example`) |
| Subir | `make up` | `make deploy` (rebuild) ou `make prod-up` (sem rebuild) |

**Por que a porta 8393 é fixa para produção:** o Cloudflare Tunnel desta
máquina é *token-based*, com o roteamento de hostname configurado no
painel da Cloudflare (não há `/etc/cloudflared/config.yml` local editável
por aqui). O ingress atual mapeia
`easyprocess.ceciliap.com -> http://localhost:8393` — mudar isso exige
acesso ao painel, não só ao código. Por isso a stack de produção sempre
publica o frontend na 8393, e a de dev usa outra porta (hoje 8104,
registrada via a skill `dev-env`).

**`frontend/Dockerfile.prod`** faz build real (`next build`) + `next start`
— o `frontend/Dockerfile` original só roda `next dev` (nunca teve modo de
produção; `docker-compose.prod.yml` usava ele por engano até 2026-08-12,
o que quebrava com "Module parse failed" no `globals.css` assim que
`NODE_ENV=production` mudava o pipeline do PostCSS/Tailwind sem o build
correspondente).

**Cuidado com `docker compose -f docker-compose.prod.yml` sem `--env-file`:**
o Compose sempre carrega `.env` do diretório atual pra interpolar `${VAR}`
no YAML (ex: `${DB_USER}` do serviço `db`), **mesmo rodando com `-f
docker-compose.prod.yml`** — ele não troca automaticamente pra
`.env.production`. Sem `--env-file .env.production` explícito, o `db` de
produção sobe com as credenciais de dev (`user`/`pass`), enquanto o
`backend` (que usa `env_file: .env.production`) tenta autenticar com as
credenciais de prod — dá `InvalidPasswordError`. Todos os alvos `make
prod-*`/`deploy*` do Makefile já passam `--env-file .env.production`; se
rodar `docker compose` direto, não esqueça a flag.

**Nunca rodar `make seed` contra produção** — o script cria usuários de
teste com senha fraca (`scripts/seed.py`, documentado no README como "só
para desenvolvimento"). Em produção, crie a conta real pela tela de
registro.

Histórico: até 2026-08-12 não havia essa separação — a stack de dev era o
que ficava exposto em `easyprocess.ceciliap.com`, então qualquer teste
manual local (inclusive bugs ainda não commitados) aparecia ao vivo no
domínio público. Ver decisão registrada na tabela abaixo.

---

## Boas práticas de desenvolvimento

### Git workflow

- Branch principal: `main` — sempre em estado deployável
- Branch de desenvolvimento: `develop`
- Feature branches: `feature/SPRINT-NUMERO-descricao`
  - Exemplo: `feature/S1-01-auth-jwt`
- Commits: **Conventional Commits** obrigatório
  - `feat:` nova funcionalidade
  - `fix:` correção de bug
  - `refactor:` refatoração sem mudança de comportamento
  - `test:` adição/ajuste de testes
  - `docs:` documentação
  - `chore:` manutenção (deps, config, CI)
- Pull Request obrigatório para merge em `develop`
- Squash merge para manter histórico limpo

### Padrões de código — Backend (Python)

- **Formatter:** Black
- **Linter:** Ruff
- **Tipagem:** mypy strict mode — sem `Any` implícito
- Schemas Pydantic para toda entrada e saída de API
- Services são classes com métodos `async`; sem lógica de negócio nos endpoints
- Toda query ao banco filtra por `tenant_id` — sem exceção
- Variáveis de ambiente via `pydantic-settings` em `core/config.py` — nunca hardcoded
- Erros retornam JSON consistente via handler global

### Padrões de código — Frontend (TypeScript)

- **Linter:** ESLint
- **Formatter:** Prettier
- TypeScript strict mode — sem `any` implícito
- Alias de importação: `@/` aponta para `src/`
- Componentes UI primitivos via shadcn/ui; não reinventar botões, inputs, cards
- Fetch centralizado em `lib/api.ts` com interceptor de token
- Tratamento de erro com `try/catch` e toast notifications

### Definition of Done (DoD)

Toda task só está pronta quando:
- [ ] Código revisado (self-review no mínimo)
- [ ] Testes unitários para lógica de negócio
- [ ] Sem erros de lint ou tipagem (`make lint` passa)
- [ ] Funcionalidade testada manualmente no Docker
- [ ] Commit com mensagem Conventional Commits

### Estimativas de pontos

| Pontos | Tempo estimado |
|--------|---------------|
| 1 | Meio dia |
| 2 | Um dia |
| 3 | Dois dias |
| 5 | Três+ dias |

Velocidade: **20 pontos/sprint** (1 desenvolvedor, sprints de 2 semanas)

---

## Segurança (regras inegociáveis)

- JWT com expiração de 30min (access) + 7 dias (refresh)
- Senhas com bcrypt cost factor 12
- **Toda query filtra por `tenant_id`** via middleware — middleware não pode ser bypassado
- Rate limiting em registro, login, upload de áudio e refinamento via chat
  (`app/core/rate_limit.py`) — janela fixa por IP (registro/login) ou
  tenant (upload/chat), com contador atômico em Postgres
  (`rate_limit_buckets`), correto mesmo com múltiplos workers do gunicorn.
  IP real extraído de `CF-Connecting-IP`/`X-Forwarded-For` (o app roda
  atrás do Cloudflare Tunnel). Limites configuráveis via
  `RATE_LIMIT_*` no `.env` (defaults: 5 registros/h, 10 logins/15min, 10
  uploads/h, 30 mensagens de chat/h, por chave)
- CORS restrito ao domínio do frontend
- Variáveis sensíveis exclusivamente via `.env` — nunca no código ou logs
- HTTPS obrigatório em produção
- IDs sempre em UUID v4 (não sequenciais — evita enumeração)
- Upload valida magic bytes do arquivo, não só extensão

---

## Banco de dados (esquema principal)

```
tenants → users → projects → processes → process_versions
                                      → chat_messages
tenants → audit_logs
```

**Multi-tenancy:** shared schema com coluna `tenant_id` em todas as tabelas. Middleware do FastAPI injeta o filtro automaticamente. Isolamento testado com testes automatizados dedicados.

**Status do processo (máquina de estados):**
```
pending → transcribing → generating → ready
       └─────────────────────────────→ error
```

---

## API — Endpoints principais

### Autenticação
```
POST /api/v1/auth/register     → Cria tenant + user admin
POST /api/v1/auth/login        → Retorna access + refresh token
POST /api/v1/auth/refresh      → Renova access token
GET  /api/v1/auth/me           → Dados do usuário logado
```

### Projetos
```
GET    /api/v1/projects           → Listar (paginado, filtrado por tenant)
POST   /api/v1/projects           → Criar
GET    /api/v1/projects/:id       → Detalhes
PUT    /api/v1/projects/:id       → Atualizar
DELETE /api/v1/projects/:id       → Soft delete (status → "archived")
```

### Processos (core)
```
POST   /api/v1/projects/:id/processes       → Upload de áudio + iniciar pipeline
GET    /api/v1/processes/:id                → Status + dados
GET    /api/v1/processes/:id/bpmn           → BPMN XML atual
PUT    /api/v1/processes/:id/bpmn           → Atualizar BPMN manualmente
GET    /api/v1/processes/:id/versions       → Histórico de versões
GET    /api/v1/processes/:id/versions/:v    → BPMN de versão específica
POST   /api/v1/processes/:id/versions/:v/restore → Restaurar versão
GET    /api/v1/processes/:id/export         → Download .bpmn
```

### Chat (refinamento)
```
POST   /api/v1/processes/:id/chat     → Envia instrução → IA ajusta BPMN
GET    /api/v1/processes/:id/chat     → Histórico de mensagens
```

### Documentação
```
GET    /api/v1/processes/:id/docs     → Documentação gerada pela IA
POST   /api/v1/processes/:id/docs     → Regenerar documentação
```

### Membros do tenant
```
POST   /api/v1/tenants/invite         → Convidar membro
GET    /api/v1/tenants/members        → Listar membros
PUT    /api/v1/tenants/members/:id    → Alterar role
DELETE /api/v1/tenants/members/:id    → Remover membro
```

---

## Pipeline de processamento

```
1. UPLOAD
   → Valida formato (.mp3, .wav, .m4a, .ogg) e tamanho (< 100MB)
   → Salva em /data/uploads/{tenant_id}/{process_id}/
   → status = "pending"
   → Dispara BackgroundTask

2. TRANSCRIÇÃO  (status = "transcribing")
   → Áudio enviado à Gemini API (`GEMINI_MODEL_TRANSCRIPTION`), language="pt"
   → Salva texto + duração

3. GERAÇÃO BPMN  (status = "generating")
   → Prompt especializado enviado à Gemini API (`GEMINI_MODEL_GENERATION`) — uma
     única chamada faz análise semântica e modelagem BPMN ao mesmo tempo (ver
     `docs/sprints/SPRINT-12-plano.md` para a proposta de separar as duas)
   → Gemini retorna JSON: { bpmn_xml, summary, actors, tasks }
   → Valida XML com lxml
   → Se inválido: retry com prompt corretivo (até 3x)
   → Salva BPMN + metadados + cria version 1

4. PRONTO  (status = "ready")
   → Frontend exibe diagrama no bpmn-js
   → Chat habilitado para refinamento
   → Exportação habilitada

5. REFINAMENTO (loop)
   → Usuário envia instrução em linguagem natural
   → Backend: BPMN atual + histórico + instrução → Gemini (`GEMINI_MODEL_REFINEMENT`)
   → Gemini retorna BPMN atualizado + descrição da mudança
   → Salva nova versão; frontend atualiza viewer em tempo real
```

Cada chamada de IA é instrumentada em `app/services/llm_usage.py` (tokens reais de
`usage_metadata` + custo estimado por tabela de preços) e persistida em
`LlmUsageLog`, visível no painel "Uso de IA" (restrito a platform admin desde a S11).

---

## Prompt Engineering

### Geração inicial
O prompt envia a transcrição e solicita JSON com:
- `bpmn_xml` — XML BPMN 2.0 válido com pools, lanes, gateways, sequence flows e labels em PT-BR
- `summary` — resumo do processo (máx 200 palavras)
- `actors` — lista JSON de participantes identificados
- `tasks` — lista JSON de tarefas com responsável

### Refinamento via chat
O prompt envia:
- BPMN XML atual
- Histórico das últimas 20 mensagens do chat
- Instrução do usuário

Retorna JSON com:
- `bpmn_xml` — XML completo atualizado
- `change_description` — o que foi alterado

### Regras de prompt
- Sempre pedir resposta **somente em JSON** (sem markdown, sem texto extra)
- Sempre validar o XML recebido com `lxml` antes de persistir
- Em caso de XML inválido: retry com prompt corretivo explicitando o erro
- Máximo 3 tentativas antes de propagar erro ao usuário

---

## Estratégia de testes

### Pirâmide
```
        ╱  E2E  ╲         ~10%  → Playwright (fluxos críticos)
       ╱─────────╲
      ╱ Integração╲        ~30%  → pytest + httpx (endpoints + pipeline)
     ╱─────────────╲
    ╱   Unitários   ╲      ~60%  → pytest / Vitest (services, utils, schemas)
   ╱─────────────────╲
```

### Metas de cobertura
| Escopo | Meta |
|--------|------|
| Backend geral | ≥ 80% |
| Frontend componentes críticos | ≥ 70% |
| Pipeline core (`services/`) | ≥ 90% |

### Ferramentas
| Camada | Ferramenta |
|--------|-----------|
| Backend unitário | pytest + pytest-asyncio |
| Backend integração | pytest + httpx.AsyncClient |
| Backend fixtures | factory-boy |
| Backend mock | pytest-mock (mockar a Gemini API) |
| Backend cobertura | pytest-cov + Codecov |
| Frontend unitário | Vitest + React Testing Library |
| Frontend E2E | Playwright |
| Banco de teste | testcontainers (PostgreSQL isolado) |
| CI | GitHub Actions |

### Regra de ouro para mocks
- **Gemini API sempre mockada** nos testes automatizados — nunca gastar créditos em CI
- Testes com API real são manuais e documentados separadamente
- Isolamento multi-tenant tem suite dedicada (`test_tenant_isolation.py`) — é crítico e não pode ser omitido

### CI (GitHub Actions)
- Push em `develop` ou `main`: roda lint + testes unitários + integração
- PR para `develop`: obrigatório passar CI antes de merge
- Testes E2E (Playwright): executados apenas no merge para `main`
- Cobertura < 80% no backend → pipeline falha

---

## Roadmap de Sprints

| Sprint | Período | Foco | Entregável |
|--------|---------|------|-----------|
| **Sprint 0** | Semanas 1-2 | Setup | Repo + Docker + estrutura + CI básico |
| **Sprint 1** | Semanas 3-4 | Auth | Login + registro + multi-tenant + isolamento |
| **Sprint 2** | Semanas 5-6 | Pipeline core | Upload → transcrição → BPMN gerado |
| **Sprint 3** | Semanas 7-8 | Interface | Viewer + chat + exportação |
| **Sprint 4** | Semanas 9-10 | Polish | Docs + testes E2E + deploy produção |

**Duração total:** ~10 semanas (2,5 meses)

---

## Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| BPMN com XML inválido | Loop de validação + retry corretivo (até 3x) |
| Gemini API indisponível/lenta | Retry com backoff exponencial; notificar usuário |
| Qualidade de transcrição pt-BR ruim | Permitir edição da transcrição antes de gerar BPMN |
| Preço por token do Gemini mudar sem aviso | Tabela de preços em `llm_usage.py` é hardcoded e não vem de API (S12-05: agora loga warning quando um modelo não está na tabela, em vez de custo $0 silencioso) — revisar manualmente quando o Gemini mudar tabela ou um `GEMINI_MODEL_*` novo for configurado |
| Vazamento de dados entre tenants | Testes de isolamento automatizados; middleware que impede bypass |

---

## Atualizando a tabela de preços do Gemini (`llm_usage.py`)

`_PRICING_PER_MILLION` em `backend/app/services/llm_usage.py` é uma tabela
hardcoded (USD por 1M tokens de input/output), não vem de nenhuma API — o
painel "Uso de IA" só é coerente enquanto essa tabela bater com o preço real
cobrado pelo Gemini. Atualizar sempre que:
- Um `GEMINI_MODEL`/`GEMINI_MODEL_TRANSCRIPTION`/`_ANALYSIS`/`_GENERATION`/
  `_REFINEMENT` novo for configurado em produção (`.env`) — adicionar a
  entrada na tabela **antes** do deploy, não depois.
- O Google anunciar mudança de preço pra um modelo já usado (já aconteceu
  2x durante a S9 — ver `docs/releases/RELEASE-S9.md`).

Se um modelo não estiver na tabela, `extract_usage` loga um `logger.warning`
(`logger="llm_usage"`) em vez de falhar silenciosamente com custo $0 — vale
monitorar esse log em produção. Preço oficial: [ai.google.dev/pricing](https://ai.google.dev/pricing).

---

## Releases

Ao fim de cada sprint, criar um documento `docs/releases/RELEASE-S{N}.md` seguindo o template abaixo.

### Template de Release

```markdown
# Release Sprint N — [Título]

**Data:** AAAA-MM-DD
**Sprint:** S{N}
**Status:** Concluído / Parcial

## Resumo
Descrição breve do que foi entregue nesta sprint.

## Funcionalidades entregues

### Backend
- [SNUM-XX] Descrição da task — critério de aceite atingido

### Frontend
- [SNUM-XX] Descrição da task — critério de aceite atingido

## Métricas
- Pontos planejados: XX
- Pontos entregues: XX
- Cobertura de testes: XX%
- Testes passando: X/X

## O que ficou para a próxima sprint
- Item não entregue + motivo

## Decisões técnicas tomadas nesta sprint
- Decisão + justificativa

## Como testar esta release
1. Passos para validar manualmente o que foi entregue

## Bugs conhecidos
- Descrição + workaround (se houver)
```

---

## Decisões técnicas registradas

| Decisão | Escolha | Justificativa |
|---------|---------|--------------|
| Transcrição, geração e refinamento | Google Gemini API, um modelo configurável por etapa (`GEMINI_MODEL_TRANSCRIPTION`/`_GENERATION`/`_REFINEMENT`) | Decisão consciente de manter Gemini (não Claude/Whisper, como versões antigas deste documento diziam) — ver `docs/releases/RELEASE-S9.md`. Modelos "lite" mais baratos custam pouco mas modelam BPMN semanticamente pobre; ajustado para `gemini-3.1-flash-lite` em geração/refino |
| Visualizador BPMN | bpmn-js | Mesma lib do Camunda Modeler; open-source; compatibilidade garantida |
| Multi-tenancy | Shared schema + `tenant_id` | Simples para MVP; toda query filtrada via middleware |
| Backend | FastAPI | Async nativo; tipagem forte com Pydantic; integração natural com IA |
| Task queue | BackgroundTasks do FastAPI | Suficiente para MVP; Celery entra quando houver fila e múltiplos workers |
| Banco de testes de integração | Compartilhado com o banco de dev (sem `TEST_DATABASE_URL` isolada) | Os testes de e2e do pipeline disparam `BackgroundTasks` real, que usa `AsyncSessionLocal` de produção — um banco de teste separado não seria visto pelo worker. Trade-off aceito: acumula tenants/usuários de teste no banco de dev (isolados por `tenant_id`, sem risco funcional). Revisar infra de teste/prod se o produto validar mercado (ver `docs/releases/RELEASE-S8.md`) |
| Hospedagem de produção | Mesma máquina do dev ("claudinha"), stack Docker separada (`docker-compose.prod.yml`, projeto `easyprocess-prod`, porta 8393) | Sem staging/homologação — só separação dev/prod. Produção fica exposta via Cloudflare Tunnel (roteamento fixo, gerenciado no painel — não editável por aqui), então a porta 8393 é fixa para produção; dev foi realocado para outra porta. Migrar para VPS/PaaS fica em aberto se o produto crescer (2026-08-12) |

---

## Checklist de boas práticas

- [x] Conventional Commits no Git
- [x] Feature branches + pull requests
- [x] Testes unitários e de integração
- [x] Linting e formatação automática (Black, Ruff, ESLint, Prettier)
- [x] Tipagem estrita (TypeScript strict + mypy)
- [x] Variáveis de ambiente via `.env` (nunca hardcoded)
- [x] Docker para desenvolvimento e produção
- [x] Migrations versionadas (Alembic)
- [x] Error handling consistente (backend e frontend)
- [x] Paginação em todas as listagens
- [x] Soft delete (dados nunca destruídos)
- [x] Versionamento do BPMN (histórico completo)
- [x] Isolamento multi-tenant testado automaticamente
- [x] Rate limiting em endpoints sensíveis
- [x] Documentação técnica e de API (Swagger automático)
- [x] Template de Release ao fim de cada sprint
