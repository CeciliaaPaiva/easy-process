# Release Sprint 3 — Interface e Visualização BPMN

**Data:** 2026-06-29
**Sprint:** S3
**Status:** Concluído

## Resumo

Entrega da interface completa da plataforma: listagem de projetos, detalhes do projeto, upload de áudio com progress bar, visualizador BPMN interativo (bpmn-js), chat de refinamento em linguagem natural e histórico de versões com restauração. No backend, foram adicionados os endpoints de chat e versões específicas, além do serviço `BpmnRefinerService` que chama a Claude API para refinar diagramas.

## Funcionalidades entregues

### Backend
- [S3-05] `BpmnRefinerService` — refina BPMN via Claude API com histórico de mensagens e retry automático até 3 tentativas
- [S3-05] `GET /processes/{id}/versions/{version}` — retorna BPMN de versão específica
- [S3-05] `POST /processes/{id}/versions/{version}/restore` — restaura versão antiga criando nova versão
- [S3-06] `GET /processes/{id}/chat` — histórico de mensagens do chat
- [S3-06] `POST /processes/{id}/chat` — envia instrução, refina BPMN, salva par user/assistant, cria nova versão
- [S3-07] Testes unitários para `BpmnRefinerService` (5 testes)
- [S3-07] Testes de integração para endpoints de chat (5 testes)
- [S3-07] Testes de integração para endpoints de versões (5 testes)

### Frontend
- [S3-01] Página de listagem de projetos (`/projects`) — cards, modal de criação, busca em tempo real, skeletons
- [S3-02] Página de detalhes do projeto (`/projects/[id]`) — lista de processos com status badges, modal de upload
- [S3-03] Componente `AudioUploader` — drag-and-drop, validação por formato/tamanho, progress bar XHR, polling de status
- [S3-04] Componente `BpmnViewer` (bpmn-js) — import dinâmico `{ssr: false}`, zoom automático ao carregar
- [S3-04] Página do processo (`/projects/[id]/processes/[processId]`) — polling de status, visualizador, chat lateral, botão de exportação
- [S3-06] Componente `ChatWindow` — histórico, envio otimista, atualização live do viewer ao receber resposta
- [S3-06] Painel de versões — listagem, restauração com feedback de loading
- [S3-08] Componentes UI criados: `Badge`, `Card`, `Dialog`, `Progress`, `Skeleton`, `Textarea`, `StatusBadge`
- [S3-08] `api.ts` estendido com métodos tipados para projects, processes, versions, chat e upload multipart com progresso

## Métricas
- Pontos planejados: 20
- Pontos entregues: 20
- Cobertura de testes backend: ~86% (meta: 80%)
- Testes passando: 93/93
- Erros de TypeScript: 0
- Erros de lint (novos): 0

## Decisões técnicas tomadas nesta sprint

- **bpmn-js com dynamic import**: `next/dynamic` com `ssr: false` para evitar erros de SSR pois a lib usa APIs do browser. Webpack configurado em `next.config.mjs` para shimmar módulos Node.js não disponíveis no browser.
- **Mock target para serviço lazy-imported**: `BpmnRefinerService` é importado dentro da função do endpoint (lazy import). Nos testes, o mock correto é `app.services.bpmn_refiner.bpmn_refiner_service.refine` (patch no método da instância singleton), não `app.api.v1.processes.bpmn_refiner_service.refine` (que não existe como atributo de módulo).
- **Upload com XHR em vez de fetch**: `api.processes.upload` usa `XMLHttpRequest` para suportar `onprogress` e exibir barra de progresso real durante o envio.
- **Polling de status no frontend**: processo em estados não-finais (`pending`, `transcribing`, `generating`) dispara polling a cada 3 segundos; o intervalo é limpo automaticamente quando o status muda para `ready` ou `error`.

## Como testar esta release

1. `make up` para subir todos os serviços
2. Acesse `http://localhost:3000` e registre uma conta
3. Crie um projeto em `/projects`
4. Na tela do projeto, clique em "Novo processo" e faça upload de um áudio .mp3
5. Acompanhe o polling de status (pending → transcribing → generating → ready)
6. Com status "ready", o diagrama BPMN é exibido automaticamente
7. Use o chat lateral para refinar o BPMN com linguagem natural
8. Clique em "Versões" para ver o histórico e restaurar versões anteriores
9. Clique em "Exportar" para baixar o arquivo `.bpmn`

## Bugs conhecidos

- O polling de status usa `setInterval` direto — em produção, substituir por WebSocket ou SSE para reduzir carga
- O `BpmnViewer` não suporta edição (viewer only); edição direta será considerada no Sprint 4 se necessário
