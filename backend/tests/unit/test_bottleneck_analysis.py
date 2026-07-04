import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.bottleneck_analysis import DISCLAIMER, BottleneckAnalysisService

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Aprovar pedido"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

MOCK_ANALYSIS = {
    "findings": [
        {
            "title": "Aprovação manual única",
            "description": "A tarefa depende de uma única pessoa, gerando ponto único de falha.",
            "severity": "alta",
            "related_elements": ["Task_1"],
        }
    ]
}


def _make_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


class TestBottleneckAnalysisService:
    @pytest.fixture
    def service(self):
        return BottleneckAnalysisService()

    @pytest.fixture
    def generate_mock(self, service, mocker):
        return mocker.patch.object(
            service._client.aio.models,
            "generate_content",
            new_callable=AsyncMock,
        )

    @pytest.mark.asyncio
    async def test_analyze_returns_findings(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response(json.dumps(MOCK_ANALYSIS))

        result = await service.analyze(VALID_BPMN)

        assert len(result.findings) == 1
        assert result.findings[0].title == "Aprovação manual única"
        assert result.findings[0].severity == "alta"
        assert result.findings[0].related_elements == ["Task_1"]
        assert result.disclaimer == DISCLAIMER

    @pytest.mark.asyncio
    async def test_analyze_returns_empty_findings(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response(json.dumps({"findings": []}))

        result = await service.analyze(VALID_BPMN)

        assert result.findings == []

    @pytest.mark.asyncio
    async def test_raises_value_error_for_empty_bpmn(self, service):
        with pytest.raises(ValueError):
            await service.analyze("")

        with pytest.raises(ValueError):
            await service.analyze("   ")

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_invalid_json(self, service, generate_mock):
        generate_mock.return_value = _make_gemini_response("não é JSON")

        with pytest.raises(RuntimeError, match="inválida"):
            await service.analyze(VALID_BPMN)
