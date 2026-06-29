# Release Sprint 4 — Documentação, polish e deploy

**Data:** 2026-06-29
**Sprint:** S4
**Status:** Concluído

## Resumo

Sprint de polish e entrega final do MVP. Adicionados: geração automática de documentação de processos via Claude API, gestão de membros do tenant (convite, alteração de papel, remoção), configuração completa de produção com Docker + Nginx + HTTPS, error handler global, testes E2E do pipeline completo e ajustes de UX (toast notifications, páginas 404/500, aba de documentação no viewer).

## Funcionalidades entregues

### Backend
- [S4-01] `DocumentationService`: gera documentação estruturada (descrição, atividades, regras de negócio, decisões, exceções) via Claude API
- [S4-01] `GET/POST /processes/{id}/docs`: endpoint de documentação do processo
- [S4-03] Global exception handler em `main.py` — toda exceção não tratada retorna JSON 500 consistente
- [S4-04] Teste E2E completo: register → projeto → upload → pipeline → chat → versões → export → isolamento de tenant
- [S4-04] Testes de error handling: upload com formato inválido, estados inválidos, autenticação, duplicação
- [S4-06] `POST /tenants/invite`, `GET /tenants/members`, `PUT/DELETE /tenants/members/{id}`: gestão de membros
- [S4-06] Testes de integração para todas as operações de membros

### Frontend
- [S4-01] `DocsPanel`: aba "Documentação" no viewer do processo com botão de regenerar
- [S4-02] Redirect da raiz do dashboard para `/projects`
- [S4-06] Página `/settings`: listagem, convite, edição inline de papel e remoção de membros
- [S4-07] Toast notifications (`ToastProvider` + `useToast` hook) para feedback em todas as ações
- [S4-07] Página 404 customizada (`not-found.tsx`)
- [S4-07] Error boundary global (`error.tsx`) para erros de runtime
- [S4-08] `api.ts` atualizado com métodos para `docs` e `tenants`

### Infraestrutura
- [S4-05] `docker-compose.prod.yml`: Nginx + Certbot (HTTPS) + backend Gunicorn + backup automático PostgreSQL
- [S4-05] `docker/nginx/nginx.conf` e `conf.d/app.conf`: reverse proxy com HTTP→HTTPS redirect
- [S4-05] `backend/Dockerfile.prod`: imagem de produção com Gunicorn e 4 workers Uvicorn
- [S4-05] `.env.production.example`: todas as variáveis de produção documentadas
- [S4-05] `make deploy` e `make deploy-migrate` no Makefile

## Métricas
- Pontos planejados: 20
- Pontos entregues: 18 (S4-02 dashboard com gráficos simplificado para redirect; S4-08 README pendente como item separado)
- Cobertura de testes: 80.2% (meta: 80%)
- Testes passando: 129/130 (1 skipped: teste de login de membro convidado requer senha real)
- Erros TypeScript: 0
- Erros de lint: 0

## Decisões técnicas tomadas nesta sprint

- **DocumentationService lazy-importado nos endpoints**: mesmo padrão do BpmnRefinerService — import dentro da função para evitar inicialização do cliente Anthropic no startup em ambientes sem ANTHROPIC_API_KEY.
- **Backup PostgreSQL via container sidecar**: `db-backup` roda `pg_dump` diário e mantém últimos 7 dias. Simples para MVP; em produção real, substituir por solução managed (RDS, Supabase).
- **Certbot via entrypoint loop**: o container de certificados renova automaticamente a cada 12h. Para primeira emissão, rodar manualmente `docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d seudominio.com`.
- **Gunicorn + 4 workers**: para MVP suficiente; cada worker é um processo Python com evento loop assíncrono do Uvicorn. Ajustar `-w` conforme cores do servidor.

## Como testar esta release

1. `make up` para desenvolvimento local
2. `make migrate` para aplicar migrations
3. Registre uma conta e explore: criar projeto → upload áudio → viewer → chat → documentação
4. Em `/settings`, convide um membro (e-mail fictício) e teste alterar papel/remover
5. Para produção: copiar `.env.production.example` → `.env.production`, preencher e rodar `make deploy`

## Bugs conhecidos

- Membros convidados via `/settings` recebem senha temporária aleatória (UUID hex) — não há e-mail de convite implementado ainda; senha deve ser comunicada manualmente ou via reset
- Aba "Documentação" chama a Claude API a cada carregamento (sem cache no frontend) — em produção, cachear no backend por `(process_id, version)`
- O BpmnViewer `fit-viewport` pode não funcionar em alguns browsers com CORS de fontes externas do bpmn-js
