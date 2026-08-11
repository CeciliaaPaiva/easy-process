# Plano Sprint 12 — Pipeline em estágios (análise separada da modelagem)

**Status:** Em andamento — S12-01, S12-02 e S12-03 concluídas (ver `docs/sprints/SPRINT-12-investigacao.md`), S12-04 a seguir

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
| S12-01 | **Investigação com casos reais — concluída, ver `docs/sprints/SPRINT-12-investigacao.md`.** 6 transcrições reais do banco de dev, rodadas de novo contra o `BpmnGeneratorService` atual (chamada real ao Gemini, sem mudança de código). Achados: tipagem de atividade já funciona bem (não é prioridade); pool/raia pra atores externos é o achado de maior prioridade — 5 de 6 casos tinham ator externo claro na transcrição e **nenhum** virou pool, mesmo quando a própria IA já identificava o ator corretamente na lista `actors` (o problema é estrutural, na tradução pra XML, não na análise); achado de brinde — `parallelGateway` de divisão com uma única saída (erro de nuance, caso concreto em "pedido pelo app"). | 3 |
| S12-02 | **Concluída.** Separou "análise" de "modelagem" em duas chamadas distintas ao Gemini. Novo `bpmn_analysis.py`: recebe a transcrição, devolve um grafo JSON tipado (atores com `is_external`, atividades com `activity_type`, gateways com `gateway_type`/`role`, transições `flows` explícitas, anotações) — sem gerar XML, com validação estrutural própria (ids únicos, `responsible` batendo com `actors`, todo flow alcançável a partir de `start`) e retry corretivo se o grafo vier inconsistente. `bpmn_generator.py` reescrito: recebe o grafo já resolvido, só traduz pra XML (não reinterpreta o processo); `summary`/`actors`/`tasks` agora vêm direto da análise (Python), sem pedir de novo ao LLM de modelagem — menos tokens de saída. Logs separados por `stage` (`bpmn_analysis`, `bpmn_modeling`) — confirmado no painel real, sem mudança de frontend. **Validado contra a API real** com o mesmo caso da investigação ("pedido pelo app"): saiu de 0 para 4 `bpmn:participant` (3 pools externos + raia do ator interno), gateways corretamente pareados split/join, 2 anotações, 2 `endEvent` distintos — resolveu exatamente o padrão "nunca tenta" achado em S12-01. **Trade-off encontrado, não estimado no plano original:** custo por processo praticamente dobrou nesse caso (~$0.0036 vs ~$0.0009 da chamada única antiga) — o risco de custo já registrado abaixo se confirmou na prática, não é só hipótese. | 5 |
| S12-03 | **Concluída.** `bpmn_validator.py` ganhou `validate_external_actors_have_pools(xml, external_actors)`: reprova se algum ator classificado como externo pela análise (S12-02) não tiver `bpmn:participant` correspondente no XML (match case-insensitive por substring, tolerante a variação de fraseado) — chamada do loop de retry de `bpmn_generator.py` logo depois de `validate_bpmn_xml` passar. Adicionada também `_find_pointless_gateway` (dentro de `validate_bpmn_xml`): gateway com exatamente 1 entrada e 1 saída — nem divide nem junta nada — reprova e dispara retry (regressão do bug de nuance achado em S12-01, mesmo padrão de `_find_combined_gateway` do fix da S10). 6 testes novos (`test_bpmn_validator.py` + 1 em `test_bpmn_generator.py` confirmando o retry fim a fim). | 5 |
| S12-04 | **Ajustar prompt de análise para o caso de nuance do gateway mal-formado.** Escopo reduzido em relação ao plano original: S12-01 não encontrou evidência de "erro de nuance" generalizado na tipagem de atividade (já funciona), então few-shot fica focado especificamente no padrão de gateway com saída/entrada única encontrado em "pedido pelo app" — 1 exemplo concreto (transcrição → JSON de análise esperado, sem esse erro) deve bastar como correção pontual, não uma reformulação ampla do prompt. | 1 |
| S12-05 | **Corrigir a tabela de preços hardcoded de `llm_usage.py` e documentar o processo de atualização.** Achado durante a investigação desta sprint: `_PRICING_PER_MILLION` não vem de API, é mantida à mão — se o Gemini mudar preço (já aconteceu 2x na S9, segundo `RELEASE-S9.md`), o painel "Uso de IA" fica silenciosamente incoerente sem ninguém perceber. Adicionar um teste que falha se `record_usage` for chamado com um `model_name` fora da tabela (hoje cai silenciosamente em `(0.0, 0.0)` — custo zero mentiroso), e documentar no `CLAUDE.md` o processo de conferir a tabela oficial do Gemini periodicamente. | 1 |

**Total: 15 pontos** (S12-01 concluída fora do fluxo normal de pontos da sprint — investigação já rodada antes do kickoff formal; S12-04 reduzida de 2 para 1 ponto pelo escopo menor confirmado pelos achados)

## Ordem sugerida dentro da sprint

1. **S12-01 primeiro, sempre** — os outros itens dependem do que for encontrado; começar S12-02/03/04 antes seria arriscar retrabalho.
2. **S12-02 logo em seguida** — é a mudança estrutural que o restante do backlog pressupõe (S12-03 valida o JSON de análise, que só existe depois de S12-02 existir).
3. S12-03 e S12-04 podem correr em paralelo depois de S12-02 pronto, cada um atacando a categoria de erro correspondente encontrada em S12-01.
4. S12-05 é independente, pode entrar em qualquer ponto da sprint — item pequeno, achado à parte.

## Decisão em aberto — resolvida por S12-01

A pergunta original ("nunca tenta" vs. "erra a nuance", e a proporção entre os dois) já tem resposta empírica, documentada em `docs/sprints/SPRINT-12-investigacao.md`: o achado dominante é "nunca tenta" (pool/raia pra ator externo, 5 de 6 casos), com um achado pontual de "erra a nuance" (gateway com saída/entrada única). Por isso S12-03 (estrutural) ficou com mais pontos que S12-04 (prompt/few-shot) no backlog acima — não é mais uma proporção a calibrar no kickoff, já está refletida na estimativa.

## Como testar (planejado)

1. Rodar os mesmos 6 casos de `SPRINT-12-investigacao.md` depois das mudanças → confirmar que os casos com ator externo (pedido pelo app, Pedidos pelo iFood, Produção sob encomenda, Gravação de áudio) passam a gerar `bpmn:participant` pro ator externo, e que o gateway de "pedido pelo app" não sai mais com uma única saída
2. `docker compose exec backend pytest tests/unit/test_bpmn_analysis.py tests/unit/test_bpmn_validator.py tests/unit/test_bpmn_generator.py -v` → cobertura da etapa nova + regressão das checagens estruturais
3. Gerar um processo do zero → confirmar no painel "Uso de IA" que aparecem **duas** linhas na tabela "Por etapa do pipeline" (`analysis` e `modeling`) em vez de uma (`generation`) — sem precisar tocar no frontend, só validando que o breakdown por `stage` já existente reflete a mudança de backend
4. Forçar um `model_name` fora da tabela de preços em teste → confirmar que o novo teste de S12-05 falha (em vez de custo zero silencioso)

## Riscos

- Separar em duas chamadas dobra a latência do pipeline de geração (duas idas e voltas à API em vez de uma) — aceitável pra este produto (processamento já é assíncrono/background, usuário não fica esperando na tela), mas vale medir o tempo real em produção pra não surpreender depois.
- **Confirmado, não é mais hipótese:** custo por processo praticamente dobrou no caso testado (~$0.0036 vs ~$0.0009 da chamada única antiga) — o cache implícito de prefixo não foi suficiente pra compensar o tanto de tokens novo que o grafo JSON intermediário adiciona nos dois sentidos (saída da análise + entrada da modelagem). Em valor absoluto ainda é centavos por processo, mas a stakeholder pediu explicitamente pra não perder de vista a economia — vale decidir com ela se compensa (qualidade muito melhor, achado em S12-02) ou se cabe uma otimização antes de ir pra produção: candidato óbvio é rebaixar o modelo da etapa de modelagem (hoje usa o mesmo tier "capaz" de antes, mas seu trabalho agora é quase mecânico — tradução de grafo já resolvido pra XML, não mais decisão semântica) para o tier mais barato, já usado na transcrição.
- Se S12-01 revelar que um dos dois tipos de erro é raro na prática, a estimativa de S12-03 ou S12-04 deve ser revisitada no meio da sprint, não só no kickoff — mesma lógica de escopo incremental já usada em sprints anteriores.

## O que ficou fora desta sprint (backlog futuro)

- **Observabilidade de eficiência por etapa na UI do admin** (comparar custo/tempo/qualidade entre análise e modelagem visualmente) — decidido esperar a decomposição estar rodando em produção antes de desenhar essa tela.
- **Servidor MCP de observabilidade do pipeline** (ferramenta de dev, não de produto) — projeto paralelo sob demanda, fora do backlog de pontos da sprint. A decompor em análise/modelagem nesta sprint torna esse servidor mais útil depois (mais granularidade pra expor).
- **Edição manual do diagrama** — promovida para item único da Sprint 13 (antes era S12-04 no plano anterior), viabilidade ainda a discutir no kickoff da S13.
