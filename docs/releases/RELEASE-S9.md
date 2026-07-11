# Release Sprint 9 — Otimização de custo, latência e precisão do pipeline de IA

**Data:** 2026-07-11
**Sprint:** S9 (ad-hoc, fora do backlog planejado — sem `SPRINT-9-plano.md` correspondente; a Sprint 9 planejada em `docs/sprints/SPRINT-9-plano.md`, animação de fluxo/gargalos no BPMN, não foi tocada e será a próxima release numerada)
**Status:** Concluído (Fases 0–3 do plano; Fase 4 fica para depois de haver dados reais de produção)

## Resumo
Pedido direto para fechar o modelo de negócio: reduzir o custo por rodada do workflow (áudio → transcrição → BPMN → refinamento) e melhorar a precisão da modelagem, mantendo o provedor de IA atual. A exploração inicial revelou que o pipeline real usa **Google Gemini** (`google-genai`, modelo `gemini-flash-lite-latest`) em vez de Whisper/Claude como o `CLAUDE.md` descreve — decisão consciente de manter Gemini e não migrar. O trabalho ficou restrito ao "workflow core" (transcrição, geração, refinamento), sem tocar em documentação/sugestões de melhoria (fora do escopo pedido).

## Funcionalidades entregues

### Backend
- **[Fase 0]** `backend/app/services/llm_usage.py` (novo): extrai `usage_metadata` (tokens de prompt/saída/cache) de cada resposta do Gemini e loga custo estimado por etapa, processo e tentativa — instrumentação necessária para medir o efeito de qualquer otimização futura
- **[Fase 1]** `transcription.py`, `bpmn_generator.py`, `bpmn_refiner.py`: passam a usar `response_schema` (Pydantic) + `response_mime_type="application/json"` em vez de parser manual por regex; regras estáticas dos prompts migraram para `system_instruction` fixo entre chamadas (habilita cache implícito de prefixo no Gemini); `temperature` baixa nas três etapas
- **[Fase 1 — correção de bug real]** O retry do gerador (`bpmn_generator.py`) acumulava só turnos `user` e nunca anexava a resposta do modelo — o prompt de correção dizia "a resposta anterior estava incorreta" sobre uma resposta que o modelo nunca via. Retries agora são chamadas enxutas (XML inválido + erro do validador), sem acumular a conversa inteira
- **[Fase 2]** `core/config.py`: novos `GEMINI_MODEL_TRANSCRIPTION`/`GEMINI_MODEL_GENERATION`/`GEMINI_MODEL_REFINEMENT`, cada um com fallback para `GEMINI_MODEL` — permite trocar o modelo por etapa via `.env` sem alterar código
- **[Fase 3]** `backend/app/services/bpmn_layout.py` (novo): auto-layout determinístico em Python (BFS por níveis a partir dos `startEvent`, tolerante a loops de retrabalho/reprovação comuns em processos reais). O Gemini deixa de gerar coordenadas (`bpmndi:BPMNShape`/`BPMNEdge`) na **geração inicial** — devolve só os elementos semânticos do processo, cortando ~metade dos tokens de saída dessa etapa e eliminando sobreposição de formas por construção (grade sem colisão), em vez de depender do LLM seguir corretamente as regras de layout do prompt
- **[Fase 3 — decisão de escopo]** O auto-layout **não** entra no refinamento via chat: o endpoint `PUT /processes/:id/bpmn` permite edição manual do layout no bpmn-js, e recalcular tudo do zero a cada instrução de chat descartaria posições que o usuário ajustou manualmente. O refino continua pedindo XML completo (com layout) ao Gemini, já beneficiado pelas melhorias da Fase 1

### Testes
- Suíte de `bpmn_generator`, `bpmn_refiner` e `transcription` reescrita para mockar `response.parsed` (structured output) em vez de `response.text` + JSON manual
- `test_llm_usage.py` (novo): extração de tokens, estimativa de custo, desconto de cache, modelo desconhecido, `usage_metadata` ausente
- `test_bpmn_layout.py` (novo): injeção do diagrama, validade BPMN do resultado, namespaces DI, shape/edge por elemento, processo com ramificação sem sobreposição, **processo com loop de retrabalho não trava o cálculo**, remoção de diagrama pré-existente antes de injetar o novo, erro tratável em XML malformado ou sem elementos reconhecíveis

## Métricas
- Pontos planejados: 22 (Fases 0-3 do plano de otimização)
- Pontos entregues: 22 (Fase 4 — ajustes data-driven — depende de telemetria real em produção, não estimável ainda)
- Cobertura de testes (backend, `app/services/`): 97% — todos os arquivos tocados/criados em 95–100%
- Testes passando: 165/166 (1 skip, mesmo skip pré-existente de sempre)
- `ruff check`/`ruff format`: limpos em todos os arquivos tocados nesta release (débito técnico pré-existente em `bottleneck_analysis.py`/`documentation.py`/linha isolada de `bpmn_validator.py` não tocados, fora de escopo)

## O que ficou para a próxima sprint
- **Fase 4 (ajustes data-driven)**: com a instrumentação da Fase 0 rodando em produção por um tempo, reavaliar `max_retries` (reduzir se a 1ª tentativa passar a validar quase sempre), decidir se vale explicit context caching (só compensa em volume), e testar se o refinamento pode voltar para um modelo mais barato (flash-lite) agora que está mais enxuto
- Validação manual fim a fim com chave real do Gemini (corpus de 5-8 transcrições) para confirmar ganho de tokens/custo/latência na prática — só rodei testes unitários com mock, que provam a lógica mas não medem o efeito real em produção
- Sprint 9 planejada (`docs/sprints/SPRINT-9-plano.md`, animação de fluxo/gargalos no BPMN) segue não iniciada — vira a próxima release numerada (S10)

## Decisões técnicas tomadas nesta sprint
- Manter Google Gemini como provedor de IA, não migrar para Claude/Whisper apesar do `CLAUDE.md` mencioná-los — decisão do usuário, registrada aqui para não ser revertida por engano numa sessão futura que leia só o `CLAUDE.md`
- Prioridade de equilíbrio custo/precisão: cortar custo onde não afeta qualidade (structured output, caching de prefixo, retry enxuto) e investir precisão só onde mais importa (geração e refino do BPMN)
- Auto-layout em Python só na geração inicial, não no refino — evita descartar edições manuais de layout feitas pelo usuário via `PUT /processes/:id/bpmn` (ver seção de escopo acima)
- Layout calculado com BFS (nível = menor distância do `startEvent`) em vez de topological sort clássico — necessário porque processos reais de entrevista frequentemente têm loops de retrabalho/reprovação, que travariam um algoritmo que exige grafo acíclico

## Como testar esta release
1. `docker compose up -d --build` backend (nenhuma dependência de sistema nova, mas os arquivos de serviço mudaram)
2. `docker compose exec backend pytest -q` → 165 passed, 1 skipped
3. `docker compose exec backend pytest --cov=app.services --cov-report=term-missing -q` → confirmar `bpmn_generator.py`, `bpmn_layout.py`, `bpmn_refiner.py`, `transcription.py`, `llm_usage.py` em 95-100%
4. Teste manual (requer `GEMINI_API_KEY` real): subir um áudio de entrevista → conferir no log do backend as linhas `llm_usage stage=... estimated_cost_usd=...` para as 3 etapas → abrir o BPMN gerado no bpmn-js e confirmar que o diagrama renderiza sem formas sobrepostas → enviar uma instrução de refino no chat e confirmar que o layout muda de forma coerente
5. `docker compose exec backend ruff check app/services/` → limpo (ignorando os arquivos pré-existentes fora de escopo listados acima)

## Bugs conhecidos
- Nenhum bug novo introduzido por esta release, até onde os testes cobrem. O bug do retry do gerador (histórico não incluía a resposta do modelo) foi corrigido, não é um bug conhecido remanescente.
- Débito técnico pré-existente (não desta release, não regressão): 39 erros de `ruff` / 14 arquivos fora do padrão `black`, listados desde `RELEASE-S8.md`, ainda não tratados.
