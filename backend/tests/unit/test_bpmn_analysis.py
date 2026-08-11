from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.bpmn_analysis import AnalysisService

TRANSCRIPTION = (
    "O analista recebe a solicitação, avalia e encaminha para o gerente aprovar."
)

VALID_ANALYSIS = {
    "summary": "Processo de aprovação de solicitações.",
    "actors": [{"name": "Gerente", "is_external": False}],
    "activities": [
        {
            "id": "aprovar_solicitacao",
            "name": "Aprovar solicitação",
            "responsible": "Gerente",
            "activity_type": "user",
        }
    ],
    "gateways": [],
    "flows": [
        {"source_id": "start", "target_id": "aprovar_solicitacao", "label": None},
        {"source_id": "aprovar_solicitacao", "target_id": "end", "label": None},
    ],
    "business_rules": [],
    "annotations": [],
}


def _make_response(parsed: object) -> MagicMock:
    resp = MagicMock()
    resp.parsed = parsed
    resp.text = "" if parsed is None else "{}"
    resp.usage_metadata = None
    return resp


def _parsed(data: dict) -> MagicMock:
    """Simula o objeto Pydantic (`_AnalysisSchema`) retornado em
    `response.parsed` pelo google-genai, só com os atributos que o serviço
    lê — evita acoplar o teste ao schema Pydantic interno."""
    from app.services.bpmn_analysis import (
        _ActivitySchema,
        _ActorSchema,
        _AnalysisSchema,
        _AnnotationSchema,
        _FlowSchema,
        _GatewaySchema,
    )

    return _AnalysisSchema(
        summary=data["summary"],
        actors=[_ActorSchema(**a) for a in data["actors"]],
        activities=[_ActivitySchema(**a) for a in data["activities"]],
        gateways=[_GatewaySchema(**g) for g in data.get("gateways", [])],
        flows=[_FlowSchema(**f) for f in data["flows"]],
        business_rules=data.get("business_rules", []),
        annotations=[_AnnotationSchema(**a) for a in data.get("annotations", [])],
    )


class TestAnalysisService:
    @pytest.fixture
    def service(self):
        return AnalysisService()

    @pytest.fixture
    def mock_generate(self, service, mocker):
        return mocker.patch.object(
            service._client.aio.models, "generate_content", new=AsyncMock()
        )

    @pytest.mark.asyncio
    async def test_analyzes_transcription_into_graph(self, service, mock_generate):
        mock_generate.return_value = _make_response(_parsed(VALID_ANALYSIS))

        result = await service.analyze(TRANSCRIPTION)

        assert result.summary == VALID_ANALYSIS["summary"]
        assert result.actors[0].name == "Gerente"
        assert result.actors[0].is_external is False
        assert result.activities[0].activity_type == "user"
        assert result.flows[0].source_id == "start"

    @pytest.mark.asyncio
    async def test_raises_value_error_for_short_transcription(self, service):
        with pytest.raises(ValueError, match="curta"):
            await service.analyze("curto")

    @pytest.mark.asyncio
    async def test_retries_when_activity_responsible_not_in_actors(
        self, service, mock_generate
    ):
        """responsible que não bate com nenhum actor é um grafo inconsistente
        — deve virar retry, não passar adiante pra etapa de modelagem."""
        broken = {
            **VALID_ANALYSIS,
            "actors": [{"name": "Outra Pessoa", "is_external": False}],
        }
        mock_generate.side_effect = [
            _make_response(_parsed(broken)),
            _make_response(_parsed(VALID_ANALYSIS)),
        ]

        result = await service.analyze(TRANSCRIPTION, max_retries=2)
        assert result.actors[0].name == "Gerente"

    @pytest.mark.asyncio
    async def test_retries_when_flow_references_unknown_id(
        self, service, mock_generate
    ):
        broken = {
            **VALID_ANALYSIS,
            "flows": [
                {"source_id": "start", "target_id": "atividade_fantasma", "label": None}
            ],
        }
        mock_generate.side_effect = [
            _make_response(_parsed(broken)),
            _make_response(_parsed(VALID_ANALYSIS)),
        ]

        result = await service.analyze(TRANSCRIPTION, max_retries=2)
        assert result.flows[0].target_id == "aprovar_solicitacao"

    @pytest.mark.asyncio
    async def test_retries_when_no_flow_starts_from_start(self, service, mock_generate):
        broken = {
            **VALID_ANALYSIS,
            "flows": [
                {
                    "source_id": "aprovar_solicitacao",
                    "target_id": "end",
                    "label": None,
                }
            ],
        }
        mock_generate.side_effect = [
            _make_response(_parsed(broken)),
            _make_response(_parsed(VALID_ANALYSIS)),
        ]

        result = await service.analyze(TRANSCRIPTION, max_retries=2)
        assert any(f.source_id == "start" for f in result.flows)

    @pytest.mark.asyncio
    async def test_raises_runtime_error_after_max_retries(self, service, mock_generate):
        mock_generate.return_value = _make_response(None)

        with pytest.raises(RuntimeError, match="tentativas"):
            await service.analyze(TRANSCRIPTION, max_retries=2)

    @pytest.mark.asyncio
    async def test_retry_prompt_includes_invalid_graph_not_full_history(
        self, service, mock_generate
    ):
        broken = {
            **VALID_ANALYSIS,
            "flows": [
                {"source_id": "start", "target_id": "atividade_fantasma", "label": None}
            ],
        }
        mock_generate.side_effect = [
            _make_response(_parsed(broken)),
            _make_response(_parsed(VALID_ANALYSIS)),
        ]

        await service.analyze(TRANSCRIPTION, max_retries=2)

        second_call_contents = mock_generate.call_args_list[1].kwargs["contents"]
        assert isinstance(second_call_contents, str)
        assert "atividade_fantasma" in second_call_contents
