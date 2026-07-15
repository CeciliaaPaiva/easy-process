# Plano Sprint 13 — Fluxograma para não-técnicos + brainstorm de personas

**Status:** Planejada, não iniciada (depende da conclusão da Sprint 12)

## Contexto

A stakeholder identificou 3 personas de usuário e pediu um brainstorm de como entregar valor pras 3, com destaque para um "fluxograma" (alternativa ao BPMN técnico) e um possível dashboard para líderes não-técnicos.

## As 3 personas

| Persona | Quem é | O que quer |
|---|---|---|
| **A — Analista técnico** | Já entende BPMN, é quem hoje o produto atende bem (viewer técnico, chat de refinamento, gateways/raias/anotações corretos — foco da S12) | Modelar processos complexos com precisão, exportar pra ferramentas BPMN reais |
| **B — Líder de equipe / gestor não-técnico** | Não conhece notação BPMN. Quer identificar e resolver gargalos na rotina da equipe | Instruir a equipe de forma simples; decidir rápido onde otimizar |
| **C — Colaborador individual** | Não conhece notação BPMN. Quer documentar sua própria rotina | Documentar rápido pra treinar substitutos e organizar o próprio trabalho |

## Brainstorm — ideias por persona

**Persona A (já atendida hoje)** — o produto já entrega: viewer técnico, chat de refinamento, versionamento, exportação BPMN/PNG/PDF (S11), edição manual (S12). Sem pendência nova identificada nesta rodada.

**Persona B (líder/gestor)**
- *Dashboard de "saúde do processo"*: lista dos processos da equipe com um badge tipo "3 gargalos identificados", clicando vai direto pra aba "Sugestões" que já existe (reaproveita `bottleneck_analysis_service`, sem trabalho novo de IA).
- *Resumo executivo*: usar o `summary` que já é gerado na geração inicial + destacar as sugestões de maior severidade num card no topo, em linguagem simples, sem termos BPMN.
- O **Modo Apresentação (S10)** já é uma ferramenta forte pra essa persona — "instruir de maneira simples" é literalmente o que a animação resolve. Vale destacar isso mais na UI pra essa persona descobrir a feature (hoje é um botão discreto no canto do viewer).
- *Antes/depois*: quando o líder aplica uma sugestão via chat, mostrar um comparativo simples ("de 6 passos para 4", "removida 1 aprovação manual") em vez de só a nova versão do diagrama.
- *Checklist exportável*: lista numerada de passos em texto simples (sem notação), pra compartilhar com a equipe sem exigir que ninguém entenda BPMN.

**Persona C (colaborador individual)**
- *Guia de treinamento exportável*: PDF com título "Como fazer: [processo]" e passos numerados + o fluxograma simples (não o BPMN técnico), em vez de export técnico.
- *Perguntas guiadas na gravação*: hoje o áudio é livre; um roteiro tipo "descreva o passo 1... o que você faz se der errado?" ajudaria quem trava na hora de gravar sem saber o que falar.
- *Compartilhamento simples*: link direto pro guia, sem exigir que o substituto tenha conta na plataforma.

## O que entra nesta sprint vs. vira backlog futuro

Dado o volume de ideias acima, só o item com pedido explícito e mais alto valor imediato (fluxograma) entra nesta sprint com pontos comprometidos. As demais ideias (dashboard de gargalos, resumo executivo, antes/depois, checklist exportável, perguntas guiadas, compartilhamento sem conta) ficam registradas aqui como backlog priorizável — decisão de trazer alguma pra dentro desta sprint (se sobrar capacidade) ou pra próxima é do kickoff, não travada agora.

## Decisão técnica em aberto — confirmar no kickoff

Duas abordagens pro "fluxograma simples":

| Abordagem | Custo | Prós | Contras |
|---|---|---|---|
| **Reskin do BPMN já gerado** (view mode) | ~8 pts | Reaproveita 100% do pipeline de IA já existente (uma fonte de verdade); esconde raias/pools/tipos de gateway visualmente (CSS + mapeamento de ícone), sem gerar nada novo | Estrutura de fundo continua sendo BPMN "de verdade" — se a IA modelar mal (S12), o fluxograma simples também herda o erro |
| **Geração dedicada** (segunda chamada de IA com notação simplificada) | ~13+ pts | Pode ser genuinamente mais simples/didático, adaptado à persona não-técnica desde a geração | Dobra custo de IA por processo (chamada extra); duas fontes de verdade pra manter sincronizadas quando o usuário refina via chat |

**Recomendação:** começar pela opção "reskin" (mais barata, reaproveita tudo) e só evoluir pra geração dedicada se as limitações de fidelidade se mostrarem bloqueantes na prática — mesmo padrão de decisão incremental já usado na S9 (Modo Apresentação: lib da comunidade primeiro, motor próprio só se necessário).

## Backlog preliminar (revisar após decisão da tabela acima)

| Item | Descrição | Pontos (se reskin) |
|---|---|---|
| S13-01 | Toggle "Fluxograma simples" / "BPMN técnico" no viewer | 2 |
| S13-02 | Reestilizar diagrama no modo simples: esconder raias/pools, generalizar ícones de tipo de atividade (tudo vira retângulo arredondado), gateways viram losango genérico de decisão (sem X/+/O) | 4 |
| S13-03 | Export "guia de treinamento" (PDF com passos numerados, linguagem simples) reaproveitando o modo fluxograma | 2 |
| **Total** | | **~8** |

## Como testar (planejado)

1. Abrir um processo com raias, gateway exclusive e gateway paralelo → ativar "Fluxograma simples" → confirmar que raias/pools somem visualmente e os gateways viram losangos genéricos, sem perder a estrutura do fluxo
2. Alternar entre os dois modos várias vezes → confirmar que não há perda de dados (é só apresentação, o XML por trás não muda)
3. Exportar o guia de treinamento → PDF legível por alguém sem nenhum conhecimento de BPMN

## Riscos

- "Reskin" pode não ser suficiente pra atender de verdade a persona C se a estrutura do BPMN subjacente for muito técnica (ex: muitos gateways aninhados de um processo real) — o risco fica menor se S12 (qualidade da modelagem) for concluída antes, já que aí a estrutura de base é mais limpa.
- Escopo desta sprint deliberadamente conservador (só o fluxograma) — o dashboard pra líderes (persona B) é a ideia de maior potencial de valor percebido, mas foi propositalmente deixada de fora dos pontos comprometidos até validar interesse real com a stakeholder no kickoff.
