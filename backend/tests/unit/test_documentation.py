import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.documentation import DocumentationService

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Aprovar pedido"/>
    <bpmn:exclusiveGateway id="GW_1" name="Aprovado?"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

MOCK_DOC = {
    "description": "Processo de aprovação de pedidos.",
    "activities": [{"name": "Aprovar pedido", "responsible": "Gestor", "description": "Avalia o pedido", "inputs": ["Pedido"], "outputs": ["Aprovação"]}],
    "business_rules": ["Pedidos acima de R$1000 exigem aprovação do diretor"],
    "decision_points": [{"name": "Aprovado?", "criteria": "Valor e conformidade", "outcomes": ["Sim", "Não"]}],
    "exceptions": ["Pedido inválido retorna ao solicitante"],
}


def _make_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


class TestDocumentationService:
    @pytest.fixture
    def service(self):
        return DocumentationService()

    @pytest.fixture
    def generate_mock(self, service, mocker):
        return mocker.patch.object(
            service._client.aio.models,
            "generate_content",
            new_callable=AsyncMock,
        )

    @pytest.mark.asyncio
    async def test_generate_returns_structured_doc(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response(json.dumps(MOCK_DOC))

        result = await service.generate(VALID_BPMN)

        assert result.description == MOCK_DOC["description"]
        assert len(result.activities) == 1
        assert result.activities[0]["name"] == "Aprovar pedido"
        assert len(result.business_rules) == 1
        assert len(result.decision_points) == 1
        assert len(result.exceptions) == 1

    @pytest.mark.asyncio
    async def test_raises_value_error_for_empty_bpmn(self, service):
        with pytest.raises(ValueError):
            await service.generate("")

        with pytest.raises(ValueError):
            await service.generate("   ")

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_invalid_json(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response("não é JSON")

        with pytest.raises(RuntimeError, match="inválida"):
            await service.generate(VALID_BPMN)

    @pytest.mark.asyncio
    async def test_handles_missing_fields_gracefully(self, service, generate_mock):
        partial = {"description": "Processo sem atividades"}
        generate_mock.return_value = _make_gemini_response(json.dumps(partial))

        result = await service.generate(VALID_BPMN)
        assert result.description == "Processo sem atividades"
        assert result.activities == []
        assert result.business_rules == []
        assert result.exceptions == []
