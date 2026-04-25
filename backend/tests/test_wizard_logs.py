import asyncio
import sys

from app.services import wizard_service


class _FakeSocket:
    def __init__(self):
        self.calls = 0

    async def recv(self):
        self.calls += 1
        if self.calls == 1:
            raise asyncio.TimeoutError()
        if self.calls == 2:
            return "stage-1-complete"
        raise RuntimeError("socket closed")


class _FakeConnection:
    def __init__(self, socket):
        self.socket = socket

    async def __aenter__(self):
        return self.socket

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeWebsocketsModule:
    def __init__(self, socket):
        self.socket = socket

    def connect(self, *_args, **_kwargs):
        return _FakeConnection(self.socket)


def test_collect_ws_log_tail_continues_after_timeout(monkeypatch):
    fake_socket = _FakeSocket()
    wizard_service._ws_log_cache.clear()
    monkeypatch.setitem(sys.modules, "websockets", _FakeWebsocketsModule(fake_socket))

    tail = asyncio.run(wizard_service._collect_ws_log_tail("127.0.0.1", "probe-key"))

    assert "stage-1-complete" in tail
    assert fake_socket.calls >= 2
