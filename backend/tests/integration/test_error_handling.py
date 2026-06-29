"""
Testes de tratamento de erros e edge cases — S4-03.
"""
import io

import pytest

from tests.integration.conftest import register_user


class TestGlobalErrorHandler:
    async def test_health_endpoint_returns_200(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    async def test_unknown_route_returns_404(self, client):
        resp = await client.get("/api/v1/rota-inexistente")
        assert resp.status_code == 404

    async def test_method_not_allowed_returns_405(self, client):
        resp = await client.delete("/api/v1/health")
        assert resp.status_code == 405


class TestUploadEdgeCases:
    async def test_upload_invalid_format_returns_400(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects", json={"name": "P"}, headers=auth["headers"]
        )
        project_id = proj.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Teste"},
            files={"audio": ("video.mp4", b"fake", "video/mp4")},
            headers=auth["headers"],
        )
        assert resp.status_code == 400
        assert "formato" in resp.json()["detail"].lower() or "inválido" in resp.json()["detail"].lower()

    async def test_upload_missing_name_returns_422(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects", json={"name": "P"}, headers=auth["headers"]
        )
        project_id = proj.json()["id"]

        resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        assert resp.status_code == 422

    async def test_upload_to_nonexistent_project_returns_404(self, client, mocker):
        import uuid
        auth = await register_user(client)

        resp = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/processes",
            data={"name": "Teste"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        assert resp.status_code == 404

    async def test_upload_to_archived_project_returns_404(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects", json={"name": "Para arquivar"}, headers=auth["headers"]
        )
        project_id = proj.json()["id"]
        await client.delete(f"/api/v1/projects/{project_id}", headers=auth["headers"])

        resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Teste"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        assert resp.status_code == 404


class TestBpmnEndpointEdgeCases:
    async def test_get_bpmn_on_pending_process_returns_400(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects", json={"name": "P"}, headers=auth["headers"]
        )
        mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/f.mp3")
        mocker.patch("app.api.v1.processes.process_audio_pipeline")
        upload = await client.post(
            f"/api/v1/projects/{proj.json()['id']}/processes",
            data={"name": "Pendente"},
            files={"audio": ("audio.mp3", b"f", "audio/mpeg")},
            headers=auth["headers"],
        )
        process_id = upload.json()["id"]

        resp = await client.get(f"/api/v1/processes/{process_id}/bpmn", headers=auth["headers"])
        assert resp.status_code == 400

    async def test_export_on_pending_process_returns_400(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects", json={"name": "P"}, headers=auth["headers"]
        )
        mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/f.mp3")
        mocker.patch("app.api.v1.processes.process_audio_pipeline")
        upload = await client.post(
            f"/api/v1/projects/{proj.json()['id']}/processes",
            data={"name": "Pendente"},
            files={"audio": ("audio.mp3", b"f", "audio/mpeg")},
            headers=auth["headers"],
        )
        process_id = upload.json()["id"]

        resp = await client.get(f"/api/v1/processes/{process_id}/export", headers=auth["headers"])
        assert resp.status_code == 400


class TestAuthEdgeCases:
    async def test_login_wrong_password_returns_401(self, client):
        auth = await register_user(client)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": auth["email"], "password": "senha-errada"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email_returns_401(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ninguem@test.com", "password": "qualquer"},
        )
        assert resp.status_code == 401

    async def test_access_protected_without_token_returns_401(self, client):
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 401

    async def test_access_protected_with_invalid_token_returns_401(self, client):
        resp = await client.get(
            "/api/v1/projects",
            headers={"Authorization": "Bearer token-invalido"},
        )
        assert resp.status_code == 401

    async def test_register_duplicate_email_returns_409(self, client):
        import uuid
        email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
        body = {
            "name": "User",
            "email": email,
            "password": "senha123",
            "company_name": f"Empresa {uuid.uuid4().hex[:6]}",
        }
        r1 = await client.post("/api/v1/auth/register", json=body)
        assert r1.status_code == 201

        body2 = {**body, "company_name": f"Outra {uuid.uuid4().hex[:6]}"}
        r2 = await client.post("/api/v1/auth/register", json=body2)
        assert r2.status_code == 409
