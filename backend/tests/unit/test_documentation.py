import json
from unittest.mock import AsyncMock

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


class TestDocumentationService:
    @pytest.fixture
    def service(self):
        return DocumentationService()

    @pytest.mark.asyncio
    async def test_generate_returns_structured_doc(self, service, mocker):
        mock_content = mocker.MagicMock()
        mock_content.text = json.dumps(MOCK_DOC)
        mock_response = mocker.MagicMock()
        mock_response.content = [mock_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

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
    async def test_raises_runtime_error_on_invalid_json(self, service, mocker):
        mock_content = mocker.MagicMock()
        mock_content.text = "não é JSON"
        mock_response = mocker.MagicMock()
        mock_response.content = [mock_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

        with pytest.raises(RuntimeError, match="inválida"):
            await service.generate(VALID_BPMN)

    @pytest.mark.asyncio
    async def test_handles_missing_fields_gracefully(self, service, mocker):
        partial = {"description": "Processo sem atividades"}
        mock_content = mocker.MagicMock()
        mock_content.text = json.dumps(partial)
        mock_response = mocker.MagicMock()
        mock_response.content = [mock_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

        result = await service.generate(VALID_BPMN)
        assert result.description == "Processo sem atividades"
        assert result.activities == []
        assert result.business_rules == []
        assert result.exceptions == []
