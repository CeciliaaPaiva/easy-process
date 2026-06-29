# Release Sprint 2 — CRUD de Projetos + Pipeline Core

**Data:** 2026-06-29
**Sprint:** S2
**Status:** Concluído

## Resumo

Pipeline end-to-end funcional: upload de áudio → transcrição (Whisper) → geração de BPMN via Claude API. CRUD completo de projetos e processos com isolamento multi-tenant. 75 testes passando com 84% de cobertura.

## Funcionalidades entregues

### Backend

- **[S2-01]** Model `Project` + migration Alembic — tabela criada com FK para tenants, índice em `tenant_id`
- **[S2-02]** CRUD de projetos — `GET /projects`, `POST /projects`, `GET /projects/:id`, `PUT /projects/:id`, `DELETE /projects/:id` (soft delete → archived); paginação, busca por nome, isolamento por tenant
- **[S2-03]** Models `Process`, `ProcessVersion`, `ChatMessage` + migration — FKs, índices e server defaults corretos
- **[S2-04]** `StorageService` — validação de extensão e tamanho (100MB), salva em `/data/uploads/{tenant_id}/{process_id}/audio.{ext}`
- **[S2-05]** `TranscriptionService` — wrapper assíncrono do Whisper com singleton do modelo, retorna texto + segmentos + timestamps
- **[S2-06]** `BpmnGeneratorService` — prompt especializado para Claude API, validação XML com lxml, retry conversacional (preserva contexto da transcrição) até 3 tentativas
- **[S2-07]** Pipeline assíncrono (`process_audio_pipeline`) via `BackgroundTasks` — orquestra transcrição → geração BPMN → versioning; máquina de estados `pending → transcribing → generating → ready | error`
- **[Extra]** `GET /projects/:id/processes` — lista processos de um projeto (necessário para Sprint 3)
- **[Extra]** `GET /processes/:id/status` — endpoint leve de polling (retorna apenas `id`, `status`, `version`)
- **[Extra]** `ChatMessageResponse` schema — preparado para Sprint 3

## Métricas

- Pontos planejados: 20
- Pontos entregues: 20 + 2 extras
- Cobertura de testes: 84% (meta: 80%) ✅
- Cobertura `services/`: 92-96% (meta: 90%) ✅
- Testes passando: 75/75
  - Unitários: 29
  - Integração: 44 (auth, projetos, processos, pipeline, isolamento)

## O que ficou para a próxima sprint

- Frontend completo (Sprint 3): viewer BPMN com bpmn-js, chat de refinamento, upload com progresso
- Backend: endpoints de chat (`POST/GET /processes/:id/chat`) — Sprint 3
- Backend: `GET/POST /processes/:id/versions/:v` e restore — Sprint 3 (S3-07)
- Backend: documentação gerada pela IA — Sprint 4

## Decisões técnicas tomadas nesta sprint

- **Retry conversacional no BpmnGenerator:** em vez de substituir o prompt inteiro no retry, adiciona as mensagens anteriores ao histórico da conversa. Isso preserva o contexto da transcrição e permite que o Claude entenda o erro sem perder o contexto original.
- **Pipeline sem re-raise:** `process_audio_pipeline` captura exceções, registra em log e define `status = "error"`, mas não releva a exceção. Background tasks não devem propagar erros para a camada HTTP (a resposta já foi enviada).
- **Patch correto nos testes:** mock do pipeline nos testes de integração deve ser em `app.api.v1.processes.process_audio_pipeline` (local import binding), não em `app.workers.process_audio.process_audio_pipeline`.
- **Singleton do Whisper:** `TranscriptionService._model` como atributo de classe garante que o modelo (pesado, ~150MB) seja carregado uma vez por processo.

## Como testar esta release

```bash
# Subir serviços
make up

# Aplicar migrations
make migrate

# Rodar testes
DATABASE_URL="sqlite+aiosqlite:///./test_integration.db" make test

# Testar manualmente via Swagger
open http://localhost:8000/docs
# 1. POST /api/v1/auth/register
# 2. POST /api/v1/projects
# 3. POST /api/v1/projects/{id}/processes (multipart com áudio .mp3)
# 4. GET /api/v1/processes/{id}/status (polling até "ready")
# 5. GET /api/v1/processes/{id}/bpmn
# 6. GET /api/v1/processes/{id}/export
```

## Bugs conhecidos

- **Whisper não instalado no ambiente local:** `openai-whisper` não está no `pyproject.toml` (instalação separada por ser pesado). Em produção, instalar no Dockerfile: `pip install openai-whisper`. Em testes, sempre mockar `transcription_service.transcribe`.
- **ANTHROPIC_API_KEY obrigatório em produção:** sem a chave, o pipeline falha na etapa de geração BPMN com `AuthenticationError`. Definir em `.env`.
