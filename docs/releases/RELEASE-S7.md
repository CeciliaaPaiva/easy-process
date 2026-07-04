# Release Sprint 7 — "Gargalos" evolui para "Sugestões" com gatilho de monetização + destaque visual no diagrama

**Data:** 2026-07-04
**Sprint:** S7
**Status:** Concluído

## Resumo
Esta sprint refinou o recurso de IA entregue na S6 (antiga aba "Gargalos") a partir de feedback direto da PO, transformando-o na aba **"Sugestões"**: um recurso pensado deliberadamente como gatilho de monetização futura (o dono da empresa vê a sugestão e sente a necessidade de contratar um analista de negócio), com linguagem técnica de BPM e sem repetição de frase-padrão entre os achados. Também foi adicionado destaque visual em vermelho no próprio diagrama BPMN: ao passar o mouse sobre uma sugestão, o(s) elemento(s) relacionado(s) acendem em vermelho no viewer, facilitando o entendimento para quem não lê BPMN fluentemente. Com essa entrega, consideramos fechada a **primeira versão do MVP**.

## Funcionalidades entregues

### Frontend
- [S7-01] Aba renomeada de "Gargalos" para "Sugestões" (`page.tsx`, `BottleneckPanel.tsx`) — label, textos de erro e estado vazio atualizados
- [S7-02] `BpmnViewer.tsx` ganhou prop `highlightIds`: usa `canvas.addMarker`/`removeMarker` do bpmn-js para aplicar a classe `.bpmn-suggestion-highlight` (stroke vermelho + preenchimento claro, definida em `globals.css`) nos elementos indicados
- [S7-03] `BottleneckPanel.tsx` expõe `onHighlight(elementIds)`, disparado em `onMouseEnter`/`onMouseLeave` de cada card de sugestão, repassando `related_elements` do finding
- [S7-04] `page.tsx` mantém o estado `highlightIds` compartilhado entre `BottleneckPanel` e `BpmnViewer`; limpo automaticamente ao trocar de aba (evita destaque "preso" se o usuário sair da aba Sugestões no meio do hover)

### Backend
- [S7-05] `bottleneck_analysis.py`: prompt e `_SYSTEM_INSTRUCTION` reescritos — exige terminologia técnica de BPM (gateway de decisão, handoff, retrabalho, SLA, throughput, ponto único de falha), descrições sucintas, e uma chamada para ação variada ao final de cada finding (proibido repetir a mesma frase entre achados na mesma resposta)
- [S7-06] `DISCLAIMER` reformulado para reforçar o papel do analista de negócio sem soar como aviso legal genérico

## Métricas
- Testes passando: 132/133 (1 skip) — suite backend inalterada nesta sprint, sem regressão
- Cobertura: não recalculada nesta sprint (mudança é só de prompt/copy/UI, sem lógica nova testável isoladamente)
- Frontend: `tsc --noEmit` limpo

## O que ficou para a próxima sprint
- Avaliada e **não implementada ainda**: animação de token (bolinha) percorrendo o fluxo do BPMN, com desaceleração perto dos elementos de "Sugestões" — viável via lib `bpmn-js-token-simulation` (comunidade bpmn.io), customização de branding possível via CSS vars/classes (`.bts-token-count`, `--token-simulation-*`), mas sem API de tema oficial. Estimativa: 2-3 pontos
- Nome técnico interno (rota `/bottlenecks`, classes `Bottleneck*`) não foi renomeado — só a camada visível ao usuário mudou. Renomear para `suggestions` é refactor cosmético, sem urgência
- Meta de monetização ainda em aberto: a aba "Sugestões" foi desenhada como gatilho, mas o modelo de cobrança em si (assinatura, sob demanda, comissão sobre indicação de analista) ainda não foi decidido

## Decisões técnicas tomadas nesta sprint
- Destaque de elementos usa a API nativa de markers do bpmn-js (`addMarker`/`removeMarker`) em vez de manipular o SVG diretamente — mais robusto a mudanças de versão da lib
- Optou-se por não renomear endpoints/classes de backend (`bottlenecks`, `BottleneckAnalysisService`) nesta sprint para não ampliar o escopo de um ajuste que era, na origem, apenas de copy e prompt

## Como testar esta release
1. `docker compose up -d`, logar com `dev@example.com`/`devpass123`
2. Abrir um processo pronto → aba "Sugestões" (antiga "Gargalos") → conferir que os achados usam termos técnicos e não repetem a mesma frase de chamada para ação
3. Passar o mouse sobre um card de sugestão e confirmar que o(s) elemento(s) relacionado(s) acendem em vermelho no diagrama à esquerda
4. Trocar de aba no meio do hover e confirmar que o destaque some (não fica preso)
5. `docker compose exec backend pytest tests/ -q` — deve passar 132/133

## Bugs conhecidos
- Nenhum bug conhecido nesta release
