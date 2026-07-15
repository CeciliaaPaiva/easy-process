# Plano Sprint 12 — Qualidade da modelagem de IA + edição manual

**Status:** Planejada, não iniciada (depende da conclusão da Sprint 11)

## Contexto

A S9 (`docs/releases/RELEASE-S9.md`) já tentou resolver isso uma vez: adicionou `SEMANTIC_MODELING_RULES` em `backend/app/services/bpmn_prompts.py` cobrindo tipos de gateway, tipos de atividade, pool vs. raia e anotações, e trocou o modelo (`gemini-flash-lite-latest` → `gemini-3.1-flash-lite`) porque o mais barato "modelava BPMN semanticamente pobre". A stakeholder reporta que, na prática, ainda não está bom o suficiente: piscinas e raias não são modeladas, gateways saem do tipo errado, sem anotações, sem caixas pretas, sem diferenciar atividade manual/usuário/sistema. Ou a regra de prompt não é suficiente sozinha (LLM não segue 100% das vezes), ou há uma regressão, ou os casos reais são mais variados do que o teste sintético usado na S9 ("1 decisão + 2 atores", conforme a própria release já registrava como limitação).

Em paralelo, o pedido de "não consigo mexer manualmente" quando a IA erra é a mesma dor por outro ângulo: mesmo com prompt/validação melhores, a IA nunca vai acertar 100% — o usuário precisa de uma saída para corrigir sem depender só do chat.

**Importante:** a edição manual (S12-04) é um modo **adicional**, não uma substituição da visualização atual. O Modo Apresentação (S10), o zoom/pan (S11-03) e o highlight de gargalos continuam sendo a experiência padrão ao abrir um processo — isso não muda. Editar é uma ação explícita ("entrar no modo edição"), não o comportamento default do viewer.

## Backlog

| Item | Descrição | Pontos |
|---|---|---|
| S12-01 | **Investigação com casos reais.** Rodar de 5 a 8 transcrições reais e variadas (múltiplos atores, gateways de tipos diferentes, pelo menos um caso que deveria gerar pool externo/caixa preta) contra o pipeline atual. Catalogar exatamente qual regra a IA ignora e com que frequência — isso vira a lista de prioridade dos dois itens seguintes, em vez de tentar adivinhar. | 3 |
| S12-02 | **Reforçar `bpmn_validator.py` com checagens estruturais para os padrões mais recorrentes encontrados em S12-01.** Mesmo padrão já usado para o bug do gateway combinado (fix em `2e7f53f`): regra de prompt sozinha não impede a IA de errar de novo, a validação com retry corretivo (já existe no pipeline, até 3x) garante que o XML persistido não tenha o padrão errado. Exemplos prováveis de checagem (a confirmar com S12-01): gateway de divisão sem gateway de junção correspondente; `bpmn:participant` com elementos internos mas sem `laneSet` quando há 2+ atores na transcrição (sinal de pool devendo ser raia); atividade sem nenhum tipo específico quando a transcrição descreve claramente o modo de execução. | 5 |
| S12-03 | **Ajustar prompts/few-shot conforme achados de S12-01.** Se o problema for a IA "esquecendo" a regra em transcrições mais longas/complexas, considerar exemplos few-shot concretos (input de transcrição → BPMN esperado) em vez de só regras descritivas — few-shot geralmente performa melhor que instrução pura para modelos menores como o `flash-lite` usado hoje. | 3 |
| S12-04 | **Edição manual do diagrama, como modo à parte — não substitui a visualização atual.** A view padrão do processo continua exatamente como é hoje: `bpmn-js` `Viewer` read-only, com Modo Apresentação (S10), zoom/pan (S11-03) e highlight de gargalos funcionando normalmente — é o que o analista técnico usa no dia a dia e não pode regredir. Edição manual entra como um modo **separado**, acionado por um botão explícito tipo "Editar diagrama" (ex.: `BpmnEditor.tsx`, componente novo, só montado quando esse modo está ativo). Ao entrar no modo edição: troca para `bpmn-js` `Modeler` com toolbar básica (mover elemento, editar label, redesenhar sequenceFlow). Ao salvar ou sair do modo edição, volta pro `Viewer` normal. Salvar via `PUT /processes/:id/bpmn` (endpoint já existe, já cria nova versão). Roda **depois** de S11-03 (zoom/pan) — o Modeler precisa da mesma navegação. | 8 |

**Total: 19 pontos**

## Ordem sugerida dentro da sprint

1. **S12-01 primeiro, sempre** — os outros três itens dependem do que for encontrado; estimar/começar S12-02/S12-03 antes seria arriscar retrabalho.
2. S12-02 e S12-03 podem correr em paralelo depois do achado.
3. S12-04 (edição manual) é independente dos outros três — pode começar a qualquer momento depois que S11-03 (zoom) estiver pronto, inclusive em paralelo com S12-01/02/03 se a capacidade da sprint permitir.

## Decisão em aberto — confirmar no kickoff

Vale perguntar à stakeholder, antes de comprometer pontos em S12-02/03: os exemplos de erro que ela viu são mais "a IA nunca tenta" (regra ausente) ou "a IA tenta mas erra os detalhes" (ex: usa `userTask` quando deveria ser `manualTask`)? A resposta muda o peso relativo entre reforçar a validação estrutural (pega ausência total de um padrão) vs. ajustar few-shot (pega erro de nuance/classificação, que validação estrutural não consegue verificar — não dá para validar via XML se "userTask" era ou não a escolha semântica certa para aquele trecho da transcrição).

## Como testar (planejado)

1. Rodar os mesmos 5-8 casos de S12-01 depois das mudanças → comparar taxa de acerto antes/depois por regra
2. `docker compose exec backend pytest tests/unit/test_bpmn_validator.py tests/unit/test_bpmn_generator.py -v` → novos testes de regressão para cada checagem estrutural adicionada
3. Abrir um processo pronto → confirmar que a view padrão é a mesma de hoje (Viewer read-only, Modo Apresentação e zoom/pan disponíveis) → clicar em "Editar diagrama" → arrastar um elemento, editar o label de uma tarefa, redesenhar uma seta torta → salvar → confirmar nova versão criada em "Versões" com o XML corrigido → confirmar que volta pra view padrão (não fica preso no modo edição)
4. Confirmar que o modo edição não quebra o Modo Apresentação nem o highlight de gargalos na view padrão (ambos dependem de IDs de elemento estáveis — mover/editar não pode trocar IDs)

## Riscos

- S12-04 é o item mais arriscado da sprint: trocar `Viewer` por `Modeler` (só dentro do modo edição) muda módulos internos do bpmn-js carregados (o `Modeler` inclui bundles bem maiores — palette, context pad, direct editing). Como os dois modos usam instâncias separadas do bpmn-js (`BpmnViewer.tsx` continua intocado; `BpmnEditor.tsx` é novo), o risco de conflito de módulo é baixo — mas testar mesmo assim que `TokenSimulationModule` (S10) e o highlight de gargalos (`highlightIds`, desde S7) continuam funcionando sem regressão na view padrão depois que o modo edição existir.
- Se S12-01 revelar que o problema é majoritariamente "erro de nuance" (não detectável por validação estrutural), o ROI de S12-02 cai — decisão de escopo deve ser revisitada no meio da sprint, não só no kickoff.
