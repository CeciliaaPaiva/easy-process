import uuid


async def _register(client, suffix: str = "") -> dict:
    uid = suffix or uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "name": f"User {uid}",
            "email": f"iso_{uid}@test.com",
            "password": "senha123",
            "company_name": f"Empresa ISO {uid}",
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestTenantIsolation:
    async def test_user_a_cannot_use_user_b_token_as_their_own(self, client):
        data_a = await _register(client, "a1")
        data_b = await _register(client, "b1")

        # /me com token de A retorna dados de A
        me_a = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {data_a['access_token']}"},
        )
        assert me_a.json()["email"] == data_a["user"]["email"]

        # /me com token de B retorna dados de B (não de A)
        me_b = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {data_b['access_token']}"},
        )
        assert me_b.json()["email"] == data_b["user"]["email"]
        assert me_b.json()["tenant_id"] != me_a.json()["tenant_id"]

    async def test_tenant_ids_are_different_between_companies(self, client):
        data_x = await _register(client, "x1")
        data_y = await _register(client, "y1")
        assert data_x["user"]["tenant_id"] != data_y["user"]["tenant_id"]

    async def test_refresh_token_preserves_tenant_id(self, client):
        data = await _register(client, "z1")
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": data["refresh_token"]},
        )
        new_token = refresh_resp.json()["access_token"]
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert me.json()["tenant_id"] == data["user"]["tenant_id"]
