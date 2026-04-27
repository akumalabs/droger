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


def test_run_frontend_build_skips_when_frontend_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(update_service, "FRONTEND_ROOT", tmp_path / "frontend")

    output = update_service._run_frontend_build()

    assert output == ""


def test_run_frontend_build_runs_install_and_build(monkeypatch, tmp_path):
    frontend_root = tmp_path / "frontend"
    frontend_root.mkdir()
    (frontend_root / "package-lock.json").write_text("{}", encoding="utf-8")

    calls = []

    class _Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_subprocess_run(command, cwd, capture_output, text, check):
        calls.append((tuple(command), cwd, capture_output, text, check))
        if command[-2:] == ["run", "build"]:
            return _Result(stdout="build ok")
        return _Result(stdout="install ok")

    monkeypatch.setattr(update_service, "FRONTEND_ROOT", frontend_root)
    monkeypatch.setattr(update_service.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    monkeypatch.setattr(update_service.subprocess, "run", fake_subprocess_run)

    output = update_service._run_frontend_build()

    assert calls[0][0] == ("/usr/bin/npm", "ci")
    assert calls[1][0] == ("/usr/bin/npm", "run", "build")
    assert output == "install ok\nbuild ok"


def test_apply_update_includes_frontend_build_output(monkeypatch):
    before_status = {
        "branch": "main",
        "update_available": True,
        "tracked_remote_ref": "origin/main",
    }
    after_status = {
        "branch": "main",
        "update_available": False,
        "tracked_remote_ref": "origin/main",
    }

    monkeypatch.setattr(update_service, "_git_available", lambda: None)
    monkeypatch.setattr(update_service, "get_update_status", lambda: before_status)
    monkeypatch.setattr(update_service, "_run_pull", lambda _branch, _remote: "pull ok")
    monkeypatch.setattr(update_service, "_run_frontend_build", lambda: "build ok")

    state = {"count": 0}

    def fake_status():
        state["count"] += 1
        return before_status if state["count"] == 1 else after_status

    monkeypatch.setattr(update_service, "get_update_status", fake_status)

    result = update_service.apply_update()

    assert result["updated"] is True
    assert result["status"] == after_status
    assert result["output"] == "pull ok\nbuild ok"


def test_split_remote_ref_validates_input():
    assert update_service._split_remote_ref("origin/main") == ("origin", "main")

    try:
        update_service._split_remote_ref("main")
        raise AssertionError("Expected HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 500
