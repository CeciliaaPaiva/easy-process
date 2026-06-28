# CLAUDE.md — Plataforma BPMN com IA (Easy Process)

> Guia técnico completo para desenvolvimento com Claude Code.
> Leia este documento antes de iniciar qualquer tarefa no projeto.

---

## Visão geral do produto

**Easy Process** é uma plataforma SaaS B2B que transforma entrevistas em áudio em diagramas BPMN completos usando IA. O fluxo principal é: upload de áudio → transcrição (Whisper) → geração de BPMN (Claude API) → refinamento via chat.

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
| Transcrição | OpenAI Whisper (local, modelo `base`) | - |
| Geração BPMN | Claude API (Anthropic) | claude-sonnet-4-6 |
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
```

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
- Rate limiting no upload de áudio
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
   → Whisper local processa o áudio (modelo "base", language="pt")
   → Salva texto + segmentos com timestamps

3. GERAÇÃO BPMN  (status = "generating")
   → Prompt especializado enviado ao Claude API
   → Claude retorna JSON: { bpmn_xml, summary, actors, tasks }
   → Valida XML com lxml
   → Se inválido: retry com prompt corretivo (até 3x)
   → Salva BPMN + metadados + cria version 1

4. PRONTO  (status = "ready")
   → Frontend exibe diagrama no bpmn-js
   → Chat habilitado para refinamento
   → Exportação habilitada

5. REFINAMENTO (loop)
   → Usuário envia instrução em linguagem natural
   → Backend: BPMN atual + histórico + instrução → Claude
   → Claude retorna BPMN atualizado + descrição da mudança
   → Salva nova versão; frontend atualiza viewer em tempo real
```

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
| Backend mock | pytest-mock (mockar Whisper e Claude API) |
| Backend cobertura | pytest-cov + Codecov |
| Frontend unitário | Vitest + React Testing Library |
| Frontend E2E | Playwright |
| Banco de teste | testcontainers (PostgreSQL isolado) |
| CI | GitHub Actions |

### Regra de ouro para mocks
- **Whisper e Claude API sempre mockados** nos testes automatizados — nunca gastar créditos em CI
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
| Whisper lento em CPU | Limitar áudio a 60min; modelo `base`; processamento em background |
| Claude API indisponível | Retry com backoff exponencial; notificar usuário |
| Qualidade de transcrição pt-BR ruim | Permitir edição da transcrição antes de gerar BPMN; upgrade para modelo `small` |
| Vazamento de dados entre tenants | Testes de isolamento automatizados; middleware que impede bypass |

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
| Transcrição | Whisper local (`base`) | Zero custo; roda em CPU; qualidade razoável em pt-BR |
| Visualizador BPMN | bpmn-js | Mesma lib do Camunda Modeler; open-source; compatibilidade garantida |
| Multi-tenancy | Shared schema + `tenant_id` | Simples para MVP; toda query filtrada via middleware |
| Backend | FastAPI | Async nativo; tipagem forte com Pydantic; integração natural com IA |
| Task queue | BackgroundTasks do FastAPI | Suficiente para MVP; Celery entra quando houver fila e múltiplos workers |

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
