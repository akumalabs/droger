from fastapi import HTTPException

from app.services import update_service


def test_resolve_remote_ref_prefers_upstream(monkeypatch):
    monkeypatch.setattr(update_service, "_upstream_remote_ref", lambda: "origin/main")
    monkeypatch.setattr(update_service, "_origin_default_remote_ref", lambda: "origin/master")

    assert update_service._resolve_remote_ref("main") == "origin/main"


def test_resolve_remote_ref_falls_back_to_origin_branch(monkeypatch):
    monkeypatch.setattr(update_service, "_upstream_remote_ref", lambda: None)
    monkeypatch.setattr(update_service, "_origin_default_remote_ref", lambda: None)

    assert update_service._resolve_remote_ref("main") == "origin/main"


def test_resolve_remote_ref_uses_origin_default_on_detached_head(monkeypatch):
    monkeypatch.setattr(update_service, "_upstream_remote_ref", lambda: None)
    monkeypatch.setattr(update_service, "_origin_default_remote_ref", lambda: "origin/main")

    assert update_service._resolve_remote_ref("HEAD") == "origin/main"


def test_get_update_status_detached_head_uses_origin_default(monkeypatch):
    calls = []

    def fake_git_command(*args):
        return list(args)

    def fake_run(command):
        calls.append(tuple(command))
        if command == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "HEAD"
        if command == ["rev-parse", "HEAD"]:
            return "loc123"
        if command == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            raise HTTPException(status_code=500, detail="no upstream")
        if command == ["symbolic-ref", "refs/remotes/origin/HEAD"]:
            return "refs/remotes/origin/main"
        if command == ["fetch", "--quiet", "origin"]:
            return ""
        if command == ["rev-parse", "origin/main"]:
            return "rem456"
        if command == ["rev-list", "--left-right", "--count", "HEAD...origin/main"]:
            return "0 1"
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(update_service, "_git_available", lambda: None)
    monkeypatch.setattr(update_service, "_git_command", fake_git_command)
    monkeypatch.setattr(update_service, "_run", fake_run)

    status = update_service.get_update_status()

    assert status["branch"] == "HEAD"
    assert status["local_commit"] == "loc123"
    assert status["remote_commit"] == "rem456"
    assert status["behind"] == 1
    assert status["update_available"] is True
    assert ("fetch", "--quiet", "origin") in calls
