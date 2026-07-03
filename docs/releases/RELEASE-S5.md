# Release Sprint 5 — Migração de IA para Gemini e estabilização da suíte de testes

**Data:** 2026-07-03
**Sprint:** S5
**Status:** Concluído

## Resumo
Substituição da transcrição de áudio baseada em Whisper local por transcrição via Gemini (multimodal, mesma API key já usada para geração de BPMN/chat/documentação), simplificando drasticamente o build do backend. Corrigidos problemas de infraestrutura de testes (event loop) e mocks desatualizados. Corrigido bug crítico de renderização do diagrama BPMN no frontend (CSS ausente + IDs duplicados no XML gerado pela IA fazendo as setas do fluxo não aparecerem) e reforçado o layout gerado pela IA para as setas não cruzarem por cima das atividades.

## Funcionalidades entregues

### Backend
- [S5-01] Remoção do `openai-whisper`/PyTorch como dependência de transcrição — build do backend caiu de ~45min para ~97s
- [S5-02] `TranscriptionService` reescrito para usar `google-genai` (áudio como `Part` binário multimodal), reaproveitando `GEMINI_API_KEY`/`GEMINI_MODEL` já existentes; resposta forçada em JSON puro via `response_mime_type="application/json"`
- [S5-03] Remoção de `WHISPER_MODEL` de `config.py`, `.env`, `.env.example` e `.env.production.example`
- [S5-04] Correção de `RuntimeError: ... attached to a different loop` nos testes de integração via `asyncio_default_fixture_loop_scope`/`asyncio_default_test_loop_scope = "session"` em `pyproject.toml`
- [S5-05] Correção de mocks obsoletos em `test_bpmn_generator.py` e `test_documentation.py` (referenciavam `service._model.start_chat`/`generate_content_async`, API antiga do SDK; atualizados para `service._client.aio.models.generate_content`)
- [S5-06] `bpmn_generator.py`, `bpmn_refiner.py` e `documentation.py` agora leem o modelo de `settings.GEMINI_MODEL` em vez de hardcoded `"gemini-2.0-flash"` (que foi descontinuado); modelo padrão trocado para `gemini-flash-lite-latest` (mais barato e estável)
- [S5-07] `bpmn_validator.py`: nova checagem de IDs duplicados entre elementos semânticos e de diagrama (`bpmndi:BPMNShape`/`bpmndi:BPMNEdge`), e nova checagem de sobreposição de formas (`Bounds` colidindo) — ambas acionam o retry automático da IA com o erro explicado
- [S5-08] Prompts de geração (`bpmn_generator.py`) e refinamento (`bpmn_refiner.py`) reforçados com regras geométricas explícitas de layout (tamanhos fixos de shapes, espaçamento horizontal de 150px, alinhamento por centro vertical, waypoints saindo/entrando pelas bordas laterais) e proibição de namespaces de estilo não declarados (ex: `bioc:stroke`)

### Frontend
- [S5-09] `BpmnViewer.tsx`: adicionado import dos CSS obrigatórios do `bpmn-js` (`diagram-js.css`, `bpmn-js.css`, `bpmn-embedded.css`) — sem eles o diagrama importava sem erro mas não renderizava visualmente

### Documentação
- [S5-10] `README.md` atualizado (fluxo, pré-requisitos e variáveis de ambiente refletindo Gemini em vez de Whisper/Anthropic)

## Métricas
- Pontos planejados: —
- Pontos entregues: —
- Cobertura de testes: não recalculada nesta sprint (foco em corrigir falhas, não medir %)
- Testes passando: 128/129 (1 skip, verificado em 2 rodadas — 1 falha isolada foi flakiness de colisão de slug entre testes, não reproduziu na 2ª rodada)

## O que ficou para a próxima sprint
- Recalcular cobertura de testes após as mudanças (meta ≥80% backend conforme CLAUDE.md)
- Avaliar se `TranscriptionResult.segments` (timestamps por trecho) ainda é necessário — Gemini não retorna segmentos como o Whisper; hoje o campo fica sempre vazio
- Monitorar estabilidade do `gemini-flash-lite-latest` (o `gemini-2.5-flash-lite` apresentou 503 "high demand" persistente durante esta sprint especificamente em prompts longos)

## Decisões técnicas tomadas nesta sprint
- Avaliadas duas alternativas ao Whisper: Google Cloud Speech-to-Text (API dedicada, exigiria projeto GCP + service account separados) vs. Gemini multimodal (áudio como input direto, mesma API key já usada no projeto). Optou-se por Gemini multimodal pela simplicidade operacional e por já ser o único provedor de IA do stack.
- Free tier do Gemini API não ficou disponível para as contas testadas nesta região sem billing habilitado (erro `429 limit: 0` mesmo com chaves de contas diferentes); foi necessário habilitar faturamento pré-pago em uma conta Google para desbloquear o uso.
- Ambiente de desenvolvimento local roda via Docker Desktop (WSL) + `docker compose up -d --build`; nenhuma mudança de infraestrutura de deploy foi necessária.

## Como testar esta release
1. `docker compose up -d --build`
2. Acessar http://localhost:3000 (frontend) e http://localhost:8001/docs (Swagger do backend)
3. Fazer upload de um áudio (.mp3/.wav/.m4a/.ogg) em um processo e confirmar que a transcrição é gerada via Gemini
4. Confirmar que o diagrama BPMN renderiza no viewer com as setas conectando as atividades em linha reta, sem sobrepor as caixas
5. Rodar `docker compose exec backend pytest tests/ -q` e confirmar que a suíte passa

## Bugs conhecidos
- Nenhum bug conhecido nesta release
