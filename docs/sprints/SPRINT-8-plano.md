# Plano Sprint 8 — Gravação de áudio in-app

**Status:** Em execução
**Sprint anterior:** S7 (ver `docs/releases/RELEASE-S7.md`)
**Sprint seguinte:** S9 — animação de fluxo/gargalos no BPMN (ver `docs/sprints/SPRINT-9-plano.md`, ainda não implementada)

## Contexto

O pedido original agrupava duas features (gravação de áudio + animação no BPMN) numa sprint só. Foram separadas em duas: a gravação de áudio entra primeiro porque é a que tem risco técnico já conhecido (ver abaixo) e valor de produto mais imediato (reduz fricção: usuário grava a entrevista na hora, sem precisar de outro app + exportar + fazer upload).

Investigação prévia mostrou que **não existe nenhuma validação de duração de áudio** hoje (`backend/app/services/storage.py::save_audio` só valida extensão e tamanho em MB). Isso já causou um incidente real: um áudio de ~72min estourou o limite de output tokens do Gemini (`finish_reason=MAX_TOKENS`, 65.520 tokens) e quebrou o pipeline silenciosamente (processo caía para `status=error` sem mensagem útil). Gravação in-app **piora esse risco** — grava-se sem noção prévia de tamanho de arquivo — então a validação de duração é pré-requisito de viabilidade desta sprint, não um extra.

## Escopo

Gravar áudio direto no navegador (`getUserMedia` + `MediaRecorder`, APIs nativas — sem lib nova), como alternativa ao upload de arquivo, dentro do mesmo formulário de criação de processo.

**Avaliação de performance:** gravação é 100% client-side; zero custo de servidor durante a gravação, tráfego de rede só acontece no envio (idêntico ao upload hoje). O risco real não é performance de servidor — é duração descontrolada alimentando o mesmo bug do Gemini. Mitigação: limite de duração aplicado nos dois lados (client faz auto-stop; backend rejeita antes de salvar/disparar o pipeline).

## Backlog

| Item | Descrição | Pontos |
|---|---|---|
| S8-01 | `AudioRecorder.tsx`: getUserMedia + MediaRecorder, cronômetro, auto-stop no limite, preview (`<audio controls>`) antes de enviar | 3 |
| S8-02 | Toggle "Enviar arquivo / Gravar áudio" dentro de `AudioUploader.tsx`, reusando `api.processes.upload` sem mudar contrato | 2 |
| S8-03 | Validação de duração no backend: `ffprobe` (novo pacote `ffmpeg` no `backend/Dockerfile`) + `MAX_AUDIO_DURATION_MINUTES` em `core/config.py`, aplicado em `storage.py::save_audio` para upload **e** gravação | 3 |
| S8-04 | Testes: `AudioRecorder` (mock de `MediaRecorder`/`getUserMedia`) + `test_storage.py` (áudio dentro/fora do limite) — inclui bootstrap de Vitest no frontend (nunca foi configurado, apesar de estar no `package.json`) | 3 |
| **Total** | | **11** |

Bem abaixo da capacidade de 20pts/sprint — sobra espaço para o bootstrap de testes do frontend (gap pré-existente, não orçado originalmente) sem estourar a sprint.

## Decisões técnicas

- **Formato de gravação:** `audio/webm;codecs=opus` — suportado nativamente em Chrome/Firefox/Edge, e `.webm` **já estava** na allowlist do backend (`storage.py::ALLOWED_EXTENSIONS`). Safari tem suporte fraco a `MediaRecorder`; v1 assume Chrome/Firefox/Edge como alvo e apenas avisa o usuário se a API não estiver disponível, sem fallback mp4 (evita escopo extra).
- **Limite de duração:** `MAX_AUDIO_DURATION_MINUTES = 30` (default). O incidente anterior estourou com ~72min; 30min dá margem confortável (menos da metade) mantendo espaço para entrevistas normais.
- **Probing de duração via `ffprobe`** (não `mutagen`/lib Python pura): é o único jeito robusto de pegar duração de qualquer container (mp3/wav/m4a/ogg/**webm**) — suporte de `mutagen` a webm/opus é inconsistente.

## Como testar (planejado)

1. `docker compose up -d --build` (Dockerfile do backend mudou — precisa rebuild)
2. Abrir "Novo processo" → alternar para "Gravar áudio" → gravar, parar, ouvir o preview, enviar
3. Confirmar que o processo entra no pipeline normalmente (mesma máquina de estados de sempre)
4. Tentar simular um áudio acima do limite (ou ajustar `MAX_AUDIO_DURATION_MINUTES` para um valor baixo temporariamente) e confirmar rejeição com mensagem clara, tanto por upload quanto por gravação
5. `make test` e `docker compose exec frontend npm test`
