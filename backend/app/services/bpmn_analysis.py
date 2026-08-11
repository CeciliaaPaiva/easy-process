"""Etapa de ANÁLISE do pipeline de geração de BPMN (Sprint 12, S12-02).

Responsabilidade única: ler a transcrição e extrair a estrutura do processo
em um grafo JSON tipado — atores (com classificação interno/externo),
atividades (com tipo de execução), gateways (com tipo e papel) e as
transições entre eles. NÃO gera XML — isso é responsabilidade separada de
`bpmn_generator.py`, que só traduz o grafo já resolvido aqui.

Extraída de `bpmn_generator.py`, que antes fazia análise semântica e
tradução para XML na mesma chamada — ver `docs/sprints/SPRINT-12-plano.md`
e `docs/sprints/SPRINT-12-investigacao.md` para o raciocínio por trás da
separação (achado empírico: a informação da análise já saía correta, o
problema estava na tradução para XML não aproveitá-la)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.services.bpmn_prompts import SEMANTIC_MODELING_RULES
from app.services.llm_usage import record_usage

ActivityType = Literal[
    "manual", "user", "service", "business_rule", "send", "receive", "generic"
]
GatewayType = Literal["exclusive", "parallel", "inclusive"]
GatewayRole = Literal["split", "join"]

_SYSTEM_INSTRUCTION = f"""\
Você é uma analista de processos de negócio. Sua única tarefa é ANALISAR a
transcrição de uma entrevista e extrair a estrutura do processo em um grafo
JSON — você NÃO desenha nem gera XML BPMN, isso é feito por outra etapa a
partir do que você extrair aqui. Dedique toda sua atenção a entender o
processo corretamente; a tradução mecânica para XML não é problema seu.

{SEMANTIC_MODELING_RULES}

FORMATO DO GRAFO — descreva o processo como uma lista de passos conectados
por transições (`flows`), não como texto livre:

- Cada ATIVIDADE (`activities`) tem um `id` curto e único (ex:
  "confirmar_pedido"), um `responsible` que deve bater EXATAMENTE com um
  nome em `actors`, e um `activity_type` (a classificação de tipo de tarefa
  da regra 2 acima).
- Cada GATEWAY (`gateways`) tem um `id` único, um `role` ("split" = ponto de
  divisão, "join" = ponto de junção) e um `gateway_type` (regra 1 acima).
  Todo split com mais de uma saída condicional deve ter um join
  correspondente mais adiante, exceto quando um ramo termina direto em fim
  de processo.
- `flows` é a lista COMPLETA de transições do processo, cada uma com
  `source_id` e `target_id` apontando para um id de atividade/gateway, ou
  para os ids especiais reservados: "start" (só como source do primeiro
  passo) e "end" ou "end:<motivo>" (ex: "end:pedido_cancelado", quando há
  mais de um jeito do processo terminar). Toda atividade/gateway deve ser
  alcançável a partir de "start" e todo caminho deve chegar a algum "end".
  Cada flow que sai de um gateway "split" com mais de uma saída deve ter um
  `label` (ex: "Sim"/"Não", ou a condição do ramo).
- `actors`: marque `is_external=true` só para participantes de FORA da
  organização/processo modelado (regra 3 acima — vira pool separado).
  Atores internos (mesma organização) usam `is_external=false` — viram
  raia, não pool.
- `annotations`: uma nota associada a um `step_id` (atividade ou gateway)
  explicando algo que a transcrição deixou implícito — mesmo critério de
  uso moderado da regra 4 acima.

Responda respeitando estritamente o schema JSON fornecido — sem markdown,
sem texto fora do JSON."""

_RETRY_PROMPT = """\
A análise retornada tem um problema: {error}

ANÁLISE COM PROBLEMA (JSON):
{invalid_json}

Corrija o problema apontado e retorne o JSON completo novamente, respeitando
o schema."""


class _ActorSchema(BaseModel):
    name: str
    is_external: bool


class _ActivitySchema(BaseModel):
    id: str
    name: str
    responsible: str
    activity_type: ActivityType


class _GatewaySchema(BaseModel):
    id: str
    role: GatewayRole
    gateway_type: GatewayType
    question: str | None = None


class _FlowSchema(BaseModel):
    source_id: str
    target_id: str
    label: str | None = None


class _AnnotationSchema(BaseModel):
    step_id: str
    text: str


class _AnalysisSchema(BaseModel):
    summary: str
    actors: list[_ActorSchema]
    activities: list[_ActivitySchema]
    gateways: list[_GatewaySchema] = []
    flows: list[_FlowSchema]
    business_rules: list[str] = []
    annotations: list[_AnnotationSchema] = []


@dataclass
class ActorInfo:
    name: str
    is_external: bool


@dataclass
class ActivityInfo:
    id: str
    name: str
    responsible: str
    activity_type: str


@dataclass
class GatewayInfo:
    id: str
    role: str
    gateway_type: str
    question: str | None = None


@dataclass
class FlowInfo:
    source_id: str
    target_id: str
    label: str | None = None


@dataclass
class AnnotationInfo:
    step_id: str
    text: str


@dataclass
class ProcessAnalysisResult:
    summary: str
    actors: list[ActorInfo] = field(default_factory=list)
    activities: list[ActivityInfo] = field(default_factory=list)
    gateways: list[GatewayInfo] = field(default_factory=list)
    flows: list[FlowInfo] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    annotations: list[AnnotationInfo] = field(default_factory=list)


def _validate_graph(data: _AnalysisSchema) -> str | None:
    """Checagem de sanidade estrutural — não é validação semântica completa
    (isso é S12-03, sobre o XML final), só garante que o grafo não tem
    referência solta antes de chegar na etapa de modelagem."""
    node_ids = [a.id for a in data.activities] + [g.id for g in data.gateways]
    if len(node_ids) != len(set(node_ids)):
        return "ids de atividades/gateways devem ser únicos"

    actor_names = {a.name for a in data.actors}
    for activity in data.activities:
        if activity.responsible not in actor_names:
            return (
                f"atividade '{activity.id}' tem responsible='{activity.responsible}' "
                "que não está na lista de actors"
            )

    if not any(f.source_id == "start" for f in data.flows):
        return "nenhum flow parte de 'start'"

    node_id_set = set(node_ids)
    for f in data.flows:
        for ref, role in (
            (f.source_id, "source_id"),
            (f.target_id, "target_id"),
        ):
            if ref == "start" or ref.startswith("end"):
                continue
            if ref not in node_id_set:
                return (
                    f"flow referencia {role}='{ref}' que não existe em "
                    "activities/gateways"
                )

    return None


def _to_result(data: _AnalysisSchema) -> ProcessAnalysisResult:
    return ProcessAnalysisResult(
        summary=data.summary,
        actors=[ActorInfo(a.name, a.is_external) for a in data.actors],
        activities=[
            ActivityInfo(a.id, a.name, a.responsible, a.activity_type)
            for a in data.activities
        ],
        gateways=[
            GatewayInfo(g.id, g.role, g.gateway_type, g.question) for g in data.gateways
        ],
        flows=[FlowInfo(f.source_id, f.target_id, f.label) for f in data.flows],
        business_rules=list(data.business_rules),
        annotations=[AnnotationInfo(a.step_id, a.text) for a in data.annotations],
    )


class AnalysisService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.gemini_model_analysis

    async def analyze(
        self,
        transcription: str,
        max_retries: int = 3,
        process_id: str | None = None,
        tenant_id: str | None = None,
    ) -> ProcessAnalysisResult:
        if not transcription or len(transcription.strip()) < 50:
            raise ValueError("Transcrição muito curta ou vazia (mínimo 50 caracteres)")

        transcription = transcription[:50_000]
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_AnalysisSchema,
            temperature=0.1,
        )

        last_error = "formato inválido"
        prompt = f"TRANSCRIÇÃO:\n{transcription}"

        for attempt in range(1, max_retries + 1):
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
            await record_usage(
                "bpmn_analysis",
                tenant_id,
                process_id,
                response,
                self._model_name,
                attempt,
            )

            data = response.parsed
            if data is None:
                last_error = "JSON inválido na resposta"
                prompt = (
                    f"TRANSCRIÇÃO:\n{transcription}\n\n"
                    "A resposta anterior não seguiu o schema JSON esperado. "
                    "Retorne novamente respeitando o schema."
                )
                continue

            error = _validate_graph(data)
            if error is None:
                return _to_result(data)

            last_error = error
            prompt = _RETRY_PROMPT.format(
                error=error, invalid_json=data.model_dump_json()
            )

        raise RuntimeError(
            f"Não foi possível analisar o processo após {max_retries} tentativas. "
            f"Último erro: {last_error}"
        )


analysis_service = AnalysisService()
