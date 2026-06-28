# Arquitetura MVP — Plataforma de Modelagem BPMN com IA

## 1. Visão geral do produto

Uma plataforma SaaS B2B que transforma entrevistas em áudio em diagramas BPMN completos, usando IA para transcrever, analisar e modelar processos automaticamente. O público-alvo inicial são analistas de negócios que querem acelerar a fase de modelagem.

### Proposta de valor
- Upload de áudio → BPMN pronto em minutos (não em dias)
- Refinamento via chat com IA (sem precisar saber BPMN)
- Exportação para Camunda Modeler / qualquer ferramenta BPMN
- Multi-tenant: cada empresa isolada

---

## 2. Stack tecnológica

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| Frontend | Next.js 14+ (App Router) + TypeScript | SSR, React (você já conhece), ecosystem maduro |
| Visualizador BPMN | bpmn-js (Camunda open-source) | Viewer + editor leve, gratuito, padrão do mercado |
| Backend / API | Python 3.11+ com FastAPI | Async, tipagem, integra com Whisper nativo |
| Transcrição | OpenAI Whisper (local, modelo `base` ou `small`) | Gratuito, roda local, boa qualidade pt-BR |
| Geração BPMN | Claude API (Anthropic) | Melhor para geração de XML estruturado |
| Banco de dados | PostgreSQL 16 | Multi-tenant, JSONB, robusto |
| Armazenamento | Sistema de arquivos local (→ S3 futuro) | Zero custo no MVP |
| Containerização | Docker + Docker Compose | Deploy consistente no servidor |
| Autenticação | JWT + bcrypt | Simples, stateless |

---

## 3. Módulos do sistema

### 3.1 Frontend (Next.js)

```
src/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   └── register/
│   ├── (dashboard)/
│   │   ├── projects/              # Lista de projetos
│   │   ├── projects/[id]/         # Detalhe do projeto
│   │   ├── projects/[id]/viewer/  # Visualizador BPMN (bpmn-js)
│   │   ├── projects/[id]/chat/    # Chat com IA
│   │   └── projects/[id]/docs/    # Documentação gerada
│   └── layout.tsx
├── components/
│   ├── bpmn/
│   │   ├── BpmnViewer.tsx         # Wrapper do bpmn-js
│   │   └── BpmnToolbar.tsx        # Ações: exportar, zoom, etc
│   ├── chat/
│   │   ├── ChatWindow.tsx         # Interface de chat
│   │   └── ChatMessage.tsx
│   └── upload/
│       └── AudioUploader.tsx      # Upload + progresso
├── lib/
│   ├── api.ts                     # Client HTTP (fetch/axios)
│   └── auth.ts                    # Gerenciamento de token JWT
└── types/
    └── index.ts                   # Tipagens compartilhadas
```

**Páginas principais:**
- Login / Registro
- Dashboard: lista de projetos da empresa
- Projeto: visualizador BPMN + chat lateral + documentação
- Upload: enviar áudio e acompanhar processamento

### 3.2 Backend (FastAPI)

```
app/
├── main.py                        # Entrypoint FastAPI
├── core/
│   ├── config.py                  # Settings (env vars)
│   ├── security.py                # JWT, hashing, auth
│   └── database.py                # SQLAlchemy engine + session
├── models/                        # SQLAlchemy ORM
│   ├── tenant.py
│   ├── user.py
│   ├── project.py
│   ├── process.py
│   ├── chat_message.py
│   └── audit_log.py
├── schemas/                       # Pydantic (request/response)
│   ├── tenant.py
│   ├── user.py
│   ├── project.py
│   └── process.py
├── api/
│   ├── v1/
│   │   ├── auth.py                # POST /login, /register
│   │   ├── projects.py            # CRUD projetos
│   │   ├── processes.py           # Upload, status, BPMN
│   │   ├── chat.py                # Chat com IA
│   │   └── export.py              # Download BPMN XML
│   └── deps.py                    # Dependências (get_db, get_user)
├── services/
│   ├── transcription.py           # Whisper local
│   ├── bpmn_generator.py          # Claude API → BPMN XML
│   ├── bpmn_refiner.py            # Chat → ajustes no BPMN
│   └── documentation.py           # Geração de docs do processo
└── workers/
    └── process_audio.py           # Task assíncrona (Celery ou background)
```

### 3.3 Serviços de IA

**Transcrição (Whisper local):**
```python
# services/transcription.py
import whisper

model = whisper.load_model("base")  # ou "small" para pt-BR melhor

async def transcribe(audio_path: str) -> dict:
    result = model.transcribe(audio_path, language="pt")
    return {
        "text": result["text"],
        "segments": result["segments"],  # com timestamps
        "language": result["language"]
    }
```

**Geração BPMN (Claude API):**
```python
# services/bpmn_generator.py
# O prompt envia a transcrição e recebe BPMN XML válido
# Detalhado na seção 6 (Prompt Engineering)
```

---

## 4. Banco de dados (PostgreSQL)

### Schema multi-tenant

```sql
-- Cada empresa é um tenant isolado
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'analyst',  -- admin, analyst, viewer
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE processes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    -- Artefatos
    audio_path VARCHAR(500),
    transcription TEXT,
    bpmn_xml TEXT,                       -- O XML BPMN gerado/editado
    -- Metadados extraídos pela IA
    summary TEXT,                        -- Resumo do processo
    actors JSONB DEFAULT '[]',           -- Participantes identificados
    tasks JSONB DEFAULT '[]',            -- Tarefas extraídas
    -- Controle
    version INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'pending', -- pending, transcribing, generating, ready, error
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Histórico de versões do BPMN (cada edição via chat gera nova versão)
CREATE TABLE process_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id UUID REFERENCES processes(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    bpmn_xml TEXT NOT NULL,
    change_description TEXT,             -- O que a IA mudou
    created_at TIMESTAMP DEFAULT NOW()
);

-- Mensagens do chat de refinamento
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id UUID REFERENCES processes(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,           -- user, assistant
    content TEXT NOT NULL,
    bpmn_version INTEGER,               -- Versão do BPMN após esta mensagem
    created_at TIMESTAMP DEFAULT NOW()
);

-- Auditoria
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para multi-tenant
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_projects_tenant ON projects(tenant_id);
CREATE INDEX idx_processes_tenant ON processes(tenant_id);
CREATE INDEX idx_processes_status ON processes(status);
CREATE INDEX idx_chat_process ON chat_messages(process_id);
```

### Estratégia multi-tenant
- Abordagem: coluna `tenant_id` em todas as tabelas (shared schema)
- Toda query filtra por `tenant_id` via middleware/dependency do FastAPI
- Simples para o MVP, escalável para centenas de tenants
- Migração futura para schema-per-tenant se necessário

---

## 5. API (endpoints principais)

### Autenticação
```
POST   /api/v1/auth/register     → Criar conta + tenant
POST   /api/v1/auth/login        → JWT token
POST   /api/v1/auth/refresh      → Renovar token
```

### Projetos
```
GET    /api/v1/projects           → Listar projetos (do tenant)
POST   /api/v1/projects           → Criar projeto
GET    /api/v1/projects/:id       → Detalhes do projeto
PUT    /api/v1/projects/:id       → Atualizar projeto
DELETE /api/v1/projects/:id       → Remover projeto
```

### Processos (o core)
```
POST   /api/v1/processes          → Upload de áudio + iniciar pipeline
GET    /api/v1/processes/:id      → Status + dados do processo
GET    /api/v1/processes/:id/bpmn → Obter BPMN XML atual
PUT    /api/v1/processes/:id/bpmn → Atualizar BPMN (edição manual)
GET    /api/v1/processes/:id/versions → Histórico de versões
GET    /api/v1/processes/:id/export   → Download BPMN (.bpmn)
```

### Chat (refinamento com IA)
```
POST   /api/v1/processes/:id/chat     → Enviar mensagem → IA ajusta BPMN
GET    /api/v1/processes/:id/chat     → Histórico do chat
```

### Documentação
```
GET    /api/v1/processes/:id/docs     → Documentação gerada pela IA
POST   /api/v1/processes/:id/docs     → Regenerar documentação
```

---

## 6. Pipeline de processamento (fluxo principal)

```
1. UPLOAD
   Usuário envia áudio (.mp3, .wav, .m4a, .ogg)
   → Backend salva no filesystem
   → Cria registro no banco com status "pending"
   → Inicia task assíncrona

2. TRANSCRIÇÃO
   Status → "transcribing"
   → Whisper (local) processa o áudio
   → Salva transcrição no banco (campo transcription)
   → Salva segmentos com timestamps

3. ANÁLISE + GERAÇÃO BPMN
   Status → "generating"
   → Envia transcrição para Claude API com prompt especializado
   → Claude retorna:
     a) BPMN XML válido (padrão 2.0)
     b) Resumo do processo
     c) Lista de atores/participantes
     d) Lista de tarefas identificadas
   → Salva tudo no banco
   → Cria versão 1 em process_versions

4. PRONTO
   Status → "ready"
   → Frontend exibe BPMN no viewer (bpmn-js)
   → Habilita chat para refinamento
   → Habilita exportação

5. REFINAMENTO (loop)
   Usuário envia instrução no chat
   → Backend envia: BPMN atual + histórico do chat + instrução
   → Claude retorna BPMN atualizado + descrição da mudança
   → Salva nova versão
   → Frontend atualiza viewer em tempo real
```

---

## 7. Prompt engineering (estratégia)

### Prompt de geração inicial (simplificado)
```
Você é um especialista em modelagem de processos BPMN 2.0.

Analise a transcrição de uma entrevista com um cliente e gere:

1. Um diagrama BPMN 2.0 em XML válido, incluindo:
   - Start Event e End Event
   - User Tasks e Service Tasks
   - Gateways (Exclusive, Parallel) quando houver decisões ou paralelismo
   - Pools e Lanes para cada ator/departamento identificado
   - Sequence Flows conectando todos os elementos
   - Labels descritivos em português

2. Um resumo do processo (máx 200 palavras)

3. Lista de atores/participantes identificados (JSON)

4. Lista de tarefas identificadas com responsável (JSON)

TRANSCRIÇÃO:
{transcription}

Responda APENAS com JSON no formato:
{
  "bpmn_xml": "<?xml version='1.0'...>",
  "summary": "...",
  "actors": [...],
  "tasks": [...]
}
```

### Prompt de refinamento (chat)
```
Você é um especialista em BPMN 2.0. O usuário quer ajustar
um diagrama existente.

BPMN ATUAL:
{current_bpmn_xml}

HISTÓRICO DO CHAT:
{chat_history}

INSTRUÇÃO DO USUÁRIO:
{user_message}

Retorne o BPMN XML completo atualizado e uma breve descrição
do que foi alterado. Formato JSON:
{
  "bpmn_xml": "...",
  "change_description": "..."
}
```

---

## 8. Infraestrutura (Docker Compose)

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/bpmn_platform
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - WHISPER_MODEL=base
      - UPLOAD_DIR=/data/uploads
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - uploads:/data/uploads
    depends_on:
      - db

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=bpmn_platform
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  pgdata:
  uploads:
```

---

## 9. Segurança (MVP)

- JWT com expiração de 24h + refresh token
- Senhas com bcrypt (cost factor 12)
- Toda query filtrada por tenant_id (middleware)
- Rate limiting no upload de áudio (evitar abuso do Whisper)
- CORS configurado apenas para o frontend
- Variáveis sensíveis via .env (nunca no código)
- HTTPS obrigatório em produção

---

## 10. Roadmap do MVP

### Fase 1 — Foundation (semanas 1-2)
- [ ] Setup do monorepo (frontend + backend)
- [ ] Docker Compose funcional
- [ ] Banco de dados com migrations (Alembic)
- [ ] Autenticação (register, login, JWT)
- [ ] CRUD de projetos

### Fase 2 — Core pipeline (semanas 3-4)
- [ ] Upload de áudio + armazenamento
- [ ] Integração Whisper local (transcrição)
- [ ] Prompt engineering para geração BPMN
- [ ] Integração Claude API
- [ ] Pipeline completo: áudio → BPMN

### Fase 3 — Interface (semanas 5-6)
- [ ] Viewer BPMN com bpmn-js
- [ ] Chat de refinamento com IA
- [ ] Versionamento do BPMN
- [ ] Exportação (.bpmn para Camunda Modeler)

### Fase 4 — Polish (semanas 7-8)
- [ ] Documentação automática do processo
- [ ] Dashboard com métricas básicas
- [ ] Multi-tenant completo (convite de membros)
- [ ] Testes automatizados
- [ ] Deploy no servidor com DevOps

### Futuro (pós-MVP)
- Deploy automático no Camunda (via API/MCP)
- Suporte a múltiplos idiomas
- Templates de processos comuns
- Comparação visual entre versões
- Integrações (Slack, Teams, Google Drive)
- Planos e billing (Stripe)

---

## 11. Estrutura do repositório

```
bpmn-ai-platform/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── app/
│       ├── components/
│       ├── lib/
│       └── types/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/               # Migrations
│   ├── alembic.ini
│   └── app/
│       ├── main.py
│       ├── core/
│       ├── models/
│       ├── schemas/
│       ├── api/
│       ├── services/
│       └── workers/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 12. Decisões técnicas e trade-offs

**Por que Whisper local e não uma API?**
Zero custo. O modelo `base` roda em CPU (não precisa de GPU) e produz transcrições razoáveis em português. Se a qualidade não for suficiente, migra para `small` ou `medium` — ainda local e gratuito.

**Por que bpmn-js e não um editor custom?**
É a mesma biblioteca que o Camunda Modeler usa. Garante compatibilidade total com o ecossistema Camunda. É open-source (Camunda Community License) e amplamente documentado.

**Por que shared schema (tenant_id) e não schema-per-tenant?**
Com poucos clientes iniciais, shared schema é mais simples de manter. Toda query já filtra por tenant_id via middleware. Migramos para schemas isolados se necessário para compliance.

**Por que FastAPI e não Django/Flask?**
Async nativo (essencial para o pipeline de transcrição), tipagem forte com Pydantic, documentação OpenAPI automática, e integração natural com o ecossistema Python de IA.

**Por que não usar Celery desde o início?**
Para o MVP, BackgroundTasks do FastAPI é suficiente para processar um áudio por vez. Celery entra quando houver fila e múltiplos workers.
