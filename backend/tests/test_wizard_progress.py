import asyncio

from app.services import wizard_service


class _FakeDB:
    def __init__(self, latest_job=None):
        self.latest_job = latest_job

    async def scalar(self, _stmt):
        return self.latest_job


class _FakeHttpResponse:
    def __init__(self, status_code=404, text=""):
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _url):
        return _FakeHttpResponse(status_code=404, text="")


def test_install_progress_defaults_rdp_port_when_no_job(monkeypatch):
    async def fake_resolve_token(_db, _user_id, _token_id):
        return "do-token"

    async def fake_do_request(_method, _path, _token):
        return {
            "droplet": {
                "id": 101,
                "status": "new",
                "networks": {"v4": []},
            }
        }

    monkeypatch.setattr(wizard_service, "resolve_token", fake_resolve_token)
    monkeypatch.setattr(wizard_service.do_service, "do_request", fake_do_request)

    result = asyncio.run(wizard_service.get_install_progress(_FakeDB(), "user-1", "tok-1", 101))

    assert result["rdp_port"] == 3389
    assert result["rdp_open"] is False
    assert result["ping_ok"] is False


def test_install_progress_uses_default_rdp_port_when_saved_port_invalid(monkeypatch):
    class _Job:
        windows_version = "win2022"
        rdp_port = 70000
        command = None

    async def fake_resolve_token(_db, _user_id, _token_id):
        return "do-token"

    async def fake_do_request(_method, _path, _token):
        return {
            "droplet": {
                "id": 202,
                "status": "active",
                "networks": {
                    "v4": [
                        {"type": "public", "ip_address": "203.0.113.10"},
                    ]
                },
            }
        }

    async def fake_ping(_host):
        return False

    async def fake_tcp(_host, _port):
        return False

    monkeypatch.setattr(wizard_service, "resolve_token", fake_resolve_token)
    monkeypatch.setattr(wizard_service.do_service, "do_request", fake_do_request)
    monkeypatch.setattr(wizard_service, "_ping_host", fake_ping)
    monkeypatch.setattr(wizard_service, "_tcp_open", fake_tcp)
    monkeypatch.setattr(wizard_service.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(wizard_service.get_install_progress(_FakeDB(_Job()), "user-1", "tok-1", 202))

    assert result["rdp_port"] == 3389
    assert result["rdp_open"] is False
