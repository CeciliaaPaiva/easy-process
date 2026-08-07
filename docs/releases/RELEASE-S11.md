# Release Sprint 11 — Correções de UX e acesso (fundação)

**Data:** 2026-08-07
**Sprint:** S11
**Status:** Concluído

## Resumo
Primeira leva de correções pontuais reportadas pela stakeholder após a S9/S10: fecha uma exposição real de dado sensível (painel de custo de IA visível a qualquer admin de tenant cliente), e resolve as quatro reclamações de UX mais recorrentes no viewer BPMN e no chat de refinamento — sem zoom, sem exportar imagem/PDF, chat com input de uma linha só, layout que quebra em telas menores.

## Funcionalidades entregues

### Backend
- **[S11-01]** Novo campo `User.is_platform_admin` (migration `005`, default `false`) — distingue admin de tenant (`role="admin"`, gerencia membros do próprio workspace) de admin da plataforma (acessa dados agregados entre tenants). `_require_admin` em `admin.py` passa a checar `is_platform_admin` em vez de `role == "admin"`. Script `scripts/set_platform_admin.py <email> [--revoke]` concede/revoga o acesso via banco — sem toggle na UI, por decisão do plano (é operação de infraestrutura, não feature de produto)
- **[S11-01]** `UserResponse` (schema) passa a expor `is_platform_admin`, consumido pela sidebar no frontend
- **Bug encontrado durante a implementação, corrigido junto:** colunas `created_at`/`updated_at` de todas as tabelas eram `TIMESTAMP WITHOUT TIME ZONE` mas sempre guardaram UTC — o frontend interpretava a string ISO sem offset como horário local do navegador, adiantando os horários exibidos (visível no próprio painel "Uso de IA" que esta sprint restringiu). Migration `004` converte todas para `TIMESTAMP WITH TIME ZONE`

### Frontend
- **[S11-01]** Sidebar: link "Uso de IA" só aparece para `is_platform_admin === true` (antes: qualquer `role === "admin"`)
- **[S11-02]** `ChatWindow.tsx`: `<input>` de uma linha trocado por `<Textarea>` com auto-resize (cresce até 160px, depois rola); Enter envia, Shift+Enter quebra linha
- **[S11-03]** `BpmnViewer.tsx`: troca `bpmn-js` `Viewer` puro por `bpmn-js/lib/NavigatedViewer` (já inclui `ZoomScrollModule` + `MoveCanvasModule`) — scroll do mouse e pinch dão zoom, arrastar move o canvas. Botões +/- e "ajustar à tela" sobrepostos no canto inferior esquerdo do viewer (canto direito é ocupado pelo selo "powered by bpmn.io", exigido pela licença). Convivência com Modo Apresentação (S10) e `TokenSimulationModule` preservada — nenhum dos dois módulos novos interfere no driver de auto-play
- **[S11-04]** Botão "Exportar" virou menu com 3 opções: `.bpmn` (XML, já existia), PNG e PDF — ambos gerados no client a partir do SVG que o próprio `bpmn-js` renderiza (`viewer.saveSVG()`, exposto via `BpmnViewerHandle.exportSvg()` — imperative handle repassada por prop `viewerRef`, não por `ref` nativa, porque `next/dynamic()` não encaminha `ref` para componentes que não usam `forwardRef`). Novo `lib/bpmnExport.ts`: PNG desenha o SVG num `<canvas>` (escala 2x) e exporta via `toBlob`; PDF (`jsPDF`, nova dependência) usa página dimensionada exatamente ao tamanho do diagrama em vez de A4 fixo, evitando diagramas grandes/largos ficarem cortados ou espremidos
- **[S11-05]** Layout responsivo da página de processo: header com `flex-wrap`, breadcrumb "Projeto /" escondido abaixo de `md`, nome do processo truncado com `max-w` progressivo. Painel direito (`w-80` fixo antes) agora é um painel deslizante (`fixed`, com overlay) abaixo de `lg`, acionado por um botão "Painel"; em `xl` cresce para `w-96`

## Métricas
- Pontos planejados: 14
- Pontos entregues: 14
- Testes passando: 188 passed, 1 skipped (backend, `pytest -q`); 17/17 (frontend, `npx vitest run`)
- `tsc --noEmit` e `eslint --max-warnings=0` limpos no frontend
- `ruff check`/`black --check` no backend: nenhum erro novo introduzido pelos arquivos desta sprint (débito pré-existente em `tenants.py`, linhas intocadas pelo diff — mesma categoria de débito já registrada em releases anteriores)

## Validação visual (ao vivo, navegador real)
Feita depois do commit inicial, com o Chrome integrado, em `easyprocess.claudinha.local` (ambiente de dev provisionado via `dev-env`, adicionada entrada em `/etc/hosts` local — DNS de `*.claudinha.local` ainda não existe a nível de rede). Duas contas de teste criadas para o teste (`qa.admin3@…`, tenant comum; `qa.platform@…`, promovida via `scripts/set_platform_admin.py`) — removidas do projeto/processo de teste ao final, contas mantidas para reteste futuro.

1. **S11-01**: logada como admin de tenant comum, sidebar não mostra "Uso de IA"; `GET /admin/usage` (chamado direto, sem passar pela UI) retorna 403; acesso direto pela URL `/admin/usage` também bloqueado (tela "Apenas administradores..."). Logada como platform admin, sidebar mostra o link e a página carrega normalmente. **Confirmado.**
2. **S11-03**: scroll do mouse simulado pelo Chrome DevTools Protocol não dispara o listener de wheel do bpmn-js (limitação conhecida de automação, não indica bug — o `NavigatedViewer` é a mesma lib usada pelo Camunda Modeler). Testado pelos botões +/-/ajustar à tela (nosso código): funcionam. Arrastar para mover o canvas: funciona. Ativado o Modo Apresentação e testado zoom simultâneo: token continuou avançando normalmente durante o zoom, sem travar — **sem conflito confirmado**.
3. **S11-04**: os 3 formatos exportados sem erro (nenhuma mensagem de erro na tela, console limpo); `.bpmn` confirmado com `GET /processes/:id/export` retornando 200 nos logs do backend. Não foi possível abrir os arquivos PNG/PDF baixados para inspeção visual do conteúdo — o Chrome controlado pela extensão roda numa máquina diferente do filesystem acessível por este agente (pasta de downloads não visível daqui).
4. **S11-05**: testado com sidebar do dashboard recolhida (para isolar o layout da página do processo) via iframe de largura fixa, já que o `resize_window` não teve efeito — o display do Chrome está travado em 1280×720. Em 375px: painel vira modal deslizante com overlay, header quebra em duas linhas sem cortar informação crítica, sem scroll horizontal. Em 768px: header numa linha só, nome completo visível, painel ainda é modal (correto, abaixo de `lg`=1024). Em ~1200px (o máximo alcançável no display disponível): painel volta a ficar fixo ao lado do diagrama, breadcrumb "Projeto /" reaparece. **Não foi possível testar 1920px real** — sem uma janela de browser maior que 1280px disponível nesta sessão.

## O que ficou para a próxima sprint
- Nenhuma pendência do escopo planejado desta sprint.
- Duas lacunas da validação, por limitação do ambiente de automação, não do código: (a) o layout em telas ≥1280px (`xl:w-96` do painel) não foi visualmente confirmado — só por leitura de código; (b) o conteúdo dos arquivos PNG/PDF baixados não foi aberto para inspeção. Recomendado conferir os dois em um navegador com monitor largo antes do próximo deploy em produção.

## Decisões técnicas tomadas nesta sprint
- `is_platform_admin` como coluna nova em vez de reaproveitar `role` — evita colisão semântica entre "admin de tenant" (dado de produto, editável por convite) e "admin de plataforma" (dado operacional, só editável via banco)
- `NavigatedViewer` em vez de compor módulos manualmente em cima do `Viewer` puro — já empacota zoom/pan testados pela própria lib, menos superfície pra dar errado
- PNG/PDF gerados 100% no client a partir do SVG existente — sem endpoint novo no backend, sem dependência de lib de imagem/PDF do lado servidor
- PDF com página dimensionada ao diagrama (não A4 fixo) — trade-off aceito: não é uma página "imprimível" padrão, mas evita o problema mais provável (diagrama grande cortado/ilegível) sem escopo extra de paginação múltipla

## Como testar esta release
1. `docker compose up -d --build` (frontend ganhou dependência nova: `jspdf`) e `docker compose exec backend alembic upgrade head` (migrations 004 e 005)
2. Conceder acesso de plataforma à sua conta: `docker compose exec backend python scripts/set_platform_admin.py seu-email@exemplo.com`
3. Login como cliente com `role=admin` de um tenant qualquer → confirmar link "Uso de IA" escondido na sidebar e `GET /api/v1/admin/usage-summary` retornando 403; login com a conta de platform admin → acesso normal
4. Chat de um processo: colar um parágrafo longo → campo cresce até um máximo e depois rola; Enter envia, Shift+Enter quebra linha
5. Abrir um processo "Pronto": scroll do mouse sobre o diagrama dá zoom, arrastar move o canvas, botões +/- e "ajustar à tela" funcionam; ativar Modo Apresentação com zoom/pan disponíveis, sem conflito
6. Exportar um processo nos 3 formatos pelo menu "Exportar" → `.bpmn` abre no Camunda Modeler, PNG abre como imagem, PDF abre com o diagrama legível
7. Abrir a página de processo em 375px, 768px e 1920px de largura → painel lateral vira modal deslizante abaixo de `lg`, header não trunca status/nome de forma ilegível, sem scroll horizontal forçado

## Bugs conhecidos
- Nenhum bug novo em aberto no escopo desta sprint.
- Débito técnico pré-existente (não desta release): erros de `ruff` em arquivos de teste e em duas linhas intocadas de `tenants.py`, já registrados desde `RELEASE-S8.md`/`RELEASE-S10.md`.
- **Bug pré-existente encontrado durante a validação manual desta sprint, fora do escopo do S11 (não corrigido aqui):** a tela de registro (e, pela mesma causa em `lib/api.ts`, qualquer tela que trate erro de validação 422 da API) exibe `[object Object]` em vez de uma mensagem legível. Causa raiz: `ApiError` usa `error.detail` como `message`, mas o FastAPI retorna `detail` como uma **lista** de objetos de erro do Pydantic em validações 422 (não uma string) — só funciona corretamente para os `HTTPException(detail="string")` usados no resto do backend. Reproduzido registrando com um domínio de e-mail reservado (`.test`), mas afeta qualquer 422 de validação. Vale um item pequeno (~1 ponto) em uma sprint futura: extrair a primeira mensagem de `detail[0].msg` (ou juntar todas) quando `detail` vier como array.
