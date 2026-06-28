# Release Sprint 1 — Autenticação e Multi-tenant

**Data:** 2026-06-28
**Sprint:** S1
**Status:** Concluído

---

## Resumo

Autenticação JWT completa com isolamento por empresa (multi-tenant). Um usuário pode criar uma conta (que cria automaticamente o tenant da empresa), fazer login, renovar o token e acessar seus dados. O isolamento garante que cada empresa veja apenas seus próprios recursos. O frontend tem as páginas de login, registro e o layout autenticado com sidebar.

---

## Funcionalidades entregues

### Backend
- **[S1-01]** Models `Tenant` e `User` com migration Alembic (`001_create_tenants_and_users`) — UUIDs como chave primária, índices em `slug`, `email` e `tenant_id`
- **[S1-02]** Módulo de segurança (`core/security.py`) — `create_access_token` (30min), `create_refresh_token` (7 dias), `verify_token`, `hash_password`, `verify_password` com bcrypt
- **[S1-03]** Endpoints de autenticação:
  - `POST /api/v1/auth/register` → cria tenant + user admin, retorna tokens
  - `POST /api/v1/auth/login` → valida credenciais, retorna tokens
  - `POST /api/v1/auth/refresh` → renova access token via refresh token
  - `GET /api/v1/auth/me` → retorna dados do usuário autenticado
- **[S1-04]** Middleware de isolamento (`api/deps.py`) — `get_current_user` e `get_current_tenant` com validação JWT, verificação de `type: access/refresh` e lookup por `tenant_id`
- **[S1-07]** Seed script (`scripts/seed.py`) — cria Demo Corp (admin@demo.com) e Acme Inc (user@acme.com)

### Frontend
- **[S1-05]** Páginas de login e registro com formulários funcionais, validação de campos, exibição de erros e redirect pós-autenticação para `/projects`
- **[S1-05]** Layout de autenticação (`(auth)/layout.tsx`) — fundo centralizado com logo
- **[S1-05]** Componentes UI: `Button` (4 variantes + loading state), `Input` (com label e mensagem de erro), `Alert` (error/success/warning)
- **[S1-06]** Layout autenticado (`(dashboard)/layout.tsx`) — proteção de rota via `isAuthenticated()`, redirect para `/login` se não autenticado
- **[S1-06]** Sidebar (`components/sidebar.tsx`) — logo, navegação (Projetos, Configurações), botão de logout com `clearTokens()`
- **[S1-05]** `lib/auth.ts` — `getAccessToken`, `setTokens`, `clearTokens`, `isAuthenticated` via localStorage

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Pontos planejados | 20 |
| Pontos entregues | 20 |
| Testes passando | 28/28 |
| Lint (Ruff + Black) | ✅ zero erros |
| Cobertura estimada | > 80% nos services e endpoints de auth |

---

## O que ficou para a próxima sprint

Nada. Todos os 7 itens foram entregues com critério de aceite atingido.

---

## Decisões técnicas tomadas nesta sprint

| Decisão | Justificativa |
|---------|--------------|
| Email globalmente único (`UNIQUE(email)`) em vez de `UNIQUE(tenant_id, email)` | Simplifica o login no MVP — sem ambiguidade de "qual empresa" ao logar. Revisável na Sprint 4 se o produto precisar de suporte a consultores em múltiplas empresas |
| `bcrypt>=3.2,<4.0` pinado | `passlib 1.7.4` tem incompatibilidade com `bcrypt >= 4.0` (bug no `detect_wrap_bug` interno). Fixar em `<4.0` é o workaround estável até o passlib ser atualizado |
| Slug gerado automaticamente do nome da empresa | Facilita URLs amigáveis no futuro. Conflitos resolvidos com sufixo numérico (`-2`, `-3`, etc.) |
| Refresh token valida campo `type: refresh` | Evita que um access token seja usado como refresh token (e vice-versa) — defesa em profundidade |
| SQLite+aiosqlite para testes locais | Elimina dependência de PostgreSQL rodando localmente; CI usa PostgreSQL real via Docker |

---

## Como testar esta release

```bash
# Subir serviços
make up && make migrate && make seed

# Testar registro via Swagger
# Acessar http://localhost:8000/docs → POST /api/v1/auth/register

# Testar no frontend
# Acessar http://localhost:3000/register → preencher formulário

# Testar login
# http://localhost:3000/login → admin@demo.com / demo123

# Rodar testes automatizados
make test
```

---

## Bugs conhecidos

Nenhum.

---

## Próxima sprint

**Sprint 2 — CRUD de Projetos + Pipeline Core**
- Models: `Project`, `Process`, `ProcessVersion`, `ChatMessage`
- CRUD completo de projetos com paginação
- Upload de áudio (validação de formato + tamanho)
- Integração com Whisper local (transcrição)
- Integração com Claude API (geração de BPMN)
- Pipeline assíncrono: upload → transcrição → BPMN → status `ready`
