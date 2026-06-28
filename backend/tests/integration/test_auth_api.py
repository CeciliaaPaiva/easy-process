import uuid


def _payload(suffix: str = "") -> dict:
    uid = suffix or uuid.uuid4().hex[:8]
    return {
        "name": f"Test User {uid}",
        "email": f"user_{uid}@test.com",
        "password": "senha123",
        "company_name": f"Empresa {uid}",
    }


class TestRegister:
    async def test_creates_tenant_and_returns_tokens(self, client):
        resp = await client.post("/api/v1/auth/register", json=_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["role"] == "admin"

    async def test_duplicate_email_returns_409(self, client):
        payload = _payload()
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_missing_required_field_returns_422(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "x@x.com", "password": "123456"},
        )
        assert resp.status_code == 422

    async def test_short_password_returns_422(self, client):
        p = _payload()
        p["password"] = "12"
        resp = await client.post("/api/v1/auth/register", json=p)
        assert resp.status_code == 422

    async def test_invalid_email_returns_422(self, client):
        p = _payload()
        p["email"] = "nao-e-email"
        resp = await client.post("/api/v1/auth/register", json=p)
        assert resp.status_code == 422


class TestLogin:
    async def test_valid_credentials_return_tokens(self, client):
        p = _payload()
        await client.post("/api/v1/auth/register", json=p)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": p["email"], "password": p["password"]},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_wrong_password_returns_401(self, client):
        p = _payload()
        await client.post("/api/v1/auth/register", json=p)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": p["email"], "password": "senhaerrada"},
        )
        assert resp.status_code == 401

    async def test_nonexistent_email_returns_401(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "naoexiste@test.com", "password": "qualquer"},
        )
        assert resp.status_code == 401
        # Mensagem genérica — não revela se o e-mail existe
        assert "Credenciais" in resp.json()["detail"]


class TestRefreshToken:
    async def test_valid_refresh_returns_new_access_token(self, client):
        p = _payload()
        reg = await client.post("/api/v1/auth/register", json=p)
        refresh = reg.json()["refresh_token"]
        resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_access_token_as_refresh_returns_401(self, client):
        p = _payload()
        reg = await client.post("/api/v1/auth/register", json=p)
        access = reg.json()["access_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client):
        resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "token.invalido.aqui"}
        )
        assert resp.status_code == 401


class TestGetMe:
    async def test_authenticated_returns_user(self, client):
        p = _payload()
        reg = await client.post("/api/v1/auth/register", json=p)
        token = reg.json()["access_token"]
        resp = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == p["email"]

    async def test_without_token_returns_403(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    async def test_with_invalid_token_returns_401_or_403(self, client):
        resp = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer token.invalido"}
        )
        assert resp.status_code in (401, 403)
