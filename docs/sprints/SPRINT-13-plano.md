# Plano Sprint 13 — Edição manual do diagrama

**Status:** Planejada, não iniciada (depende da conclusão da Sprint 12) — **viabilidade ainda a discutir no kickoff, escopo abaixo é ponto de partida, não compromisso fechado**

## Contexto

Promovido de item único (S12-04 no plano anterior) para sprint própria, por decisão da stakeholder — o volume de decisões de design e o risco técnico do item justificam discussão isolada, sem competir por atenção com o resto do backlog de qualidade de modelagem (agora concentrado na Sprint 12).

A dor por trás do pedido: mesmo depois da Sprint 12 melhorar a qualidade da modelagem por IA, ela nunca vai acertar 100% dos casos — o usuário precisa de uma saída pra corrigir sem depender só do chat de refinamento (que já existe, mas é "às cegas": você descreve o que quer em texto, sem ver/arrastar o elemento diretamente).

**Importante, já decidido:** a edição manual é um modo **adicional**, não substitui a visualização atual. O Modo Apresentação (S10), o zoom/pan (S11-03) e o highlight de gargalos continuam sendo a experiência padrão ao abrir um processo — isso não muda. Editar é uma ação explícita ("entrar no modo edição"), não o comportamento default do viewer.

## Perguntas de viabilidade a resolver no kickoff (antes de comprometer pontos)

1. **Conflito com o chat de refinamento.** Hoje, cada instrução de chat gera uma nova versão via `PUT /processes/:id/bpmn`, reescrevendo o XML inteiro (inclusive layout, desde a decisão da S9 de não recalcular posições no refino). Se o usuário edita manualmente e *depois* usa o chat, a IA vê o XML editado como base — isso é o comportamento desejado, ou existe risco da IA "desfazer" ajustes manuais que não entendeu? Precisa de um teste manual dedicado antes de fechar escopo.
2. **Convivência com o auto-layout.** O auto-layout (S9) roda só na geração inicial, não no refino — mas se o modo edição permite mover elementos livremente, o próximo refino via chat (que reescreve o XML completo) pode descartar posições ajustadas à mão, do mesmo jeito que já pode descartar ajustes de layout feitos hoje via edição direta no bpmn-js (o endpoint já permite isso, sem UI dedicada). Não é um risco novo introduzido por esta sprint, mas vale confirmar que o modo edição não piora essa situação existente.
3. **Superfície do Modeler vs. Viewer.** Trocar de `Viewer` (read-only, leve) pra `Modeler` (paleta, context pad, edição direta de label, redesenho de conexões) é uma dependência bem maior do bpmn-js. Precisa confirmar que os módulos de zoom/pan (S11-03), Modo Apresentação (S10) e `TokenSimulationModule` continuam funcionando na visão padrão sem esse peso extra sendo carregado por padrão — só quando o modo edição é ativado explicitamente.
4. **Escopo de "editável".** Editar tudo (mover, redesenhar conexão, trocar tipo de elemento, criar/remover elemento) é um Modeler completo — esforço bem maior do que editar só o que resolve os erros mais comuns encontrados na Sprint 12 (ex: só trocar tipo de gateway/atividade e editar label, sem redesenho livre de conexão). Vale decidir o escopo mínimo que resolve a dor real antes de estimar pontos.

## Esboço de backlog (a confirmar/reestimar no kickoff, depois das perguntas acima)

| Item | Descrição | Pontos (estimativa preliminar) |
|---|---|---|
| S13-01 | Botão explícito "Editar diagrama" — componente novo `BpmnEditor.tsx`, montado só quando o modo está ativo; troca pra `bpmn-js` `Modeler` com toolbar básica | 3 |
| S13-02 | Edição de elementos: mover, editar label, redesenhar `sequenceFlow` | 3 |
| S13-03 | Salvar via `PUT /processes/:id/bpmn` (endpoint já existe, já cria nova versão) + sair do modo edição volta pro `Viewer` normal | 1 |
| S13-04 | Testes de não-regressão: Modo Apresentação, zoom/pan e highlight de gargalos continuam funcionando na visão padrão depois que o modo edição existir no bundle | 2 |

**Total preliminar: ~9 pontos** — sujeito a mudar bastante conforme as respostas do kickoff, principalmente a pergunta 4 (escopo de "editável").

## Riscos

- Maior risco técnico do roadmap atual: troca de módulo bpmn-js (`Viewer` → `Modeler`) tem superfície de API bem maior, mais chance de regressão nos recursos já entregues (S10/S11-03) do que qualquer item anterior.
- Se a pergunta de viabilidade 1 (conflito com refino via chat) revelar um problema real de UX (IA desfazendo edição manual sem explicar), pode ser necessário um item extra de "avisar o usuário" ou "preservar edição manual como contexto explícito pro chat" — não estimado ainda.

## Como testar (planejado, a refinar após kickoff)

1. Abrir um processo pronto → confirmar que a view padrão é a mesma de hoje (Viewer read-only, Modo Apresentação e zoom/pan disponíveis) → clicar em "Editar diagrama" → arrastar um elemento, editar o label de uma tarefa, redesenhar uma seta torta → salvar → confirmar nova versão criada em "Versões" com o XML corrigido → confirmar que volta pra view padrão (não fica preso no modo edição)
2. Confirmar que o modo edição não quebra o Modo Apresentação nem o highlight de gargalos na view padrão (ambos dependem de IDs de elemento estáveis — mover/editar não pode trocar IDs)
3. Editar manualmente, depois enviar uma instrução pelo chat → confirmar (ou documentar, se o resultado for inesperado) o que acontece com o ajuste manual
