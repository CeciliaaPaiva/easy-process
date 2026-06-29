"""
Teste end-to-end do fluxo completo:
register → criar projeto → upload → pipeline → chat → export → versões
"""
import uuid

from app.services.bpmn_generator import BpmnGenerationResult
from app.services.bpmn_refiner import BpmnRefinementResult
from app.services.transcription import TranscriptionResult
from app.workers.process_audio import process_audio_pipeline
from tests.integration.conftest import register_user

BPMN_V1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" name="Início"/>
    <bpmn:task id="Task_1" name="Analisar pedido"/>
    <bpmn:exclusiveGateway id="GW_1" name="Aprovado?"/>
    <bpmn:task id="Task_2" name="Notificar aprovação"/>
    <bpmn:endEvent id="End_1" name="Fim"/>
  </bpmn:process>
</bpmn:definitions>"""

BPMN_V2 = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" name="Início"/>
    <bpmn:task id="Task_1" name="Analisar pedido"/>
    <bpmn:task id="Task_3" name="Validar documentos"/>
    <bpmn:exclusiveGateway id="GW_1" name="Aprovado?"/>
    <bpmn:task id="Task_2" name="Notificar aprovação"/>
    <bpmn:endEvent id="End_1" name="Fim"/>
  </bpmn:process>
</bpmn:definitions>"""

TRANSCRIPTION = "O analista recebe o pedido, analisa e encaminha para aprovação do gerente."


class TestFullPipelineFlow:
    async def test_register_to_export_full_flow(self, client, mocker):
        # 1. Registrar usuário
        auth = await register_user(client)
        assert "headers" in auth

        # 2. Criar projeto
        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Projeto E2E", "description": "Teste completo do pipeline"},
            headers=auth["headers"],
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        # 3. Upload de áudio (pipeline mockado)
        mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/e2e/audio.mp3")
        mocker.patch("app.api.v1.processes.process_audio_pipeline")
        mocker.patch(
            "app.workers.process_audio.transcription_service.transcribe",
            return_value=TranscriptionResult(text=TRANSCRIPTION, duration=30.0),
        )
        mocker.patch(
            "app.workers.process_audio.bpmn_generator_service.generate",
            return_value=BpmnGenerationResult(
                bpmn_xml=BPMN_V1,
                summary="Processo de aprovação de pedidos.",
                actors=["Analista", "Gerente"],
                tasks=[{"name": "Analisar pedido"}, {"name": "Notificar aprovação"}],
            ),
        )

        upload_resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Processo E2E"},
            files={"audio": ("audio.mp3", b"fake-audio-bytes", "audio/mpeg")},
            headers=auth["headers"],
        )
        assert upload_resp.status_code == 201
        process_id = uuid.UUID(upload_resp.json()["id"])
        assert upload_resp.json()["status"] == "pending"

        # 4. Executar pipeline
        await process_audio_pipeline(process_id)

        # 5. Verificar: processo ready com BPMN e transcrição
        proc_resp = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth["headers"],
        )
        assert proc_resp.status_code == 200
        proc = proc_resp.json()
        assert proc["status"] == "ready"
        assert proc["transcription"] == TRANSCRIPTION
        assert proc["bpmn_xml"] == BPMN_V1
        assert proc["summary"] == "Processo de aprovação de pedidos."
        assert proc["version"] == 1

        # 6. Verificar: BPMN endpoint
        bpmn_resp = await client.get(
            f"/api/v1/processes/{process_id}/bpmn",
            headers=auth["headers"],
        )
        assert bpmn_resp.status_code == 200
        assert "bpmn:definitions" in bpmn_resp.json()["bpmn_xml"]

        # 7. Chat de refinamento
        mocker.patch(
            "app.services.bpmn_refiner.bpmn_refiner_service.refine",
            return_value=BpmnRefinementResult(
                bpmn_xml=BPMN_V2,
                change_description="Adicionada tarefa de validação de documentos.",
            ),
        )

        chat_resp = await client.post(
            f"/api/v1/processes/{process_id}/chat",
            json={"message": "Adicione uma tarefa de validação de documentos antes do gateway"},
            headers=auth["headers"],
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert chat_data["version"] == 2
        assert "Validar documentos" in chat_data["bpmn_xml"]
        assert chat_data["user_message"]["role"] == "user"
        assert chat_data["assistant_message"]["role"] == "assistant"

        # 8. Verificar: BPMN atualizado após chat
        proc_v2 = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth["headers"],
        )
        assert proc_v2.json()["version"] == 2
        assert "Validar documentos" in proc_v2.json()["bpmn_xml"]

        # 9. Histórico de chat
        hist_resp = await client.get(
            f"/api/v1/processes/{process_id}/chat",
            headers=auth["headers"],
        )
        assert hist_resp.status_code == 200
        messages = hist_resp.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

        # 10. Listar versões
        versions_resp = await client.get(
            f"/api/v1/processes/{process_id}/versions",
            headers=auth["headers"],
        )
        assert versions_resp.status_code == 200
        versions = versions_resp.json()
        assert len(versions) == 2
        version_numbers = [v["version"] for v in versions]
        assert 1 in version_numbers
        assert 2 in version_numbers

        # 11. Obter versão específica
        v1_resp = await client.get(
            f"/api/v1/processes/{process_id}/versions/1",
            headers=auth["headers"],
        )
        assert v1_resp.status_code == 200
        assert "Analisar pedido" in v1_resp.json()["bpmn_xml"]

        # 12. Restaurar versão 1
        restore_resp = await client.post(
            f"/api/v1/processes/{process_id}/versions/1/restore",
            headers=auth["headers"],
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["version"] == 3
        assert "Validar documentos" not in restore_resp.json()["bpmn_xml"]

        # 13. Exportar .bpmn
        export_resp = await client.get(
            f"/api/v1/processes/{process_id}/export",
            headers=auth["headers"],
        )
        assert export_resp.status_code == 200
        assert "application/xml" in export_resp.headers["content-type"]
        assert "bpmn:definitions" in export_resp.text
        assert "attachment" in export_resp.headers.get("content-disposition", "")

    async def test_pipeline_error_flow(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects",
            json={"name": "Projeto Erro"},
            headers=auth["headers"],
        )
        project_id = proj.json()["id"]

        mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/e2e/audio.mp3")
        mocker.patch("app.api.v1.processes.process_audio_pipeline")
        mocker.patch(
            "app.workers.process_audio.transcription_service.transcribe",
            side_effect=RuntimeError("Whisper indisponível"),
        )

        upload = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Processo Erro"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        process_id = uuid.UUID(upload.json()["id"])
        await process_audio_pipeline(process_id)

        proc = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth["headers"],
        )
        assert proc.json()["status"] == "error"

        # Chat bloqueado em processo com erro
        chat = await client.post(
            f"/api/v1/processes/{process_id}/chat",
            json={"message": "teste"},
            headers=auth["headers"],
        )
        assert chat.status_code == 400

    async def test_tenant_isolation_in_pipeline(self, client, mocker):
        """Tenant B não pode acessar processos do tenant A."""
        auth_a = await register_user(client)
        auth_b = await register_user(client)

        proj = await client.post(
            "/api/v1/projects",
            json={"name": "Projeto A"},
            headers=auth_a["headers"],
        )
        project_id = proj.json()["id"]

        mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/fake/audio.mp3")
        mocker.patch("app.api.v1.processes.process_audio_pipeline")

        upload = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Processo A"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth_a["headers"],
        )
        process_id = upload.json()["id"]

        for path in [
            f"/api/v1/processes/{process_id}",
            f"/api/v1/processes/{process_id}/bpmn",
            f"/api/v1/processes/{process_id}/chat",
            f"/api/v1/processes/{process_id}/versions",
        ]:
            resp = await client.get(path, headers=auth_b["headers"])
            assert resp.status_code == 404, f"Endpoint {path} deveria retornar 404 para outro tenant"
