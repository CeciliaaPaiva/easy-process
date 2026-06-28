class TestHealth:
    async def test_health_check_returns_200(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_health_check_returns_ok_status(self, client):
        response = await client.get("/api/v1/health")
        assert response.json() == {"status": "ok"}
