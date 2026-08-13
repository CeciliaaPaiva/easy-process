from starlette.requests import Request

from app.core.rate_limit import client_ip


def _request(
    headers: dict[str, str] | None = None, client_host: str = "9.9.9.9"
) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw_headers, "client": (client_host, 1)})


class TestClientIp:
    def test_prefers_cf_connecting_ip(self):
        req = _request(
            {"cf-connecting-ip": "1.1.1.1", "x-forwarded-for": "2.2.2.2"},
            client_host="3.3.3.3",
        )
        assert client_ip(req) == "1.1.1.1"

    def test_falls_back_to_x_forwarded_for(self):
        req = _request({"x-forwarded-for": "2.2.2.2, 5.5.5.5"}, client_host="3.3.3.3")
        assert client_ip(req) == "2.2.2.2"

    def test_falls_back_to_request_client_host(self):
        req = _request({}, client_host="3.3.3.3")
        assert client_ip(req) == "3.3.3.3"

    def test_returns_unknown_without_client_or_headers(self):
        req = Request({"type": "http", "headers": [], "client": None})
        assert client_ip(req) == "unknown"
