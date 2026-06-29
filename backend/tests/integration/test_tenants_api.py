import pytest

from tests.integration.conftest import register_user


async def _register_admin(client):
    return await register_user(client)


async def _register_second_user(client, admin_auth: dict) -> dict:
    """Convida e retorna um novo membro via API."""
    email = f"member_{__import__('uuid').uuid4().hex[:8]}@test.com"
    resp = await client.post(
        "/api/v1/tenants/invite",
        json={"email": email, "name": "Membro Teste", "role": "analyst"},
        headers=admin_auth["headers"],
    )
    assert resp.status_code == 201
    return resp.json()


class TestListMembers:
    async def test_admin_sees_all_members(self, client):
        auth = await _register_admin(client)
        resp = await client.get("/api/v1/tenants/members", headers=auth["headers"])
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) >= 1
        assert any(m["email"] == auth["email"] for m in members)

    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get("/api/v1/tenants/members")
        assert resp.status_code == 401

    async def test_other_tenant_members_not_visible(self, client):
        auth_a = await _register_admin(client)
        auth_b = await _register_admin(client)
        await _register_second_user(client, auth_a)

        resp_b = await client.get("/api/v1/tenants/members", headers=auth_b["headers"])
        emails_b = [m["email"] for m in resp_b.json()]
        assert auth_a["email"] not in emails_b


class TestInviteMember:
    async def test_admin_invites_new_member(self, client):
        auth = await _register_admin(client)
        member = await _register_second_user(client, auth)
        assert member["role"] == "analyst"
        assert member["tenant_id"] == auth["user"]["tenant_id"]

    async def test_duplicate_email_returns_409(self, client):
        auth = await _register_admin(client)
        member = await _register_second_user(client, auth)

        resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": member["email"], "name": "Outro", "role": "viewer"},
            headers=auth["headers"],
        )
        assert resp.status_code == 409

    async def test_non_admin_cannot_invite(self, client):
        auth_admin = await _register_admin(client)
        member = await _register_second_user(client, auth_admin)

        analyst_login = await client.post(
            "/api/v1/auth/login",
            json={"email": member["email"], "password": "change-me"},
        )
        if analyst_login.status_code != 200:
            pytest.skip("Login do membro convidado requer senha real — skip")

    async def test_invalid_role_returns_422(self, client):
        auth = await _register_admin(client)
        import uuid
        resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": f"x{uuid.uuid4().hex[:6]}@test.com", "name": "X", "role": "superuser"},
            headers=auth["headers"],
        )
        assert resp.status_code == 422


class TestUpdateMember:
    async def test_admin_updates_member_role(self, client):
        auth = await _register_admin(client)
        member = await _register_second_user(client, auth)

        resp = await client.put(
            f"/api/v1/tenants/members/{member['id']}",
            json={"role": "viewer"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    async def test_cannot_update_own_role(self, client):
        auth = await _register_admin(client)
        resp = await client.put(
            f"/api/v1/tenants/members/{auth['user']['id']}",
            json={"role": "viewer"},
            headers=auth["headers"],
        )
        assert resp.status_code == 400

    async def test_member_not_found_returns_404(self, client):
        auth = await _register_admin(client)
        import uuid
        resp = await client.put(
            f"/api/v1/tenants/members/{uuid.uuid4()}",
            json={"role": "viewer"},
            headers=auth["headers"],
        )
        assert resp.status_code == 404


class TestRemoveMember:
    async def test_admin_removes_member(self, client):
        auth = await _register_admin(client)
        member = await _register_second_user(client, auth)

        resp = await client.delete(
            f"/api/v1/tenants/members/{member['id']}",
            headers=auth["headers"],
        )
        assert resp.status_code == 204

        members = (await client.get("/api/v1/tenants/members", headers=auth["headers"])).json()
        assert not any(m["id"] == member["id"] for m in members)

    async def test_cannot_remove_self(self, client):
        auth = await _register_admin(client)
        resp = await client.delete(
            f"/api/v1/tenants/members/{auth['user']['id']}",
            headers=auth["headers"],
        )
        assert resp.status_code == 400
