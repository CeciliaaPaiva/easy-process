# Plano de implementação — Plataforma BPMN com IA

## Convenções e boas práticas gerais

### Git workflow
- Branch principal: `main` (sempre deployável)
- Branch de desenvolvimento: `develop`
- Feature branches: `feature/SPRINT-NUMERO-descricao` (ex: `feature/S1-01-auth-jwt`)
- Commits: Conventional Commits — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Pull request obrigatório para merge em `develop`
- Squash merge para manter histórico limpo

### Padrão de código
- Backend: Black (formatter) + Ruff (linter) + mypy (tipagem)
- Frontend: ESLint + Prettier + TypeScript strict mode
- Testes: pytest (backend), Jest/Vitest (frontend)
- Variáveis de ambiente: nunca hardcoded, sempre via `.env`

### Definition of Done (DoD) — vale para todas as tasks
- Código revisado (self-review no mínimo)
- Testes unitários para lógica de negócio
- Sem erros de lint ou tipagem
- Documentação atualizada se necessário
- Funcionalidade testada manualmente
- Commit com mensagem descritiva

### Estrutura de cada sprint
- Duração: 2 semanas (10 dias úteis)
- Cada task tem estimativa em pontos (1 = meio dia, 2 = um dia, 3 = dois dias, 5 = três+ dias)
- Velocidade estimada: 20 pontos por sprint (1 desenvolvedor)

---

## Sprint 0 — Foundation e setup (semana 1-2)
**Objetivo:** Infraestrutura pronta para desenvolver sem atrito.
**Entregável:** Repositório configurado, Docker rodando, banco criado, CI básico.

### Tasks

#### S0-01 · Criar monorepo e estrutura de diretórios [2 pts]
```
bpmn-ai-platform/
├── frontend/          # Next.js app
├── backend/           # FastAPI app
├── docker/            # Dockerfiles separados
├── docs/              # Documentação do projeto
├── scripts/           # Scripts auxiliares (seed, migrate)
├── docker-compose.yml
├── .env.example
├── .gitignore
├── Makefile           # Atalhos: make up, make test, make lint
└── README.md
```
**Critério de aceite:** `git clone` + `make up` sobe tudo do zero.

#### S0-02 · Configurar Docker Compose completo [3 pts]
Serviços: `frontend`, `backend`, `db` (PostgreSQL 16).
- Hot reload no frontend e backend (volumes montados)
- Health checks no banco
- Variáveis via `.env`
- Rede interna nomeada

**Critério de aceite:** `docker compose up` sobe os 3 serviços; frontend acessível em `localhost:3000`, backend em `localhost:8000/docs` (Swagger).

#### S0-03 · Setup backend FastAPI com estrutura limpa [3 pts]
```
backend/app/
├── main.py              # App factory
├── core/
│   ├── config.py        # Pydantic Settings (carrega .env)
│   ├── database.py      # SQLAlchemy async engine + session
│   └── security.py      # (placeholder)
├── models/              # (placeholder __init__.py)
├── schemas/             # (placeholder __init__.py)
├── api/
│   ├── deps.py          # get_db dependency
│   └── v1/
│       └── health.py    # GET /health → {"status": "ok"}
└── tests/
    └── test_health.py
```
- Instalar: FastAPI, uvicorn, SQLAlchemy, asyncpg, pydantic-settings, python-jose, passlib, python-multipart
- `pyproject.toml` com dependências e scripts
- Configurar Black + Ruff + mypy

**Critério de aceite:** `GET /health` retorna 200; `make lint` passa sem erros; `make test` roda pytest.

#### S0-04 · Setup frontend Next.js com TypeScript [3 pts]
```
frontend/src/
├── app/
│   ├── layout.tsx       # Layout raiz (fonte, metadata)
│   ├── page.tsx         # Landing page (placeholder)
│   └── (auth)/
│       └── login/
│           └── page.tsx # Placeholder
├── components/
│   └── ui/              # Componentes base (Button, Input, Card)
├── lib/
│   ├── api.ts           # Fetch wrapper com base URL e token
│   └── utils.ts
└── types/
    └── index.ts
```
- Instalar: Tailwind CSS, shadcn/ui (init), lucide-react
- ESLint + Prettier configurados
- Alias de importação: `@/` → `src/`

**Critério de aceite:** `localhost:3000` renderiza página; `make lint:frontend` passa.

#### S0-05 · Configurar banco e migrations (Alembic) [3 pts]
- Instalar alembic no backend
- Configurar `alembic.ini` apontando para `DATABASE_URL`
- Criar migration inicial vazia (para validar o setup)
- Script `make migrate` e `make migration MSG="descricao"`

**Critério de aceite:** `make migrate` roda sem erro; tabela `alembic_version` existe no banco.

#### S0-06 · Makefile com atalhos de desenvolvimento [1 pt]
```makefile
up:             docker compose up -d
down:           docker compose down
logs:           docker compose logs -f
test:           docker compose exec backend pytest
lint:           docker compose exec backend ruff check . && black --check .
migrate:        docker compose exec backend alembic upgrade head
migration:      docker compose exec backend alembic revision --autogenerate -m "$(MSG)"
seed:           docker compose exec backend python scripts/seed.py
```

**Critério de aceite:** Todos os comandos funcionam.

#### S0-07 · README com setup instructions [1 pt]
- Pré-requisitos (Docker, Docker Compose)
- Como rodar (`make up`)
- Como rodar testes
- Estrutura do projeto
- Variáveis de ambiente documentadas

**Critério de aceite:** Alguém novo consegue rodar o projeto seguindo o README.

**Total Sprint 0: 16 pontos**

---

## Sprint 1 — Autenticação e multi-tenant (semana 3-4)
**Objetivo:** Usuário se registra, faz login e acessa apenas dados do seu tenant.
**Entregável:** Auth funcional com isolamento por empresa.

### Tasks

#### S1-01 · Models: Tenant e User [3 pts]
```python
# models/tenant.py
class Tenant(Base):
    __tablename__ = "tenants"
    id: UUID (PK)
    name: str
    slug: str (unique)
    plan: str (default "free")
    created_at: datetime

# models/user.py
class User(Base):
    __tablename__ = "users"
    id: UUID (PK)
    tenant_id: UUID (FK → tenants)
    email: str
    password_hash: str
    name: str
    role: str (default "analyst")
    is_active: bool (default True)
    created_at: datetime
```
- Migration Alembic gerando as tabelas
- Índices: `(tenant_id, email)` unique

**Critério de aceite:** Migration roda; tabelas existem no banco com constraints corretas.

#### S1-02 · Módulo de segurança (JWT + hashing) [3 pts]
```python
# core/security.py
- create_access_token(data, expires_delta) → str
- create_refresh_token(data) → str
- verify_token(token) → payload dict
- hash_password(password) → str
- verify_password(plain, hashed) → bool
```
- JWT com python-jose (HS256)
- bcrypt via passlib
- Access token: 30min; Refresh token: 7 dias
- Testes unitários para cada função

**Critério de aceite:** Testes passam; token gerado é decodificável; senha hashada não é reversível.

#### S1-03 · Endpoints de autenticação [5 pts]
```
POST /api/v1/auth/register
  Body: { name, email, password, company_name }
  → Cria tenant + user (admin)
  → Retorna { access_token, refresh_token, user }

POST /api/v1/auth/login
  Body: { email, password }
  → Valida credenciais
  → Retorna { access_token, refresh_token, user }

POST /api/v1/auth/refresh
  Body: { refresh_token }
  → Retorna novo { access_token }

GET /api/v1/auth/me
  Header: Authorization: Bearer <token>
  → Retorna dados do usuário logado
```
- Schemas Pydantic para request/response
- Tratamento de erros (email duplicado, senha inválida, token expirado)
- Testes para cada endpoint (happy path + erros)

**Critério de aceite:** Swagger funcional; registro cria tenant + user; login retorna tokens válidos; `/me` retorna dados do usuário.

#### S1-04 · Middleware de tenant isolation [3 pts]
```python
# api/deps.py
async def get_current_user(token) → User
async def get_current_tenant(user) → Tenant
async def get_db_with_tenant(tenant) → Session
  # Adiciona filtro automático por tenant_id
```
- Toda query passa pelo filtro de tenant
- Usuário sem token → 401
- Usuário acessando recurso de outro tenant → 403
- Teste: criar 2 tenants e verificar que um não vê dados do outro

**Critério de aceite:** Teste de isolamento passa; não é possível acessar dados entre tenants.

#### S1-05 · Frontend: páginas de login e registro [3 pts]
- Página `/login` com formulário (email, senha)
- Página `/register` com formulário (nome, email, senha, empresa)
- Componentes: Input, Button, Card, Alert (shadcn/ui)
- `lib/api.ts`: interceptor que adiciona token no header
- `lib/auth.ts`: armazenar token, verificar expiração, refresh automático
- Redirect para `/projects` após login bem-sucedido
- Redirect para `/login` se não autenticado

**Critério de aceite:** Fluxo completo: registro → login → dashboard (vazio) → logout.

#### S1-06 · Frontend: layout autenticado com sidebar [2 pts]
- Layout com sidebar: logo, menu (Projetos, Configurações), botão logout
- Header com nome do usuário e empresa
- Responsivo (sidebar colapsável em mobile)
- Proteção de rota: redireciona para `/login` se sem token

**Critério de aceite:** Layout renderiza corretamente; sidebar funcional; proteção de rota funciona.

#### S1-07 · Seed script para desenvolvimento [1 pt]
```python
# scripts/seed.py
# Cria tenant "Demo Corp" + usuário admin (admin@demo.com / 123456)
# Cria tenant "Acme Inc" + usuário (user@acme.com / 123456)
```

**Critério de aceite:** `make seed` cria dados; login funciona com credenciais do seed.

**Total Sprint 1: 20 pontos**

---

## Sprint 2 — CRUD de projetos + pipeline core (semana 5-6)
**Objetivo:** Upload de áudio → transcrição → geração de BPMN funcional.
**Entregável:** Pipeline end-to-end rodando, mesmo que com interface básica.

### Tasks

#### S2-01 · Model: Project [2 pts]
```python
class Project(Base):
    __tablename__ = "projects"
    id, tenant_id, name, description, status, created_by, created_at, updated_at
```
- Migration Alembic
- Índice em tenant_id

**Critério de aceite:** Tabela criada com constraints.

#### S2-02 · CRUD endpoints de projetos [3 pts]
```
GET    /api/v1/projects           → Lista (paginado, filtrado por tenant)
POST   /api/v1/projects           → Criar
GET    /api/v1/projects/:id       → Detalhe
PUT    /api/v1/projects/:id       → Atualizar
DELETE /api/v1/projects/:id       → Soft delete (status → archived)
```
- Paginação: `?page=1&per_page=20`
- Schemas Pydantic
- Testes: CRUD completo + isolamento por tenant

**Critério de aceite:** Testes passam; Swagger funcional; isolamento verificado.

#### S2-03 · Models: Process, ProcessVersion, ChatMessage [3 pts]
```python
class Process(Base):
    # id, project_id, tenant_id, name, audio_path, transcription,
    # bpmn_xml, summary, actors (JSONB), tasks (JSONB),
    # version, status, created_at, updated_at

class ProcessVersion(Base):
    # id, process_id, version, bpmn_xml, change_description, created_at

class ChatMessage(Base):
    # id, process_id, role, content, bpmn_version, created_at
```
- Migration Alembic com todas as tabelas e FKs

**Critério de aceite:** Todas as tabelas criadas; FKs e índices corretos.

#### S2-04 · Serviço de upload e armazenamento de áudio [2 pts]
```python
# services/storage.py
async def save_audio(file: UploadFile, tenant_id, process_id) → str:
    # Valida extensão (.mp3, .wav, .m4a, .ogg)
    # Valida tamanho (max 100MB)
    # Salva em /data/uploads/{tenant_id}/{process_id}/audio.{ext}
    # Retorna path
```
- Estrutura de diretórios por tenant (isolamento no filesystem também)
- Endpoint: `POST /api/v1/projects/:id/processes` (multipart/form-data)

**Critério de aceite:** Upload salva arquivo no path correto; rejeita formatos inválidos; rejeita arquivos > 100MB.

#### S2-05 · Serviço de transcrição com Whisper [3 pts]
```python
# services/transcription.py
import whisper

class TranscriptionService:
    def __init__(self):
        self.model = whisper.load_model("base")

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        result = self.model.transcribe(audio_path, language="pt")
        return TranscriptionResult(
            text=result["text"],
            segments=[
                Segment(start=s["start"], end=s["end"], text=s["text"])
                for s in result["segments"]
            ],
            language=result["language"],
            duration=result["segments"][-1]["end"]
        )
```
- Singleton do modelo (carregar uma vez, reusar)
- Tratar erros de arquivo corrompido
- Teste com arquivo de áudio curto (fixture)

**Critério de aceite:** Transcrição funciona com áudio em pt-BR; retorna texto + segmentos com timestamps.

#### S2-06 · Serviço de geração BPMN com Claude API [5 pts]
```python
# services/bpmn_generator.py
class BpmnGeneratorService:
    async def generate(self, transcription: str) -> BpmnGenerationResult:
        # 1. Monta o prompt com a transcrição
        # 2. Chama Claude API
        # 3. Parseia a resposta JSON
        # 4. Valida o BPMN XML (bem-formado)
        # 5. Retorna BpmnGenerationResult(bpmn_xml, summary, actors, tasks)
```
- Prompt engineering robusto (XML válido, elementos BPMN corretos)
- Retry com backoff em caso de erro da API
- Validação do XML retornado (parsear com lxml)
- Fallback: se o XML for inválido, tentar novamente com prompt corretivo
- Testes com mock da API (não gastar créditos em teste)

**Critério de aceite:** Dado um texto de transcrição, retorna BPMN XML válido que abre no Camunda Modeler.

#### S2-07 · Pipeline assíncrono (orquestrar o fluxo) [2 pts]
```python
# workers/process_audio.py
async def process_audio_pipeline(process_id: UUID):
    process = await get_process(process_id)

    # Etapa 1: Transcrição
    await update_status(process_id, "transcribing")
    transcription = await transcription_service.transcribe(process.audio_path)
    await save_transcription(process_id, transcription)

    # Etapa 2: Geração BPMN
    await update_status(process_id, "generating")
    result = await bpmn_generator.generate(transcription.text)
    await save_bpmn(process_id, result)
    await create_version(process_id, version=1, bpmn_xml=result.bpmn_xml)

    # Etapa 3: Pronto
    await update_status(process_id, "ready")
```
- Usar `BackgroundTasks` do FastAPI
- Tratar erros em cada etapa (status → "error" com mensagem)
- Endpoint de status: `GET /api/v1/processes/:id/status`

**Critério de aceite:** Upload dispara pipeline; status atualiza em cada etapa; ao final, BPMN XML está no banco.

**Total Sprint 2: 20 pontos**

---

## Sprint 3 — Interface e visualização BPMN (semana 7-8)
**Objetivo:** Usuário vê o BPMN gerado, interage via chat, exporta.
**Entregável:** Interface completa do produto, usável.

### Tasks

#### S3-01 · Frontend: lista de projetos [2 pts]
- Página `/projects` com grid/lista de projetos
- Card com: nome, descrição, quantidade de processos, data
- Botão "Novo projeto" → modal com formulário
- Busca por nome
- Loading states e empty states

**Critério de aceite:** Lista carrega do backend; criar projeto funciona; busca filtra.

#### S3-02 · Frontend: página do projeto com processos [3 pts]
- Página `/projects/:id` com detalhes e lista de processos
- Card de processo: nome, status (badge colorido), data
- Status: pending (cinza), transcribing (amarelo), generating (azul), ready (verde), error (vermelho)
- Botão "Novo processo" → abre upload

**Critério de aceite:** Lista de processos do projeto; status visual correto; navegação funcional.

#### S3-03 · Frontend: upload de áudio com progresso [3 pts]
- Modal/página de upload com drag-and-drop
- Validação client-side (formato, tamanho)
- Barra de progresso do upload
- Após upload: tela de "processando" com polling do status
- Transições de status animadas (transcribing → generating → ready)
- Ao ficar "ready": redireciona para o viewer

**Critério de aceite:** Upload funciona; progresso visual; polling atualiza status; redireciona ao completar.

#### S3-04 · Frontend: visualizador BPMN com bpmn-js [5 pts]
```typescript
// components/bpmn/BpmnViewer.tsx
// Wrapper React do bpmn-js
// - Recebe bpmn_xml como prop
// - Renderiza diagrama interativo
// - Zoom in/out, pan, fit-to-screen
// - Toolbar: zoom, centralizar, exportar PNG, baixar .bpmn
```
- Instalar: `bpmn-js` + `bpmn-js-properties-panel` (opcional)
- Layout: BPMN viewer ocupa a área principal, chat na lateral direita
- Fullscreen toggle
- Exportar como .bpmn (download do XML)
- Exportar como PNG (canvas → imagem)

**Critério de aceite:** BPMN renderiza corretamente; zoom/pan funcionam; exportação .bpmn gera arquivo válido que abre no Camunda Modeler.

#### S3-05 · Backend: endpoints do chat de refinamento [3 pts]
```
POST /api/v1/processes/:id/chat
  Body: { message: "Adicione uma tarefa de aprovação do gerente antes do envio" }
  → Envia: BPMN atual + histórico do chat + mensagem
  → Claude retorna: BPMN atualizado + descrição da mudança
  → Salva nova versão + mensagem no histórico
  → Retorna: { bpmn_xml, change_description, version }

GET /api/v1/processes/:id/chat
  → Retorna histórico de mensagens com versões
```
- Serviço `bpmn_refiner.py` com prompt específico de refinamento
- Limitar histórico do chat enviado à API (últimas 20 mensagens)
- Salvar versão a cada alteração

**Critério de aceite:** Chat com instrução em português retorna BPMN ajustado; versão é incrementada; histórico é persistido.

#### S3-06 · Frontend: chat de refinamento [3 pts]
- Painel lateral (direita) com chat
- Mensagens: usuário (direita), IA (esquerda)
- Input com botão de envio
- Loading state enquanto IA processa
- Ao receber resposta: atualiza o viewer BPMN automaticamente
- Badge de versão (v1, v2, v3...)
- Scroll automático para última mensagem

**Critério de aceite:** Chat envia mensagem; IA responde; BPMN atualiza visualmente; versão incrementa.

#### S3-07 · Backend: histórico de versões e rollback [1 pt]
```
GET /api/v1/processes/:id/versions       → Lista versões
GET /api/v1/processes/:id/versions/:v    → BPMN de versão específica
POST /api/v1/processes/:id/versions/:v/restore  → Restaurar versão
```

**Critério de aceite:** Listar versões; visualizar versão anterior; restaurar atualiza o BPMN atual.

**Total Sprint 3: 20 pontos**

---

## Sprint 4 — Documentação, polish e deploy (semana 9-10)
**Objetivo:** Produto polido, documentado, deployável.
**Entregável:** MVP pronto para demonstração e primeiros usuários.

### Tasks

#### S4-01 · Geração automática de documentação do processo [3 pts]
```python
# services/documentation.py
# Recebe BPMN XML → Claude gera documentação estruturada:
# - Descrição geral do processo
# - Tabela de atividades (nome, responsável, descrição, inputs, outputs)
# - Regras de negócio identificadas
# - Pontos de decisão e critérios
# - Exceções e tratamentos
```
- Endpoint: `GET /api/v1/processes/:id/docs`
- Cachear resultado (regenerar apenas quando BPMN mudar)
- Frontend: aba "Documentação" na página do processo

**Critério de aceite:** Documentação gerada é útil e completa; exibe corretamente no frontend.

#### S4-02 · Frontend: dashboard com métricas [2 pts]
- Total de projetos e processos
- Processos por status (gráfico simples)
- Atividade recente (últimos processos criados/editados)
- Uso do mês (quantidade de transcrições)

**Critério de aceite:** Dashboard carrega com dados reais; gráficos renderizam.

#### S4-03 · Tratamento de erros e edge cases [3 pts]
- Backend: error handler global (retorna JSON consistente)
- Frontend: error boundaries, toast notifications
- Pipeline: retry automático em caso de falha na API Claude
- Upload: tratar áudio muito curto (< 10s), muito longo (> 60min), silencioso
- Transcrição vazia: retornar erro amigável
- BPMN inválido: loop de correção (até 3 tentativas)

**Critério de aceite:** Nenhum erro não tratado; mensagens amigáveis em todos os cenários de falha.

#### S4-04 · Testes de integração do pipeline completo [3 pts]
```python
# tests/integration/test_pipeline.py
# 1. Registrar usuário
# 2. Criar projeto
# 3. Upload de áudio (fixture curto, ~30s)
# 4. Aguardar pipeline completar
# 5. Verificar: transcrição existe, BPMN é XML válido
# 6. Enviar mensagem no chat
# 7. Verificar: BPMN atualizado, versão incrementada
# 8. Exportar .bpmn
# 9. Verificar: arquivo válido
```
- Usar áudio de teste (gravar fixture de 30s descrevendo um processo simples)
- Mock da Claude API para testes automatizados (resposta fixa)
- Teste real com API (manual, não no CI)

**Critério de aceite:** Teste de integração roda do início ao fim sem falhas.

#### S4-05 · Configuração para deploy em servidor [3 pts]
- `docker-compose.prod.yml` com configs de produção
- Nginx como reverse proxy (HTTPS com Let's Encrypt)
- Backend: Gunicorn + Uvicorn workers
- Variáveis de produção documentadas
- Script de deploy: `make deploy`
- Backup automático do PostgreSQL (cron + pg_dump)
- `.env.production.example` com todas as variáveis

**Critério de aceite:** `docker compose -f docker-compose.prod.yml up` sobe tudo em modo produção; HTTPS funciona.

#### S4-06 · Convite de membros para o tenant [2 pts]
```
POST /api/v1/tenants/invite
  Body: { email, role }
  → Cria user com senha temporária
  → (futuro: enviar email de convite)

GET /api/v1/tenants/members     → Listar membros
PUT /api/v1/tenants/members/:id → Alterar role
DELETE /api/v1/tenants/members/:id → Remover membro
```
- Frontend: página de configurações com lista de membros

**Critério de aceite:** Admin consegue adicionar membro; membro faz login e vê os projetos do tenant.

#### S4-07 · Ajustes de UX e responsividade [2 pts]
- Testar em mobile (chat + viewer)
- Loading skeletons em todas as páginas
- Transições suaves entre estados
- Favicon, meta tags, título dinâmico
- 404 e 500 pages customizadas

**Critério de aceite:** Produto usável em mobile; sem estados "em branco" durante carregamento.

#### S4-08 · README final e documentação técnica [2 pts]
- README atualizado com screenshots
- Documentação da API (Swagger já gera, mas revisar)
- Guia de contribuição (para quando expandir equipe)
- Arquitetura documentada (o documento que já temos)
- `.env.example` completo e comentado

**Critério de aceite:** Documentação suficiente para um novo desenvolvedor embarcar no projeto.

**Total Sprint 4: 20 pontos**

---

## Resumo do roadmap

| Sprint | Semanas | Foco | Entregável |
|--------|---------|------|-----------|
| Sprint 0 | 1-2 | Setup | Repo + Docker + estrutura + CI |
| Sprint 1 | 3-4 | Auth | Login + registro + multi-tenant |
| Sprint 2 | 5-6 | Core | Upload → transcrição → BPMN |
| Sprint 3 | 7-8 | UI | Viewer + chat + exportação |
| Sprint 4 | 9-10 | Polish | Docs + testes + deploy |

**Velocidade: 20 pts/sprint × 5 sprints = 96 pontos totais**
**Duração: 10 semanas (2.5 meses)**

---

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| BPMN gerado pela IA com XML inválido | Pipeline quebra | Loop de validação + retry com prompt corretivo (até 3x) |
| Whisper lento em CPU (áudio longo) | UX ruim, timeout | Limitar áudio a 60min; usar modelo `base` (mais rápido); processar em background |
| Claude API fora do ar | Pipeline para | Retry com backoff exponencial; fila de retry; notificar usuário |
| Qualidade da transcrição em pt-BR | BPMN impreciso | Permitir edição da transcrição antes de gerar BPMN; upgrade para Whisper `small` |
| Multi-tenancy com vazamento de dados | Segurança crítica | Testes automatizados de isolamento; middleware que impede bypass |

---

## Checklist de boas práticas aplicadas

- [x] Conventional Commits no Git
- [x] Feature branches + pull requests
- [x] Testes unitários e de integração
- [x] Linting e formatação automática
- [x] Tipagem estrita (TypeScript + mypy)
- [x] Variáveis de ambiente (nunca hardcoded)
- [x] Docker para desenvolvimento e produção
- [x] Migrations versionadas (Alembic)
- [x] Error handling consistente (backend e frontend)
- [x] Paginação em listagens
- [x] Soft delete (não perder dados)
- [x] Versionamento do BPMN (histórico completo)
- [x] Isolamento multi-tenant testado
- [x] Rate limiting em endpoints sensíveis
- [x] Documentação técnica e de API
