# Plano Sprint 12 — Pipeline em estágios (análise separada da modelagem)

**Status:** Planejada, não iniciada (depende da conclusão da Sprint 11 — concluída)

## Contexto

Reunião de replanejamento após a Sprint 11: a stakeholder confirma que os problemas de qualidade de modelagem (gateways do tipo errado, pools/raias ausentes, sem anotações, sem diferenciar atividade manual/usuário/sistema) são **os dois casos ao mesmo tempo** — a IA às vezes não tenta um padrão (regra ausente) e às vezes tenta e erra o detalhe (nuance). Isso muda o enquadramento do problema em relação ao plano original desta sprint.

Um professor da stakeholder sugeriu quebrar o pipeline de IA em estágios separados — transcrição, análise, modelagem — em vez de um prompt único fazendo análise e modelagem juntas. Investigamos o código antes de planejar (evita estimar no escuro):

| Achado | Onde está hoje |
|---|---|
| Transcrição já é uma etapa isolada | `transcription.py`, chamada própria à Gemini API, sem Whisper (o `CLAUDE.md` estava desatualizado nisso — corrigido nesta sprint) |
| Análise e modelagem estão fundidas numa chamada só | `bpmn_generator.py::generate()` pede pro Gemini, numa única chamada: "1. XML BPMN válido, 2. resumo, 3. atores, 4. tarefas" — a etapa que exige mais raciocínio semântico (identificar tipo de gateway, pool vs. raia, tipo de atividade) compete por atenção do modelo com a etapa mais mecânica (produzir XML bem formado). É a causa raiz mais provável do "não analisa bem **e** não modela bem" |
| Infra pra modelo por etapa já existe | `core/config.py` já tem `GEMINI_MODEL_TRANSCRIPTION`/`_GENERATION`/`_REFINEMENT`, cada um com fallback — só falta a etapa "análise" existir separada de "geração" pra ter seu próprio modelo configurável |
| Painel "Uso de IA" usa dados reais | `llm_usage.py::extract_usage` lê `usage_metadata` de cada resposta real do Gemini (tokens de prompt/saída/cache) e calcula custo por uma tabela de preços por modelo, persistido em `LlmUsageLog` por chamada — não há número fabricado. Único risco: a tabela de preços é hardcoded e não vem de API, fica desatualizada se o Gemini mudar preço sem aviso (confirmado durante esta investigação, não corrigido ainda) |

**Fora do escopo desta sprint, por decisão explícita:** observabilidade de eficiência por etapa **na UI do admin** (ex: comparar custo/qualidade entre análise e modelagem) fica pra depois — vale a pena esperar a decomposição existir de verdade antes de desenhar essa tela. Um servidor MCP separado, só pra uso interno de desenvolvimento (consultar `LlmUsageLog`/versões de BPMN direto do Claude Code, sem UI), foi decidido como projeto paralelo sob demanda — não consome pontos desta sprint por não ser feature de produto.

## Backlog

| Item | Descrição | Pontos |
|---|---|---|
| S12-01 | **Investigação com casos reais.** Rodar de 5 a 8 transcrições reais e variadas (múltiplos atores, gateways de tipos diferentes, pelo menos um caso que deveria gerar pool externo/caixa preta) contra o pipeline atual (antes de qualquer mudança). Catalogar por padrão: "IA nunca tenta" vs. "IA tenta e erra a nuance" — essa distinção muda o peso relativo de S12-03 (estrutural) vs. S12-04 (prompt/few-shot) abaixo. | 3 |
| S12-02 | **Separar "análise" de "modelagem" como duas chamadas distintas ao Gemini.** Novo serviço `bpmn_analysis.py`: recebe a transcrição, devolve um JSON estruturado (schema Pydantic) com atores, atividades **com tipo** (manual/usuário/sistema), pontos de decisão e o tipo de gateway correspondente, pools/raias sugeridas, regras de negócio — sem gerar XML. `bpmn_generator.py` deixa de receber a transcrição bruta e passa a receber esse JSON já estruturado, com uma responsabilidade só: traduzir a análise em XML BPMN válido. Cada etapa loga em `record_usage` com seu próprio `stage` (`"analysis"`, `"modeling"`, em vez do `"generation"` único de hoje) — o painel "Uso de IA" já mostra o breakdown por etapa sem mudança nenhuma nele, porque a agregação já é por `stage`. | 5 |
| S12-03 | **Reforçar `bpmn_validator.py` com checagens estruturais para os padrões "IA nunca tenta" encontrados em S12-01.** Mesmo padrão já usado pro bug do gateway combinado (fix em `2e7f53f`, S10): regra de prompt sozinha não impede a IA de esquecer de novo — a validação com retry corretivo (já existe no pipeline, até 3x) garante que o JSON de análise (agora validável antes mesmo de virar XML) não tenha o padrão ausente. | 5 |
| S12-04 | **Ajustar prompt de análise conforme os padrões "erra a nuance" encontrados em S12-01.** Se o problema for a IA "esquecendo" a regra em transcrições mais longas/complexas, considerar few-shot concreto (transcrição de exemplo → JSON de análise esperado) em vez de só regra descritiva — few-shot geralmente performa melhor que instrução pura pra modelos "lite" como os usados hoje. Escopo menor que o original porque agora só precisa ajustar o prompt de análise (JSON), não mais o prompt que também tinha que se preocupar em não quebrar XML. | 2 |
| S12-05 | **Corrigir a tabela de preços hardcoded de `llm_usage.py` e documentar o processo de atualização.** Achado durante a investigação desta sprint: `_PRICING_PER_MILLION` não vem de API, é mantida à mão — se o Gemini mudar preço (já aconteceu 2x na S9, segundo `RELEASE-S9.md`), o painel "Uso de IA" fica silenciosamente incoerente sem ninguém perceber. Adicionar um teste que falha se `record_usage` for chamado com um `model_name` fora da tabela (hoje cai silenciosamente em `(0.0, 0.0)` — custo zero mentiroso), e documentar no `CLAUDE.md` o processo de conferir a tabela oficial do Gemini periodicamente. | 1 |

**Total: 16 pontos**

## Ordem sugerida dentro da sprint

1. **S12-01 primeiro, sempre** — os outros itens dependem do que for encontrado; começar S12-02/03/04 antes seria arriscar retrabalho.
2. **S12-02 logo em seguida** — é a mudança estrutural que o restante do backlog pressupõe (S12-03 valida o JSON de análise, que só existe depois de S12-02 existir).
3. S12-03 e S12-04 podem correr em paralelo depois de S12-02 pronto, cada um atacando a categoria de erro correspondente encontrada em S12-01.
4. S12-05 é independente, pode entrar em qualquer ponto da sprint — item pequeno, achado à parte.

## Decisão em aberto — confirmar no kickoff

A resposta de S12-01 confirma que os dois tipos de erro coexistem, então **os dois** S12-03 (estrutural) e S12-04 (few-shot) provavelmente entram — a única decisão real em aberto é a proporção de esforço entre eles, que só dá pra calibrar depois de ver a distribuição real dos achados de S12-01 (ex: se 80% dos erros forem "nunca tenta", vale mais reforçar validação estrutural do que few-shot).

## Como testar (planejado)

1. Rodar os mesmos 5-8 casos de S12-01 depois das mudanças → comparar taxa de acerto antes/depois por padrão
2. `docker compose exec backend pytest tests/unit/test_bpmn_analysis.py tests/unit/test_bpmn_validator.py tests/unit/test_bpmn_generator.py -v` → cobertura da etapa nova + regressão das checagens estruturais
3. Gerar um processo do zero → confirmar no painel "Uso de IA" que aparecem **duas** linhas na tabela "Por etapa do pipeline" (`analysis` e `modeling`) em vez de uma (`generation`) — sem precisar tocar no frontend, só validando que o breakdown por `stage` já existente reflete a mudança de backend
4. Forçar um `model_name` fora da tabela de preços em teste → confirmar que o novo teste de S12-05 falha (em vez de custo zero silencioso)

## Riscos

- Separar em duas chamadas dobra a latência do pipeline de geração (duas idas e voltas à API em vez de uma) — aceitável pra este produto (processamento já é assíncrono/background, usuário não fica esperando na tela), mas vale medir o tempo real em S12-01/02 pra não surpreender depois.
- Separar em duas chamadas também pode aumentar o custo por processo (mais tokens de sistema/instrução repetidos entre as duas chamadas) — o Gemini tem cache implícito de prefixo (já habilitado desde a S9 via `system_instruction` fixo) que deveria mitigar isso, mas vale confirmar com números reais do painel "Uso de IA" depois do deploy, não só assumir.
- Se S12-01 revelar que um dos dois tipos de erro é raro na prática, a estimativa de S12-03 ou S12-04 deve ser revisitada no meio da sprint, não só no kickoff — mesma lógica de escopo incremental já usada em sprints anteriores.

## O que ficou fora desta sprint (backlog futuro)

- **Observabilidade de eficiência por etapa na UI do admin** (comparar custo/tempo/qualidade entre análise e modelagem visualmente) — decidido esperar a decomposição estar rodando em produção antes de desenhar essa tela.
- **Servidor MCP de observabilidade do pipeline** (ferramenta de dev, não de produto) — projeto paralelo sob demanda, fora do backlog de pontos da sprint. A decompor em análise/modelagem nesta sprint torna esse servidor mais útil depois (mais granularidade pra expor).
- **Edição manual do diagrama** — promovida para item único da Sprint 13 (antes era S12-04 no plano anterior), viabilidade ainda a discutir no kickoff da S13.
