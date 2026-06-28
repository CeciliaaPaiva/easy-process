# Plano de cobertura de testes — Plataforma BPMN com IA

## 1. Estratégia geral

### Pirâmide de testes

```
        ╱  E2E  ╲           → Poucos, lentos, alto valor
       ╱─────────╲          → Fluxos críticos do produto
      ╱ Integração╲         → Moderados, API + banco
     ╱─────────────╲        → Endpoints, pipeline, multi-tenant
    ╱    Unitários   ╲      → Muitos, rápidos, isolados
   ╱───────────────────╲    → Services, utils, schemas, componentes
```

| Nível | Proporção | Ferramentas | Execução |
|-------|-----------|-------------|----------|
| Unitário | ~60% | pytest, Vitest | A cada commit |
| Integração | ~30% | pytest + httpx + testcontainers | A cada PR |
| E2E | ~10% | Playwright | Antes de release |

### Meta de cobertura
- Backend: 80% mínimo (services e API)
- Frontend: 70% mínimo (componentes críticos)
- Pipeline core: 90% mínimo (é o coração do produto)

### Ferramentas

| Camada | Ferramenta | Uso |
|--------|-----------|-----|
| Backend unitário | pytest + pytest-asyncio | Testar services, utils, schemas |
| Backend integração | pytest + httpx.AsyncClient | Testar endpoints com banco real |
| Backend fixtures | factory-boy | Gerar dados de teste (Tenant, User, Project...) |
| Backend mock | unittest.mock + pytest-mock | Mockar Whisper e Claude API |
| Backend cobertura | pytest-cov | Relatório de cobertura |
| Frontend unitário | Vitest + React Testing Library | Componentes e hooks |
| Frontend E2E | Playwright | Fluxos completos no browser |
| Banco de teste | testcontainers (PostgreSQL) | Banco isolado por sessão de teste |
| CI | GitHub Actions | Rodar testes automaticamente |

---

## 2. Estrutura de diretórios de teste

### Backend
```
backend/
├── tests/
│   ├── conftest.py                    # Fixtures globais
│   ├── factories.py                   # Factory Boy (Tenant, User, Project...)
│   ├── fixtures/
│   │   ├── audio_sample_30s.wav       # Áudio curto para testes
│   │   ├── valid_bpmn.xml             # BPMN XML válido de referência
│   │   ├── invalid_bpmn.xml           # BPMN XML malformado
│   │   ├── transcription_sample.txt   # Transcrição de exemplo
│   │   └── claude_response_mock.json  # Resposta mockada da Claude API
│   ├── unit/
│   │   ├── test_security.py           # JWT, hashing
│   │   ├── test_bpmn_validator.py     # Validação de XML BPMN
│   │   ├── test_bpmn_generator.py     # Geração (com mock da API)
│   │   ├── test_bpmn_refiner.py       # Refinamento (com mock)
│   │   ├── test_transcription.py      # Transcrição (com mock do Whisper)
│   │   ├── test_storage.py            # Upload e filesystem
│   │   ├── test_documentation.py      # Geração de docs
│   │   └── test_schemas.py            # Validação Pydantic
│   ├── integration/
│   │   ├── test_auth_api.py           # Registro, login, refresh, me
│   │   ├── test_projects_api.py       # CRUD projetos
│   │   ├── test_processes_api.py      # Upload, status, BPMN
│   │   ├── test_chat_api.py           # Chat de refinamento
│   │   ├── test_export_api.py         # Exportação .bpmn
│   │   ├── test_tenant_isolation.py   # Segurança multi-tenant
│   │   └── test_pipeline.py           # Pipeline completo
│   └── e2e/
│       └── test_full_flow.py          # Registro → upload → BPMN → chat → export
```

### Frontend
```
frontend/
├── __tests__/
│   ├── components/
│   │   ├── BpmnViewer.test.tsx
│   │   ├── ChatWindow.test.tsx
│   │   ├── AudioUploader.test.tsx
│   │   └── ProjectCard.test.tsx
│   ├── hooks/
│   │   ├── useAuth.test.ts
│   │   └── useProcess.test.ts
│   ├── lib/
│   │   ├── api.test.ts
│   │   └── auth.test.ts
│   └── e2e/
│       ├── auth.spec.ts               # Playwright: login/registro
│       ├── project-flow.spec.ts       # Playwright: criar projeto
│       └── bpmn-pipeline.spec.ts      # Playwright: upload → BPMN → chat
```

---

## 3. Fixtures globais (conftest.py)

```python
# backend/tests/conftest.py

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.main import create_app
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password

# Banco de teste isolado (testcontainers ou SQLite async para velocidade)
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5433/test_db"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_session(engine):
    async with AsyncSession(engine) as session:
        async with session.begin():
            yield session
        await session.rollback()  # Rollback após cada teste

@pytest.fixture
async def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
async def tenant_and_user(db_session):
    """Cria tenant + user autenticado para testes."""
    tenant = Tenant(name="Test Corp", slug="test-corp")
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="test@test.com",
        password_hash=hash_password("test123"),
        name="Test User",
        role="admin"
    )
    db_session.add(user)
    await db_session.flush()

    token = create_access_token({"sub": str(user.id), "tenant_id": str(tenant.id)})
    return tenant, user, token

@pytest.fixture
def auth_headers(tenant_and_user):
    _, _, token = tenant_and_user
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_transcription():
    with open("tests/fixtures/transcription_sample.txt") as f:
        return f.read()

@pytest.fixture
def valid_bpmn_xml():
    with open("tests/fixtures/valid_bpmn.xml") as f:
        return f.read()

@pytest.fixture
def claude_mock_response():
    with open("tests/fixtures/claude_response_mock.json") as f:
        return json.load(f)
```

---

## 4. Testes unitários

### 4.1 Segurança (test_security.py)

| ID | Caso de teste | Input | Resultado esperado |
|----|--------------|-------|-------------------|
| SEC-01 | Criar access token válido | user_id, tenant_id | Token JWT decodificável com claims corretos |
| SEC-02 | Token expirado | token com exp no passado | Exceção de token expirado |
| SEC-03 | Token com assinatura inválida | token assinado com secret errado | Exceção de assinatura inválida |
| SEC-04 | Refresh token válido | user_id | Token com exp de 7 dias |
| SEC-05 | Hash de senha | "minha_senha" | Hash bcrypt irreversível |
| SEC-06 | Verificar senha correta | "minha_senha" + hash | True |
| SEC-07 | Verificar senha incorreta | "senha_errada" + hash | False |
| SEC-08 | Senha vazia | "" | Exceção ou False |

```python
# Exemplo
class TestSecurity:
    def test_create_access_token_contains_correct_claims(self):
        token = create_access_token({"sub": "user-123", "tenant_id": "tenant-456"})
        payload = verify_token(token)
        assert payload["sub"] == "user-123"
        assert payload["tenant_id"] == "tenant-456"
        assert "exp" in payload

    def test_expired_token_raises_error(self):
        token = create_access_token(
            {"sub": "user-123"},
            expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(TokenExpiredError):
            verify_token(token)

    def test_password_hash_is_not_reversible(self):
        hashed = hash_password("minha_senha")
        assert hashed != "minha_senha"
        assert verify_password("minha_senha", hashed) is True
        assert verify_password("outra_senha", hashed) is False
```

### 4.2 Validação de BPMN XML (test_bpmn_validator.py)

| ID | Caso de teste | Input | Resultado esperado |
|----|--------------|-------|-------------------|
| VAL-01 | XML bem-formado e BPMN válido | valid_bpmn.xml | is_valid = True |
| VAL-02 | XML malformado | string sem tags | is_valid = False, erro "XML malformado" |
| VAL-03 | XML válido mas não é BPMN | `<html>...</html>` | is_valid = False, erro "não é BPMN" |
| VAL-04 | BPMN sem startEvent | BPMN sem start | is_valid = False, erro "falta startEvent" |
| VAL-05 | BPMN sem endEvent | BPMN sem end | is_valid = False, erro "falta endEvent" |
| VAL-06 | BPMN com elementos desconectados | tasks sem sequenceFlow | is_valid = False, erro "elementos desconectados" |
| VAL-07 | BPMN vazio (só definitions) | `<definitions/>` | is_valid = False, erro "processo vazio" |
| VAL-08 | String vazia | "" | is_valid = False |

### 4.3 Geração de BPMN (test_bpmn_generator.py)

| ID | Caso de teste | Input | Resultado esperado |
|----|--------------|-------|-------------------|
| GEN-01 | Geração com transcrição válida | transcription_sample.txt | BPMN XML válido + summary + actors + tasks |
| GEN-02 | Resposta da API com JSON inválido | mock retorna texto livre | Exceção tratada, retry |
| GEN-03 | Resposta com BPMN malformado | mock retorna XML quebrado | Retry com prompt corretivo (até 3x) |
| GEN-04 | Transcrição vazia | "" | Exceção "transcrição vazia" |
| GEN-05 | Transcrição muito curta (< 50 chars) | "Olá, tudo bem?" | Exceção "transcrição insuficiente" |
| GEN-06 | Transcrição muito longa (> 50k chars) | texto enorme | Truncar e processar |
| GEN-07 | API retorna erro 429 (rate limit) | mock retorna 429 | Retry com backoff exponencial |
| GEN-08 | API retorna erro 500 | mock retorna 500 | Retry até 3x, depois erro ao usuário |
| GEN-09 | Timeout da API | mock demora 60s | Timeout com erro amigável |
| GEN-10 | Resultado contém actors e tasks | transcrição com múltiplos atores | actors é lista não-vazia; tasks é lista não-vazia |

```python
# Exemplo
class TestBpmnGenerator:
    @pytest.fixture
    def mock_claude_api(self, mocker, claude_mock_response):
        return mocker.patch(
            "app.services.bpmn_generator.call_claude_api",
            return_value=claude_mock_response
        )

    async def test_generates_valid_bpmn_from_transcription(
        self, mock_claude_api, sample_transcription
    ):
        service = BpmnGeneratorService()
        result = await service.generate(sample_transcription)

        assert result.bpmn_xml is not None
        assert result.bpmn_xml.startswith("<?xml")
        assert "<bpmn:startEvent" in result.bpmn_xml
        assert "<bpmn:endEvent" in result.bpmn_xml
        assert result.summary is not None
        assert len(result.actors) > 0
        assert len(result.tasks) > 0

    async def test_retries_on_invalid_xml(self, mocker, sample_transcription):
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"bpmn_xml": "<invalid>", "summary": "", "actors": [], "tasks": []}
            return claude_mock_response  # Válido na 3ª tentativa

        mocker.patch("app.services.bpmn_generator.call_claude_api", side_effect=side_effect)
        service = BpmnGeneratorService()
        result = await service.generate(sample_transcription)

        assert call_count == 3
        assert "<bpmn:startEvent" in result.bpmn_xml
```

### 4.4 Refinamento via chat (test_bpmn_refiner.py)

| ID | Caso de teste | Input | Resultado esperado |
|----|--------------|-------|-------------------|
| REF-01 | Instrução simples | "Adicione aprovação do gerente" + BPMN atual | BPMN atualizado com nova task |
| REF-02 | Instrução de remoção | "Remova a tarefa de envio" | BPMN sem a task removida |
| REF-03 | Instrução ambígua | "Melhore o processo" | BPMN retornado (IA interpreta) + change_description |
| REF-04 | BPMN de entrada vazio | "" + instrução | Exceção "BPMN inválido" |
| REF-05 | Histórico de chat preservado | 5 mensagens anteriores | Contexto mantido na resposta |

### 4.5 Transcrição (test_transcription.py)

| ID | Caso de teste | Input | Resultado esperado |
|----|--------------|-------|-------------------|
| TRS-01 | Áudio válido pt-BR | audio_sample_30s.wav | Texto não-vazio, language = "pt" |
| TRS-02 | Arquivo inexistente | "/path/nao_existe.wav" | Exceção "arquivo não encontrado" |
| TRS-03 | Arquivo corrompido | arquivo binário aleatório | Exceção tratada |
| TRS-04 | Áudio muito curto (< 1s) | 0.5s de silêncio | Texto vazio ou aviso |
| TRS-05 | Retorno inclui segmentos | audio válido | segments é lista com start, end, text |

### 4.6 Upload e storage (test_storage.py)

| ID | Caso de teste | Input | Resultado esperado |
|----|--------------|-------|-------------------|
| STO-01 | Upload .mp3 válido | arquivo .mp3, 5MB | Salvo em path correto, retorna path |
| STO-02 | Upload .wav válido | arquivo .wav | Salvo corretamente |
| STO-03 | Formato inválido (.exe) | arquivo .exe | Exceção "formato não suportado" |
| STO-04 | Arquivo > 100MB | arquivo grande | Exceção "arquivo muito grande" |
| STO-05 | Arquivo vazio (0 bytes) | arquivo vazio | Exceção "arquivo vazio" |
| STO-06 | Path isolado por tenant | tenant_id diferente | Diretórios separados no filesystem |
| STO-07 | Nome com caracteres especiais | "entrevista (1).mp3" | Sanitizado para nome seguro |

### 4.7 Schemas Pydantic (test_schemas.py)

| ID | Caso de teste | Input | Resultado esperado |
|----|--------------|-------|-------------------|
| SCH-01 | UserCreate válido | email, password, name | Schema válido |
| SCH-02 | Email inválido | "nao-e-email" | ValidationError |
| SCH-03 | Senha muito curta | "123" | ValidationError (min 6 chars) |
| SCH-04 | ProjectCreate sem nome | {} | ValidationError (name required) |
| SCH-05 | ProcessResponse serializa JSONB | actors como lista | JSON serializado corretamente |

---

## 5. Testes de integração

### 5.1 Auth API (test_auth_api.py)

| ID | Caso de teste | Endpoint | Resultado esperado |
|----|--------------|----------|-------------------|
| AUTH-01 | Registro com sucesso | POST /auth/register | 201, retorna tokens + user |
| AUTH-02 | Registro com email duplicado | POST /auth/register | 409, erro "email já existe" |
| AUTH-03 | Registro sem campo obrigatório | POST /auth/register | 422, validation error |
| AUTH-04 | Login com credenciais válidas | POST /auth/login | 200, retorna tokens |
| AUTH-05 | Login com senha errada | POST /auth/login | 401, erro "credenciais inválidas" |
| AUTH-06 | Login com email inexistente | POST /auth/login | 401, erro genérico (sem revelar se email existe) |
| AUTH-07 | Refresh token válido | POST /auth/refresh | 200, novo access token |
| AUTH-08 | Refresh token expirado | POST /auth/refresh | 401 |
| AUTH-09 | Acessar /me autenticado | GET /auth/me | 200, dados do usuário |
| AUTH-10 | Acessar /me sem token | GET /auth/me | 401 |
| AUTH-11 | Acessar /me com token inválido | GET /auth/me | 401 |

```python
# Exemplo
class TestAuthAPI:
    async def test_register_creates_tenant_and_user(self, client):
        response = await client.post("/api/v1/auth/register", json={
            "name": "João Silva",
            "email": "joao@empresa.com",
            "password": "senha123",
            "company_name": "Minha Empresa"
        })
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "joao@empresa.com"
        assert data["user"]["role"] == "admin"

    async def test_login_with_wrong_password_returns_401(self, client, tenant_and_user):
        response = await client.post("/api/v1/auth/login", json={
            "email": "test@test.com",
            "password": "senha_errada"
        })
        assert response.status_code == 401
```

### 5.2 Projects API (test_projects_api.py)

| ID | Caso de teste | Endpoint | Resultado esperado |
|----|--------------|----------|-------------------|
| PRJ-01 | Criar projeto | POST /projects | 201, retorna projeto |
| PRJ-02 | Listar projetos (com dados) | GET /projects | 200, lista com projetos do tenant |
| PRJ-03 | Listar projetos (vazio) | GET /projects | 200, lista vazia |
| PRJ-04 | Listar com paginação | GET /projects?page=2&per_page=5 | 200, paginação correta |
| PRJ-05 | Detalhe de projeto existente | GET /projects/:id | 200, dados do projeto |
| PRJ-06 | Detalhe de projeto inexistente | GET /projects/:id | 404 |
| PRJ-07 | Detalhe de projeto de outro tenant | GET /projects/:id | 404 (não 403, para não revelar existência) |
| PRJ-08 | Atualizar projeto | PUT /projects/:id | 200, dados atualizados |
| PRJ-09 | Deletar projeto (soft delete) | DELETE /projects/:id | 200, status = "archived" |
| PRJ-10 | Sem autenticação | GET /projects | 401 |

### 5.3 Processes API (test_processes_api.py)

| ID | Caso de teste | Endpoint | Resultado esperado |
|----|--------------|----------|-------------------|
| PRC-01 | Upload de áudio válido | POST /processes | 201, status = "pending" |
| PRC-02 | Upload formato inválido | POST /processes | 400, erro formato |
| PRC-03 | Consultar status pendente | GET /processes/:id | 200, status = "pending" |
| PRC-04 | Obter BPMN quando pronto | GET /processes/:id/bpmn | 200, XML retornado |
| PRC-05 | Obter BPMN quando não pronto | GET /processes/:id/bpmn | 400, "processo não está pronto" |
| PRC-06 | Exportar .bpmn | GET /processes/:id/export | 200, content-type application/xml |
| PRC-07 | Listar versões | GET /processes/:id/versions | 200, lista de versões |
| PRC-08 | Restaurar versão | POST /processes/:id/versions/:v/restore | 200, BPMN atualizado |
| PRC-09 | Atualizar BPMN manualmente | PUT /processes/:id/bpmn | 200, nova versão criada |

### 5.4 Chat API (test_chat_api.py)

| ID | Caso de teste | Endpoint | Resultado esperado |
|----|--------------|----------|-------------------|
| CHT-01 | Enviar instrução válida | POST /processes/:id/chat | 200, BPMN atualizado + nova versão |
| CHT-02 | Enviar mensagem vazia | POST /processes/:id/chat | 400, "mensagem vazia" |
| CHT-03 | Chat em processo não-ready | POST /processes/:id/chat | 400, "processo não está pronto" |
| CHT-04 | Histórico do chat | GET /processes/:id/chat | 200, lista ordenada por data |
| CHT-05 | Versão incrementada | POST /processes/:id/chat | version = anterior + 1 |

### 5.5 Tenant isolation (test_tenant_isolation.py)

| ID | Caso de teste | Cenário | Resultado esperado |
|----|--------------|---------|-------------------|
| ISO-01 | Tenant A não vê projetos de B | User A lista projetos | Apenas projetos do tenant A |
| ISO-02 | Tenant A não acessa processo de B | User A pede GET /processes/:id_de_B | 404 |
| ISO-03 | Tenant A não edita projeto de B | User A faz PUT /projects/:id_de_B | 404 |
| ISO-04 | Tenant A não deleta recurso de B | User A faz DELETE /projects/:id_de_B | 404 |
| ISO-05 | Tenant A não acessa chat de B | User A faz GET /processes/:id_de_B/chat | 404 |
| ISO-06 | Tenant A não exporta BPMN de B | User A faz GET /processes/:id_de_B/export | 404 |
| ISO-07 | SQL injection no tenant_id | tenant_id = "'; DROP TABLE" | Erro de validação UUID |

```python
# Exemplo
class TestTenantIsolation:
    async def test_tenant_a_cannot_see_tenant_b_projects(
        self, client, db_session
    ):
        # Criar tenant A com projeto
        tenant_a, user_a, token_a = await create_tenant_and_user(db_session, "A")
        project_a = await create_project(db_session, tenant_a.id, "Projeto A")

        # Criar tenant B com projeto
        tenant_b, user_b, token_b = await create_tenant_and_user(db_session, "B")
        project_b = await create_project(db_session, tenant_b.id, "Projeto B")

        # User A lista projetos: só vê o seu
        response = await client.get(
            "/api/v1/projects",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert response.status_code == 200
        projects = response.json()["items"]
        assert len(projects) == 1
        assert projects[0]["name"] == "Projeto A"

        # User A tenta acessar projeto de B: 404
        response = await client.get(
            f"/api/v1/projects/{project_b.id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert response.status_code == 404
```

### 5.6 Pipeline completo (test_pipeline.py)

| ID | Caso de teste | Cenário | Resultado esperado |
|----|--------------|---------|-------------------|
| PIP-01 | Pipeline end-to-end | Upload → transcrição → BPMN | status final = "ready", BPMN válido |
| PIP-02 | Falha na transcrição | Áudio corrompido | status = "error", mensagem descritiva |
| PIP-03 | Falha na geração BPMN | Mock da API retorna erro 3x | status = "error" após retries |
| PIP-04 | Pipeline com chat | Upload → BPMN → chat → nova versão | version = 2, BPMN diferente |

```python
# Exemplo
class TestPipeline:
    async def test_full_pipeline_audio_to_bpmn(
        self, client, auth_headers, db_session, mocker
    ):
        # Mock do Whisper
        mocker.patch(
            "app.services.transcription.TranscriptionService.transcribe",
            return_value=TranscriptionResult(
                text="O cliente envia o pedido, o vendedor analisa e aprova ou rejeita.",
                segments=[],
                language="pt",
                duration=30.0
            )
        )

        # Mock da Claude API
        mocker.patch(
            "app.services.bpmn_generator.call_claude_api",
            return_value=claude_mock_response
        )

        # 1. Criar projeto
        project = await client.post(
            "/api/v1/projects",
            json={"name": "Teste Pipeline"},
            headers=auth_headers
        )
        project_id = project.json()["id"]

        # 2. Upload de áudio
        with open("tests/fixtures/audio_sample_30s.wav", "rb") as f:
            response = await client.post(
                f"/api/v1/projects/{project_id}/processes",
                files={"audio": ("test.wav", f, "audio/wav")},
                data={"name": "Processo de Vendas"},
                headers=auth_headers
            )
        assert response.status_code == 201
        process_id = response.json()["id"]

        # 3. Aguardar pipeline (em teste, roda síncrono)
        await asyncio.sleep(1)

        # 4. Verificar resultado
        process = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth_headers
        )
        data = process.json()
        assert data["status"] == "ready"
        assert data["transcription"] is not None
        assert data["bpmn_xml"] is not None
        assert data["summary"] is not None
        assert len(data["actors"]) > 0

        # 5. Verificar BPMN é XML válido
        bpmn_response = await client.get(
            f"/api/v1/processes/{process_id}/bpmn",
            headers=auth_headers
        )
        bpmn_xml = bpmn_response.json()["bpmn_xml"]
        assert "<?xml" in bpmn_xml
        assert "<bpmn:startEvent" in bpmn_xml
```

---

## 6. Testes de frontend

### 6.1 Componentes (Vitest + React Testing Library)

| ID | Componente | Caso de teste | Resultado esperado |
|----|-----------|--------------|-------------------|
| FE-01 | AudioUploader | Renderiza área de drag-and-drop | Área visível com texto de instrução |
| FE-02 | AudioUploader | Aceita arquivo .mp3 | onUpload chamado com o arquivo |
| FE-03 | AudioUploader | Rejeita arquivo .exe | Mensagem de erro exibida |
| FE-04 | AudioUploader | Mostra progresso do upload | Barra de progresso visível |
| FE-05 | BpmnViewer | Renderiza BPMN XML válido | Canvas com elementos visíveis |
| FE-06 | BpmnViewer | Toolbar: zoom in/out | Nível de zoom altera |
| FE-07 | BpmnViewer | Toolbar: fit to screen | Diagrama centralizado |
| FE-08 | BpmnViewer | Toolbar: exportar .bpmn | Download disparado |
| FE-09 | ChatWindow | Renderiza histórico de mensagens | Mensagens user/assistant visíveis |
| FE-10 | ChatWindow | Envia mensagem | onSend chamado com texto |
| FE-11 | ChatWindow | Input vazio não envia | Botão desabilitado |
| FE-12 | ChatWindow | Loading state durante resposta | Indicador de typing visível |
| FE-13 | ProjectCard | Exibe nome e status | Texto e badge renderizados |
| FE-14 | ProjectCard | Click navega para projeto | Router push chamado |

### 6.2 Hooks

| ID | Hook | Caso de teste | Resultado esperado |
|----|------|--------------|-------------------|
| HK-01 | useAuth | Login armazena token | Token no estado, isAuthenticated = true |
| HK-02 | useAuth | Logout limpa token | Token removido, redirect para /login |
| HK-03 | useAuth | Refresh automático | Novo token antes da expiração |
| HK-04 | useProcess | Polling de status | Status atualizado periodicamente |
| HK-05 | useProcess | Para polling quando ready | clearInterval chamado |

### 6.3 E2E (Playwright)

| ID | Fluxo | Steps | Resultado esperado |
|----|-------|-------|-------------------|
| E2E-01 | Registro e login | Preencher form → submeter → dashboard | Redirect para /projects |
| E2E-02 | Criar projeto | Login → novo projeto → preencher → salvar | Projeto na lista |
| E2E-03 | Pipeline completo | Login → projeto → upload áudio → aguardar → ver BPMN | Diagrama renderizado |
| E2E-04 | Chat refinamento | Após BPMN pronto → enviar instrução → ver atualização | BPMN muda visualmente |
| E2E-05 | Exportar BPMN | Após BPMN pronto → clicar exportar | Arquivo .bpmn baixado |
| E2E-06 | Logout | Clicar logout → tentar acessar /projects | Redirect para /login |

---

## 7. Testes de segurança

| ID | Categoria | Caso de teste | Resultado esperado |
|----|----------|--------------|-------------------|
| SEG-01 | Autenticação | Request sem token em rota protegida | 401 Unauthorized |
| SEG-02 | Autenticação | Token de outro app (secret diferente) | 401 |
| SEG-03 | Autenticação | Token expirado | 401 com mensagem específica |
| SEG-04 | Autorização | User viewer tenta deletar projeto | 403 Forbidden |
| SEG-05 | Autorização | User analyst tenta gerenciar membros | 403 |
| SEG-06 | Isolamento | Acesso cross-tenant via ID direto | 404 |
| SEG-07 | Isolamento | Enumeration de IDs (UUIDs sequenciais) | UUIDs aleatórios, não enumeráveis |
| SEG-08 | Input | SQL injection nos parâmetros | Query parametrizada, sem efeito |
| SEG-09 | Input | XSS em nome do projeto | HTML escapado na resposta |
| SEG-10 | Upload | Arquivo com extensão mascarada (.exe renomeado para .mp3) | Validar magic bytes do arquivo |
| SEG-11 | Rate limit | 100 requests em 1 minuto no upload | 429 Too Many Requests |
| SEG-12 | CORS | Request de origem não autorizada | Bloqueado |

---

## 8. Mapeamento sprint × testes

| Sprint | Testes a implementar | Prioridade |
|--------|---------------------|-----------|
| Sprint 0 | Configurar pytest, conftest.py, factories, fixtures | Setup |
| Sprint 1 | SEC-01..08, AUTH-01..11, ISO-01..07, SEG-01..07 | Alta |
| Sprint 2 | VAL-01..08, GEN-01..10, TRS-01..05, STO-01..07, PRC-01..09, PIP-01..04 | Crítica |
| Sprint 3 | REF-01..05, CHT-01..05, FE-01..14, HK-01..05 | Alta |
| Sprint 4 | E2E-01..06, SEG-08..12, testes de documentação, revisão geral | Média |

---

## 9. CI (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd backend
          pip install -e ".[test]"

      - name: Lint
        run: |
          cd backend
          ruff check .
          black --check .
          mypy app/

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5433/test_db
          JWT_SECRET: test-secret
          ANTHROPIC_API_KEY: mock-key
        run: |
          cd backend
          pytest --cov=app --cov-report=xml --cov-fail-under=80 -v

      - name: Upload coverage
        uses: codecov/codecov-action@v4

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Lint
        run: |
          cd frontend
          npm run lint

      - name: Run tests
        run: |
          cd frontend
          npm run test -- --coverage --passWithNoTests

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Start services
        run: docker compose -f docker-compose.test.yml up -d
      - name: Run Playwright
        run: |
          cd frontend
          npx playwright install --with-deps
          npx playwright test
```

---

## 10. Métricas e relatórios

| Métrica | Ferramenta | Meta |
|---------|-----------|------|
| Cobertura de código (backend) | pytest-cov + Codecov | ≥ 80% |
| Cobertura de código (frontend) | Vitest coverage + Codecov | ≥ 70% |
| Cobertura do pipeline core | pytest-cov (services/) | ≥ 90% |
| Tempo de execução dos testes | CI logs | < 5 min (unit + integration) |
| Testes falhando no CI | GitHub Actions | 0 para merge em develop |
| Testes E2E passando | Playwright report | 100% para release |

### Comandos de cobertura
```bash
# Backend: relatório no terminal
make test-cov
# → pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# Backend: relatório HTML (abrir no browser)
make test-cov-html
# → pytest --cov=app --cov-report=html
# → open htmlcov/index.html

# Frontend
npm run test -- --coverage
```
