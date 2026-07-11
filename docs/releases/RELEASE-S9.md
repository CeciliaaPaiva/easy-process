# Release Sprint 9 — Otimização de custo/precisão do pipeline de IA + painel de administração de uso

**Data:** 2026-07-11
**Sprint:** S9 (ad-hoc, fora do backlog planejado — sem `SPRINT-9-plano.md` correspondente; a Sprint 9 planejada em `docs/sprints/SPRINT-9-plano.md`, animação de fluxo/gargalos no BPMN, não foi tocada por decisão do usuário e será a próxima release numerada, S10)
**Status:** Concluído (Fases 0–3 do plano de otimização + painel de admin de uso; Fase 4 do plano de otimização fica para depois de haver dados reais de produção)

## Resumo
Dois pedidos diretos encadeados nesta sprint: (1) reduzir o custo por rodada do workflow de IA (áudio → transcrição → BPMN → refinamento) e melhorar a precisão da modelagem, mantendo o provedor de IA atual; (2) construir um painel de administração para a própria dona da plataforma acompanhar gastos de tokens e outros dados operacionais. A exploração inicial do item 1 revelou que o pipeline real usa **Google Gemini** (`google-genai`, modelo `gemini-flash-lite-latest`) em vez de Whisper/Claude como o `CLAUDE.md` descreve — decisão consciente de manter Gemini e não migrar. O item 2 nasceu da instrumentação de custo já criada no item 1 (que antes só logava em stdout) — decidimos persistir esse uso em banco e expor via um painel simples restrito a admins.

## Funcionalidades entregues

### Backend — otimização do pipeline de IA (Fases 0-3)
- **[Fase 0]** `backend/app/services/llm_usage.py` (novo): extrai `usage_metadata` (tokens de prompt/saída/cache) de cada resposta do Gemini e loga custo estimado por etapa, processo e tentativa
- **[Fase 1]** `transcription.py`, `bpmn_generator.py`, `bpmn_refiner.py`: passam a usar `response_schema` (Pydantic) + `response_mime_type="application/json"` em vez de parser manual por regex; regras estáticas dos prompts migraram para `system_instruction` fixo entre chamadas (habilita cache implícito de prefixo no Gemini); `temperature` baixa nas três etapas
- **[Fase 1 — correção de bug real]** O retry do gerador (`bpmn_generator.py`) acumulava só turnos `user` e nunca anexava a resposta do modelo — o prompt de correção dizia "a resposta anterior estava incorreta" sobre uma resposta que o modelo nunca via. Retries agora são chamadas enxutas (XML inválido + erro do validador), sem acumular a conversa inteira
- **[Fase 2]** `core/config.py`: novos `GEMINI_MODEL_TRANSCRIPTION`/`GEMINI_MODEL_GENERATION`/`GEMINI_MODEL_REFINEMENT`, cada um com fallback para `GEMINI_MODEL` — permite trocar o modelo por etapa via `.env` sem alterar código
- **[Fase 3]** `backend/app/services/bpmn_layout.py` (novo): auto-layout determinístico em Python (BFS por níveis a partir dos `startEvent`, tolerante a loops de retrabalho/reprovação comuns em processos reais). O Gemini deixa de gerar coordenadas (`bpmndi:BPMNShape`/`BPMNEdge`) na **geração inicial** — devolve só os elementos semânticos do processo, cortando ~metade dos tokens de saída dessa etapa e eliminando sobreposição de formas por construção
- **[Fase 3 — decisão de escopo]** O auto-layout **não** entra no refinamento via chat: o endpoint `PUT /processes/:id/bpmn` permite edição manual do layout no bpmn-js, e recalcular tudo do zero a cada instrução de chat descartaria posições que o usuário ajustou manualmente. O refino continua pedindo XML completo (com layout) ao Gemini, já beneficiado pelas melhorias da Fase 1

### Backend — painel de administração de uso de tokens
- `backend/app/models/llm_usage_log.py` (novo) + `alembic/versions/003_create_llm_usage_logs.py`: nova tabela `llm_usage_logs` (tenant_id, process_id, stage, model, attempt, tokens de prompt/saída/cache/total, custo estimado, timestamp), com FKs para `tenants`/`processes` e índices em tenant/processo/etapa/data
- `llm_usage.py` ganhou `record_usage()` (async): loga (como antes) **e** persiste a linha de uso via sua própria sessão de banco (`AsyncSessionLocal`) — os 3 serviços de IA são singletons sem sessão de requisição, então persistir aqui evita threadear uma `AsyncSession` por todos eles. Falha ao persistir nunca derruba o pipeline (é instrumentação, não caminho crítico) e sem `tenant_id` (ex: chamadas diretas em teste) só loga, não persiste
- `transcription.py`, `bpmn_generator.py`, `bpmn_refiner.py`, `workers/process_audio.py`, `api/v1/processes.py` (endpoint de chat): passaram a threadear `tenant_id` (de `Process.tenant_id`, já existente) até o ponto de log de uso
- `backend/app/api/v1/admin.py` (novo) + `schemas/admin.py`: `GET /api/v1/admin/usage?days=30`, restrito a `role == "admin"` (mesmo papel já usado em `tenants.py` para gerenciar membros) e **sempre filtrado pelo `tenant_id` do usuário logado** — não existe visão cross-tenant, respeitando a regra de isolamento multi-tenant do projeto. Retorna totais gerais, quebra por etapa do pipeline, quebra por dia e as 50 chamadas mais recentes

### Frontend — painel de administração de uso de IA
- `src/app/(dashboard)/admin/usage/page.tsx` (novo): página com cards de totais (chamadas, tokens, custo estimado), tabela por etapa, tabela por dia e tabela de chamadas recentes; seletor de janela (7/30/90 dias); usuários não-admin veem mensagem de acesso negado em vez da página
- `src/components/sidebar.tsx`: novo item "Uso de IA" na navegação, visível apenas quando `GET /auth/me` retorna `role === "admin"`
- `src/lib/api.ts` + `src/types/index.ts`: novo `api.admin.usage(days)` e tipos `UsageSummary`/`UsageByStage`/`UsageByDay`/`UsageLogEntry`

### Testes
- Suíte de `bpmn_generator`, `bpmn_refiner` e `transcription` reescrita para mockar `response.parsed` (structured output) em vez de `response.text` + JSON manual
- `test_llm_usage.py`: extração de tokens, estimativa de custo, desconto de cache, modelo desconhecido, `usage_metadata` ausente, **e** `record_usage()` — persiste quando há `tenant_id`, pula persistência sem `tenant_id`, aceita string ou UUID, e não propaga exceção se o banco falhar
- `test_bpmn_layout.py`: injeção do diagrama, validade BPMN do resultado, namespaces DI, processo com ramificação sem sobreposição, **processo com loop de retrabalho não trava o cálculo**, erro tratável em XML malformado ou sem elementos reconhecíveis
- `test_admin_usage_api.py` (novo, integração): 401 sem autenticação, 403 para não-admin, totais/quebras corretos para admin, **isolamento entre tenants** (uso de outro tenant não aparece), filtro por `days` exclui logs antigos
- `conftest.py`: novo fixture `db_session` para testes que precisam seedar dados sem endpoint próprio (caso do `LlmUsageLog`, escrito só pelo pipeline de IA)
- Frontend: `page.test.tsx` (novo) para a página de admin — bloqueio para não-admin, renderização de totais e quebra por etapa para admin

## Métricas
- Pontos planejados: 22 (Fases 0-3 do plano de otimização) + ~5 (painel de admin, versão simples) = 27
- Pontos entregues: 27
- Cobertura de testes (backend, `app/services/`): 100% em todos os serviços tocados (`llm_usage.py`, `bpmn_generator.py`, `bpmn_refiner.py`, `transcription.py`); `bpmn_layout.py` em 95%
- Testes passando (backend): 174/175 (1 skip, mesmo skip pré-existente de sempre)
- Testes passando (frontend): 7/7 (5 pré-existentes + 2 novos da página de admin)
- `ruff check`/`ruff format` (backend): limpos em todos os arquivos tocados nesta release
- `tsc --noEmit` / `npm run lint` (frontend): limpos

## O que ficou para a próxima sprint
- **Fase 4 do plano de otimização (ajustes data-driven)**: com a instrumentação rodando em produção por um tempo, reavaliar `max_retries`, decidir se vale explicit context caching, testar modelo mais barato no refinamento
- Validação manual fim a fim com chave real do Gemini (corpus de 5-8 transcrições) para confirmar ganho de tokens/custo/latência na prática, e para popular o painel de admin com dados reais — está em andamento pela própria PO em paralelo a esta release
- Painel de admin — versão simples entregue (totais, por etapa, por dia, log recente). Ficou fora do escopo desta entrega, para uma v2 se fizer sentido: gráficos, filtro por processo/projeto específico, exportação (CSV), visão cross-tenant para uso interno da operadora da plataforma (hoje deliberadamente restrito ao próprio tenant do admin)
- Sprint 9 planejada (`docs/sprints/SPRINT-9-plano.md`, animação de fluxo/gargalos no BPMN) segue não iniciada — vira a próxima release numerada (S10)

## Decisões técnicas tomadas nesta sprint
- Manter Google Gemini como provedor de IA, não migrar para Claude/Whisper apesar do `CLAUDE.md` mencioná-los — decisão do usuário, registrada aqui para não ser revertida por engano numa sessão futura que leia só o `CLAUDE.md`
- Auto-layout em Python só na geração inicial, não no refino — evita descartar edições manuais de layout feitas pelo usuário via `PUT /processes/:id/bpmn`
- Layout calculado com BFS (nível = menor distância do `startEvent`) em vez de topological sort clássico — necessário porque processos reais de entrevista frequentemente têm loops de retrabalho/reprovação
- Painel de uso restrito ao **próprio tenant** do admin, não cross-tenant: o projeto tem regra inegociável de isolamento multi-tenant ("toda query filtra por tenant_id — sem exceção"); reusar o papel `admin` já existente (hoje usado para gerenciar membros do próprio tenant) mantém essa garantia sem criar um novo conceito de "super-admin da plataforma". Se a PO precisar de uma visão realmente cross-tenant no futuro, isso é uma escalada deliberada, não uma extensão natural deste endpoint
- Persistência de uso feita com sessão de banco própria (`AsyncSessionLocal`) dentro de `record_usage()`, em vez de passar uma `AsyncSession` de requisição pelos 3 serviços de IA (que são singletons instanciados sem contexto de requisição) — mesmo padrão já usado pelo worker de background do pipeline
- Falha ao persistir o log de uso nunca derruba a geração/refino do BPMN — é instrumentação, não caminho crítico

## Como testar esta release
1. `docker compose up -d --build` (backend e frontend mudaram)
2. `docker compose exec backend alembic upgrade head` → aplica a migration `003_create_llm_usage_logs`
3. `docker compose exec backend pytest -q` → 174 passed, 1 skipped
4. `docker compose exec backend pytest --cov=app.services --cov-report=term-missing -q` → confirmar serviços tocados em 95-100%
5. `docker compose exec frontend npx tsc --noEmit && npm run lint && npx vitest run` → limpo, 7/7 testes
6. Teste manual (requer `GEMINI_API_KEY` real, em andamento pela PO): subir um áudio de entrevista → conferir que o BPMN gerado não tem formas sobrepostas → enviar refino no chat → logar como o usuário admin (primeiro usuário de cada tenant é sempre admin) → abrir "Uso de IA" na sidebar → conferir que os totais/tabelas batem com o processo recém-criado
7. Testar isolamento: criar um segundo tenant e confirmar que `GET /api/v1/admin/usage` dele não mostra nenhum dado do primeiro
8. Testar permissão: convidar um membro com papel "viewer"/"analyst" e confirmar que `/admin/usage` retorna 403 e a página mostra a mensagem de acesso negado

## Bugs conhecidos
- Nenhum bug novo introduzido por esta release, até onde os testes cobrem. O bug do retry do gerador (histórico não incluía a resposta do modelo, de uma sessão anterior desta mesma sprint) já estava corrigido e segue coberto por teste.
- Débito técnico pré-existente (não desta release, não regressão): erros de `ruff` em `bottleneck_analysis.py`/`documentation.py`/`bpmn_validator.py`, listados desde `RELEASE-S8.md`, ainda não tratados — nenhum arquivo tocado nesta release está entre eles.
