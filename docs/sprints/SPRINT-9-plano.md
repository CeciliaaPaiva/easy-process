# Plano Sprint 9 — Animação de fluxo e destaque de gargalos no BPMN

**Status:** Planejada, não iniciada (depende da conclusão da Sprint 8)

## Contexto

Segunda metade do pedido original: animações no diagrama BPMN para tornar a apresentação mais dinâmica e destacar gargalos, inspiradas no artigo sobre animações de gateways BPMN (token se movendo pelos sequence flows, cores por tipo de gateway, destaque de caminho ativo).

Dois achados relevantes do levantamento:

1. **Gargalos já existem.** `bottleneck_analysis_service` (Gemini) + `GET/POST /processes/:id/bottlenecks` + `BottleneckPanel.tsx` já retornam `Finding { title, description, severity, related_elements: string[] }`, e o frontend já usa `related_elements` para popular `highlightIds` no `BpmnViewer` (hover → destaque estático via `canvas.addMarker`, entregue na S7). Esta sprint é uma **extensão** desse mecanismo para virar animação, não uma feature do zero.
2. **A própria S7 já apontou o caminho** (ver "O que ficou para a próxima sprint" em `docs/releases/RELEASE-S7.md`): animação de token via lib `bpmn-js-token-simulation` (comunidade bpmn.io), com estimativa de 2-3 pontos, customização por CSS vars/classes (`.bts-token-count`, `--token-simulation-*`).

## Decisão técnica em aberto — precisa ser confirmada no kickoff desta sprint

Há duas abordagens possíveis, com trade-off custo x controle:

| Abordagem | Custo | Prós | Contras |
|---|---|---|---|
| **`bpmn-js-token-simulation`** (biblioteca da comunidade bpmn.io) | ~2-3 pts (estimativa já validada na S7) | Muito mais rápido; mantida pela comunidade; já cobre exclusive/parallel/inclusive gateway nativamente | Pensada para o Modeler interativo (simular manualmente), não para replay passivo; theming via CSS vars, sem API oficial de tema; pode trazer módulos/UI que não usaremos |
| **Motor de animação próprio** (SVG `getPointAtLength` sobre os paths do bpmn-js, via `Overlays` module) | ~13 pts (toolbar 2 + motor 5 + diferenciação por gateway 3 + overlay de gargalo 3) | Controle total do visual (glow de gargalo, velocidade, cores); não depende de plugin de terceiros; usa módulo `Overlays` já incluso no bundle atual do `Viewer` | Muito mais caro; reinventa algo que a comunidade já resolveu |

**Recomendação:** começar pela lib `bpmn-js-token-simulation` (opção validada pela própria equipe na S7, mais barata) e só evoluir para motor próprio se as limitações de tema/UI se mostrarem bloqueantes na prática. Isso muda o backlog abaixo — a Sprint 9 deve abrir confirmando essa escolha antes de estimar em pontos definitivos.

## Escopo (a confirmar no kickoff)

- Modo "Apresentação" no `BpmnViewer.tsx`/`BpmnToolbar.tsx` (novo — mencionado no `CLAUDE.md` desde o início, nunca implementado) com play/pause/velocidade.
- Token animado percorrendo os `sequenceFlow`, diferenciando visualmente por tipo de gateway (`bpmn:ExclusiveGateway` cicla ramos; `bpmn:ParallelGateway` anima todos simultâneo; `bpmn:InclusiveGateway` anima subconjunto) — sem dado real de execução, é uma animação didática (igual ao artigo de referência), não um replay fiel de uma instância real do processo.
- Destaque persistente nos elementos de `related_elements` (dado que já existe, vindo do `bottleneck_analysis_service`) durante a animação: glow/cor diferenciada + ícone, reaproveitando o mesmo prop `highlightIds`/`onHighlight` já usado pelo `BottleneckPanel`.
- Sem mudança de banco necessária — é 100% frontend, reaproveitando dados já existentes.

## Backlog preliminar (revisar após decisão da tabela acima)

| Item | Descrição | Pontos (se lib) | Pontos (se motor próprio) |
|---|---|---|---|
| S9-01 | Integrar `bpmn-js-token-simulation` (ou motor próprio) + `BpmnToolbar.tsx` (play/pause/velocidade) | 2 | 2+5=7 |
| S9-02 | Diferenciação visual por tipo de gateway | incluso na lib | 3 |
| S9-03 | Overlay de gargalo reaproveitando `related_elements` | 1 | 3 |
| S9-04 | Testes (fixture XML com exclusive/parallel gateway) | 1 | 2 |
| **Total** | | **~4** | **~15** |

## Como testar (planejado)

1. Abrir um processo pronto com sugestões na aba "Sugestões"
2. Ativar modo "Apresentação" no viewer
3. Confirmar token percorrendo os flows, com comportamento diferente em gateways exclusive vs. parallel
4. Confirmar destaque visual diferenciado nos elementos presentes em `related_elements` de algum finding
