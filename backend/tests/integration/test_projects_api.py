from tests.integration.conftest import register_user


class TestCreateProject:
    async def test_creates_project_returns_201(self, client):
        auth = await register_user(client)
        resp = await client.post(
            "/api/v1/projects",
            json={"name": "Meu Projeto", "description": "Desc"},
            headers=auth["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Meu Projeto"
        assert data["description"] == "Desc"
        assert data["status"] == "active"
        assert data["tenant_id"] == auth["user"]["tenant_id"]

    async def test_without_auth_returns_401(self, client):
        resp = await client.post("/api/v1/projects", json={"name": "X"})
        assert resp.status_code in (401, 403)

    async def test_empty_name_returns_422(self, client):
        auth = await register_user(client)
        resp = await client.post(
            "/api/v1/projects",
            json={"name": ""},
            headers=auth["headers"],
        )
        assert resp.status_code == 422


class TestListProjects:
    async def test_list_returns_only_own_tenant_projects(self, client):
        auth_a = await register_user(client)
        auth_b = await register_user(client)

        await client.post(
            "/api/v1/projects",
            json={"name": "Projeto A"},
            headers=auth_a["headers"],
        )
        await client.post(
            "/api/v1/projects",
            json={"name": "Projeto B"},
            headers=auth_b["headers"],
        )

        resp = await client.get("/api/v1/projects", headers=auth_a["headers"])
        assert resp.status_code == 200
        data = resp.json()
        names = [p["name"] for p in data["items"]]
        assert "Projeto A" in names
        assert "Projeto B" not in names

    async def test_list_pagination(self, client):
        auth = await register_user(client)
        for i in range(5):
            await client.post(
                "/api/v1/projects",
                json={"name": f"Paginado {i}"},
                headers=auth["headers"],
            )

        resp = await client.get(
            "/api/v1/projects?page=1&per_page=2",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    async def test_search_by_name(self, client):
        auth = await register_user(client)
        await client.post(
            "/api/v1/projects",
            json={"name": "Processo de Compras"},
            headers=auth["headers"],
        )
        await client.post(
            "/api/v1/projects",
            json={"name": "Processo de Vendas"},
            headers=auth["headers"],
        )

        resp = await client.get(
            "/api/v1/projects?q=Compras",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all("Compras" in p["name"] for p in data["items"])


class TestGetProject:
    async def test_get_existing_returns_200(self, client):
        auth = await register_user(client)
        create = await client.post(
            "/api/v1/projects",
            json={"name": "Detalhes"},
            headers=auth["headers"],
        )
        project_id = create.json()["id"]

        resp = await client.get(
            f"/api/v1/projects/{project_id}", headers=auth["headers"]
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    async def test_get_other_tenant_project_returns_404(self, client):
        auth_a = await register_user(client)
        auth_b = await register_user(client)

        create = await client.post(
            "/api/v1/projects",
            json={"name": "Projeto Privado"},
            headers=auth_a["headers"],
        )
        project_id = create.json()["id"]

        resp = await client.get(
            f"/api/v1/projects/{project_id}",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404


class TestUpdateProject:
    async def test_update_name_and_description(self, client):
        auth = await register_user(client)
        create = await client.post(
            "/api/v1/projects",
            json={"name": "Original"},
            headers=auth["headers"],
        )
        project_id = create.json()["id"]

        resp = await client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Atualizado", "description": "Nova desc"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Atualizado"
        assert data["description"] == "Nova desc"


class TestArchiveProject:
    async def test_archive_returns_204_and_hides_from_list(self, client):
        auth = await register_user(client)
        create = await client.post(
            "/api/v1/projects",
            json={"name": "Para Arquivar"},
            headers=auth["headers"],
        )
        project_id = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/projects/{project_id}",
            headers=auth["headers"],
        )
        assert resp.status_code == 204

        list_resp = await client.get("/api/v1/projects", headers=auth["headers"])
        ids = [p["id"] for p in list_resp.json()["items"]]
        assert project_id not in ids
