# Release Sprint 12 — Pipeline em estágios (análise separada da modelagem)

**Data:** 2026-08-11
**Sprint:** S12
**Status:** Concluído

## Resumo

Reformulação estrutural do pipeline de geração de BPMN, motivada por um replanejamento pós-Sprint 11: a stakeholder confirmou que os problemas de qualidade de modelagem eram tanto "a IA nunca tenta um padrão" quanto "a IA tenta e erra o detalhe" — e trouxe a sugestão de um professor de quebrar o pipeline em estágios de IA separados (transcrição, análise, modelagem) em vez de um prompt único fazendo tudo. Essa sprint investigou a causa raiz com dados reais antes de decidir o que construir, implementou a decomposição, reforçou validação estrutural e fechou uma lacuna de coerência no painel de custo — e corrigiu um `CLAUDE.md` desatualizado que ainda descrevia Whisper/Claude API quando o produto usa Gemini há tempo.

## Funcionalidades entregues

### Investigação (S12-01)
- **[S12-01]** 6 transcrições reais do banco de dev (não fixtures sintéticas) rodadas contra o `BpmnGeneratorService` **antes de qualquer mudança de código** — baseline real, não hipótese. Achado dominante: pools/raias para atores externos nunca eram criados (5 de 6 casos tinham ator externo claro na transcrição, 0 viraram `bpmn:participant`), mesmo quando a análise já identificava o ator corretamente — confirmando que o problema era estrutural, na tradução para XML, não na compreensão do processo. Achado secundário: um `parallelGateway` de divisão saiu com uma única saída. Tipagem de atividade já funcionava bem (não era gargalo). Documentado em `docs/sprints/SPRINT-12-investigacao.md`.

### Backend — decomposição do pipeline (S12-02)
- **[S12-02]** `app/services/bpmn_analysis.py` (novo): lê a transcrição, devolve um grafo JSON tipado — atores classificados interno/externo, atividades com tipo de execução, gateways com tipo/papel, transições explícitas (`flows`), anotações. Validação estrutural própria (ids únicos, `responsible` batendo com `actors`, grafo alcançável a partir de `start`) com retry corretivo — não depende só de regra de prompt.
- **[S12-02]** `app/services/bpmn_generator.py` (reescrito): recebe o grafo já resolvido, só traduz para XML — não reinterpreta o processo. `summary`/`actors`/`tasks` vêm direto da análise (Python), sem pedir de novo ao LLM de modelagem — menos tokens de saída.
- **[S12-02]** `core/config.py`: novo `GEMINI_MODEL_ANALYSIS` (fallback para `GEMINI_MODEL`, mesmo padrão dos outros estágios).
- **[S12-02]** `record_usage` agora loga `stage="bpmn_analysis"` e `stage="bpmn_modeling"` (antes: `"bpmn_generation"` único) — painel "Uso de IA" mostra o breakdown por etapa sem nenhuma mudança de frontend além dos rótulos (`stageLabels`).

### Backend — validação estrutural (S12-03)
- **[S12-03]** `bpmn_validator.py::validate_external_actors_have_pools`: reprova (dispara retry corretivo) quando um ator externo da análise não tem `bpmn:participant` correspondente no XML — regra de prompt sozinha já existia e já era ignorada na prática, só validação estrutural resolve.
- **[S12-03]** `bpmn_validator.py::_find_pointless_gateway`: reprova gateway com exatamente 1 entrada e 1 saída (não decide nem junta nada) — regressão direta do bug de nuance achado em S12-01, mesmo padrão do fix do gateway combinado (S10, `2e7f53f`).

### Backend — ajuste de prompt (S12-04)
- **[S12-04]** 1 exemplo concreto (ERRADO/CERTO) adicionado ao prompt de análise, contrastando o bug de gateway com saída única. Escopo pontual — S12-01 não achou evidência de erro de nuance generalizado fora desse padrão específico.

### Backend — coerência do painel de custo (S12-05)
- **[S12-05]** `llm_usage.py::extract_usage` loga `logger.warning` quando `model_name` não está na tabela de preços hardcoded, em vez de cair em custo $0 silencioso. `CLAUDE.md` ganhou seção documentando quando atualizar a tabela.

### Documentação
- **[Achado, corrigido nesta sprint]** `CLAUDE.md` descrevia Whisper (transcrição) e Claude API (geração) — desatualizado desde a S9, que já havia migrado tudo para Gemini e registrado a decisão só em `RELEASE-S9.md`, sem atualizar o documento principal. Corrigido: stack, pipeline, riscos, testes e decisões técnicas agora refletem Gemini em todas as três etapas.

## Validação contra a API real (não só testes com mock)

Cada etapa foi validada com uma chamada real ao Gemini antes de ser dada como concluída, além dos testes automatizados com mock:

- **S12-02**: mesmo caso da investigação ("pedido pelo app") rodado de novo com o pipeline novo — saiu de 0 para 4 `bpmn:participant` (3 pools externos + raia interna), gateways corretamente pareados split/join, 2 anotações, 2 `endEvent` distintos.
- **S12-04**: mesmo caso rodado uma terceira vez após o ajuste de prompt — os 5 gateways saíram todos corretos já na primeira tentativa (nenhum 1-entrada-1-saída), sem precisar do retry de segurança de S12-03.

## Trade-off encontrado — custo por processo

A decomposição em duas chamadas de IA (análise + modelagem) praticamente dobrou o custo por processo no caso testado: ~$0,0036 vs. ~$0,0009 da chamada única antiga. É centavos em valor absoluto, mas era um risco já registrado no plano original e se confirmou na prática, não ficou só hipótese. **Não corrigido nesta sprint** — decisão consciente de priorizar a correção de qualidade primeiro e validar com a stakeholder se compensa. Candidato de otimização já identificado: a etapa de modelagem ficou quase mecânica (traduz um grafo já resolvido, não decide mais semântica) — pode ser candidata a um modelo mais barato (mesmo tier já usado na transcrição) sem perda de qualidade, a testar numa sprint futura.

## Métricas
- Pontos planejados/entregues: 15 (S12-01: 3, S12-02: 5, S12-03: 5, S12-04: 1, S12-05: 1)
- Testes passando: 202/203 (1 skipped) — 14 testes novos nesta sprint (`test_bpmn_analysis.py` inteiro, novos em `test_bpmn_generator.py`, `test_bpmn_validator.py`, `test_llm_usage.py`)
- `ruff`/`black`: limpos nos arquivos tocados (débito pré-existente em `tenants.py`/arquivos de teste, já registrado desde `RELEASE-S8.md`, não tocado nesta sprint)
- `mypy`: nenhuma categoria de erro nova introduzida — mesmo padrão de débito pré-existente do SDK do Gemini (`response.parsed` tipado como união solta), já presente em `bpmn_refiner.py`/`transcription.py` antes desta sprint

## O que ficou para a próxima sprint
- Decisão sobre o trade-off de custo do S12-02 (rebaixar modelo da etapa de modelagem, ou aceitar o custo maior pela qualidade ganha) — a confirmar com a stakeholder.
- Observabilidade de eficiência por etapa **na UI do admin** (comparar custo/qualidade entre análise e modelagem visualmente) — decidido esperar a decomposição rodar em produção antes de desenhar essa tela.
- Servidor MCP de observabilidade do pipeline (ferramenta de dev, não de produto) — projeto paralelo sob demanda, ainda não iniciado.
- **Edição manual do diagrama** — promovida para item único da Sprint 13 (antes era item único desta sprint), viabilidade ainda a discutir no kickoff.

## Decisões técnicas tomadas nesta sprint
- Análise e modelagem como duas chamadas de IA separadas (não uma etapa de IA + uma etapa determinística em código) — decisão deliberada de manter a etapa de modelagem como chamada de IA mesmo o grafo já sendo bem estruturado, porque é literalmente a técnica que a stakeholder queria aprender/aplicar (sugestão do professor dela); uma tradução 100% determinística em Python teria sido mais barata e confiável, mas não seria "aplicar a ideia", seria substituí-la silenciosamente.
- Grafo de análise como `flows` (lista de arestas `source_id`/`target_id`/`label`) em vez de uma árvore ou lista de passos sequencial — representação mais simples e menos ambígua pro LLM produzir e pro código consumir, cobre ramificação/paralelismo/loops sem estrutura especial.
- IDs especiais reservados `"start"`/`"end"`/`"end:<motivo>"` no grafo — evita inventar um schema separado só pra eventos de início/fim, e já cobre o caso real de múltiplos motivos de término (ex: "pedido cancelado" vs. "pedido entregue") encontrado na investigação.
- `summary`/`actors`/`tasks` derivados em Python a partir do resultado da análise, não pedidos de novo à IA de modelagem — reduz tokens de saída e elimina risco de divergência entre o que a análise decidiu e o que a modelagem "lembra".
- Validação de pool ausente comparando nomes de ator por substring case-insensitive, não exigindo igualdade exata — tolera pequena variação de fraseado entre a etapa de análise e o texto que a modelagem usa no atributo `name` do participant.
- Alerta de modelo fora da tabela de preços é `logger.warning`, não exceção — mesma filosofia já estabelecida no código (`record_usage`: "instrumentação, não caminho crítico") de nunca deixar telemetria de custo derrubar o pipeline de produto.

## Como testar esta release
1. `docker compose up -d --build` e `docker compose exec backend alembic upgrade head` (sem migration nova nesta sprint, mas confirma que nada quebrou)
2. `docker compose exec backend pytest -q` → 202 passed, 1 skipped
3. Gerar um processo novo com um áudio/transcrição que descreva um processo com pelo menos um ator externo (cliente, fornecedor, sistema de terceiros) e um ponto de decisão → abrir o BPMN gerado e confirmar que o ator externo aparece como `bpmn:participant` separado
4. Como platform admin, abrir "Uso de IA" → confirmar duas linhas na tabela "Por etapa do pipeline": "Análise" e "Modelagem BPMN", em vez de uma "Geração BPMN" única
5. `docker compose exec backend pytest tests/unit/test_bpmn_validator.py tests/unit/test_bpmn_analysis.py tests/unit/test_llm_usage.py -v` → conferir os testes de regressão específicos desta sprint

## Bugs conhecidos
- Nenhum bug novo em aberto no escopo desta sprint.
- Custo por processo ~2x maior que antes da decomposição (ver "Trade-off encontrado" acima) — não é um bug, é uma decisão consciente pendente de validação com a stakeholder.
- Débito técnico pré-existente (não desta release): erros de `ruff` em arquivos de teste e em `tenants.py`, já registrados desde `RELEASE-S8.md`/`RELEASE-S10.md`/`RELEASE-S11.md`; padrão de `mypy` `response.parsed` solto do SDK do Gemini, presente desde antes desta sprint em `bpmn_refiner.py`/`transcription.py`.
