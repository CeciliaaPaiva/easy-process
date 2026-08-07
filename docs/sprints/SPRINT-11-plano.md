# Plano Sprint 11 — Correções de UX e acesso (fundação)

**Status:** Concluída — ver `docs/releases/RELEASE-S11.md`

## Contexto

Lista de problemas reportados pela stakeholder após a Release S9/S10, organizada em sprints. Este documento cobre a primeira leva: consertos pontuais de alto impacto e baixo/médio esforço, incluindo o fechamento de uma exposição real de dados sensíveis (painel de custo de IA visível a clientes).

Levantamento do estado atual feito antes de estimar (evita estimar no escuro):

| Problema relatado | Onde está hoje |
|---|---|
| Painel "Uso de IA" visível a clientes | `_require_admin` em `backend/app/api/v1/admin.py` só checa `role == "admin"` — não existe distinção entre admin de tenant e admin da plataforma. Qualquer cliente com um usuário `admin` no seu próprio tenant acessa `/admin/usage` hoje. |
| Sem zoom no BPMN | `BpmnViewer.tsx` usa `bpmn-js` `Viewer` puro, sem `ZoomScrollModule`/`MoveCanvasModule`. Só `canvas.zoom('fit-viewport')` no load. Sem scroll/pinch, sem botões +/-. |
| Sem exportar PNG/PDF | `GET /api/v1/processes/:id/export` só devolve o `.bpmn` (XML puro). Nenhuma lib de imagem/PDF instalada em nenhum dos dois lados. |
| Chat sem textarea expansível | `ChatWindow.tsx` usa `<input type="text">` de uma linha, sem auto-resize. |
| Barra superior/layout não responsivo | `page.tsx` do processo: zero breakpoints (`md:`/`lg:`/`sm:`) no arquivo inteiro; painel direito é `w-80 shrink-0` fixo, não colapsa em mobile. |

## Backlog

| Item | Descrição | Pontos |
|---|---|---|
| S11-01 | **Restringir "Uso de IA" à administradora da plataforma.** Adicionar campo `is_platform_admin: bool` (default `false`) ao model `User` + migration Alembic. `_require_admin` passa a checar `user.is_platform_admin` em vez de `role == "admin"`. Definir a conta da Cecilia como `is_platform_admin=True` via seed/script manual (não expor toggle na UI — é operação de banco, não uma feature de produto). Esconder o link "Uso de IA" na sidebar para quem não é platform admin. Teste de regressão: admin de tenant cliente continua recebendo 403. | 2 |
| S11-02 | **Textarea expansível no chat de refinamento.** Trocar `<input>` por `<textarea>` com auto-resize (cresce com o conteúdo até um máximo, depois rola). Manter o comportamento de enviar com Enter / quebrar linha com Shift+Enter. | 1 |
| S11-03 | **Zoom e pan no BpmnViewer.** Adicionar `ZoomScrollModule` + `MoveCanvasModule` (ou trocar para `NavigatedViewer`) aos `additionalModules`. Scroll do mouse e pinch (touch) passam a dar zoom; arrastar move o canvas. Adicionar botões +/- (e "ajustar à tela") sobrepostos ao canto do viewer, no mesmo padrão visual da `BpmnToolbar` já existente. Cuidado: não pode conflitar com o Modo Apresentação (S10) nem com o `TokenSimulationModule` já carregado — testar os dois juntos. | 2 |
| S11-04 | **Exportar PNG e PDF.** Backend continua servindo só o `.bpmn`; PNG/PDF gerados no client a partir do SVG que o `bpmn-js` já renderiza (`canvas.getModuleName('...')` → `viewer.saveSVG()` já existe na API do bpmn-js). PNG: desenhar o SVG num `<canvas>` e exportar via `toBlob`. PDF: embutir o PNG gerado num PDF de página única (avaliar `jsPDF` — biblioteca leve, sem dependência de servidor). Botão "Exportar" vira um menu com 3 opções (.bpmn / PNG / PDF) em vez de exportar direto. | 4 |
| S11-05 | **Layout responsivo da página de processo.** Header: `flex-wrap` + esconder textos secundários (ex: breadcrumb "Projeto /") abaixo de `md`. Painel direito (`w-80 shrink-0`): em telas `< lg`, vira um painel deslizante/modal acionado por um botão, em vez de ocupar espaço fixo ao lado do diagrama — o BPMN precisa do espaço horizontal. Em telas grandes (`xl`+), avaliar se o painel direito deveria crescer (hoje é sempre `w-80` fixo, não aproveita telas grandes). Testar em 3 breakpoints reais (mobile ~375px, tablet ~768px, desktop grande ~1920px) via Playwright + screenshot, não só redimensionar a janela visualmente. | 5 |

**Total: 14 pontos** (~1,5 sprints de folga em relação à velocidade de 20 pts/sprint — deixa margem para o histórico recente de bugs reais encontrados só em validação manual end-to-end, que consumiram tempo não estimado nas últimas duas sprints).

## Ordem sugerida dentro da sprint

1. **S11-01 primeiro** — é a única pendência com exposição real de dado sensível a clientes; não deveria esperar.
2. S11-02 e S11-03 podem ser feitos em paralelo (não têm dependência entre si nem com o resto).
3. S11-04 depende de S11-03 estar funcionando (zoom/pan não deveria quebrar a geração do SVG usada pra exportar — testar depois de S11-03, não antes).
4. S11-05 por último — é o item mais arriscado de regressão visual (toca o layout geral da página), melhor fazer depois que os outros 4 já estabilizaram a área.

## Como testar (planejado)

1. Login como cliente com role `admin` de um tenant → confirmar 403/link escondido em "Uso de IA"; login como Cecilia (`is_platform_admin=True`) → confirmar acesso normal
2. Chat: colar um parágrafo longo no input → confirmar que o campo cresce, sem precisar rolar horizontalmente pra ler o que foi digitado
3. Abrir um processo pronto → scroll do mouse sobre o diagrama dá zoom; arrastar move o canvas; botões +/- funcionam; ativar Modo Apresentação continua funcionando com zoom/pan disponíveis
4. Exportar um processo nos 3 formatos → `.bpmn` abre no Camunda Modeler, PNG abre como imagem, PDF abre com o diagrama legível numa página
5. Abrir a página de processo em 375px, 768px e 1920px de largura → nada quebra, painel lateral não force scroll horizontal, header não trunca informação crítica (nome do processo, status)

## Riscos

- Zoom/pan (S11-03) pode interagir mal com o Modo Apresentação (S10) — o canvas já tem overlays posicionados de forma absoluta; testar os dois módulos juntos antes de dar como pronto.
- PDF client-side (S11-04) pode ter qualidade ruim em diagramas muito grandes/largos (a página do PDF tem proporção fixa) — se o resultado ficar ilegível, considerar gerar em orientação paisagem ou dividir em múltiplas páginas como fallback, mas isso é escopo extra a validar durante a sprint, não estimado agora.
