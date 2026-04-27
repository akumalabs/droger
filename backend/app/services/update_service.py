from pathlib import Path
import shutil
import subprocess
import threading
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_ROOT = REPO_ROOT / "frontend"
_update_lock = threading.Lock()


def _git_command(*args: str) -> list[str]:
    return ["git", "-c", f"safe.directory={REPO_ROOT}", *args]


def _git_available() -> None:
    if not shutil.which("git"):
        raise HTTPException(status_code=503, detail="git is not available on this server")
    if not (REPO_ROOT / ".git").exists():
        raise HTTPException(status_code=503, detail="Server is not running from a git repository")


def _run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise HTTPException(status_code=500, detail=detail or f"Command failed: {' '.join(command)}")
    return (result.stdout or "").strip()


def _run_pull(branch: str) -> str:
    result = subprocess.run(
        _git_command("pull", "--ff-only", "origin", branch),
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise HTTPException(status_code=409, detail=detail or "Failed to apply update")
    return (result.stdout or "").strip()


def _run_frontend_build() -> str:
    if not FRONTEND_ROOT.exists():
        return ""

    npm = shutil.which("npm")
    if not npm:
        raise HTTPException(status_code=503, detail="npm is not available on this server")

    lock_file = FRONTEND_ROOT / "package-lock.json"
    install_cmd = [npm, "ci"] if lock_file.exists() else [npm, "install"]
    build_cmd = [npm, "run", "build"]

    install = subprocess.run(
        install_cmd,
        cwd=str(FRONTEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if install.returncode != 0:
        detail = (install.stderr or install.stdout or "").strip()
        raise HTTPException(status_code=409, detail=detail or "Failed to install frontend dependencies")

    build = subprocess.run(
        build_cmd,
        cwd=str(FRONTEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if build.returncode != 0:
        detail = (build.stderr or build.stdout or "").strip()
        raise HTTPException(status_code=409, detail=detail or "Failed to build frontend")

    return "\n".join(part for part in [install.stdout or "", build.stdout or ""] if part).strip()


def _upstream_remote_ref() -> str | None:
    try:
        ref = _run(_git_command("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"))
    except HTTPException:
        return None
    ref = (ref or "").strip()
    return ref or None


def _origin_default_remote_ref() -> str | None:
    try:
        ref = _run(_git_command("symbolic-ref", "refs/remotes/origin/HEAD"))
    except HTTPException:
        return None
    ref = (ref or "").strip()
    prefix = "refs/remotes/"
    if ref.startswith(prefix):
        return ref[len(prefix):]
    return None


def _resolve_remote_ref(branch: str) -> str:
    upstream_ref = _upstream_remote_ref()
    if upstream_ref:
        return upstream_ref

    if branch and branch != "HEAD":
        return f"origin/{branch}"

    origin_default = _origin_default_remote_ref()
    if origin_default:
        return origin_default

    raise HTTPException(status_code=500, detail="Unable to determine tracked remote branch")


def get_update_status() -> dict:
    _git_available()

    branch = _run(_git_command("rev-parse", "--abbrev-ref", "HEAD"))
    local_commit = _run(_git_command("rev-parse", "HEAD"))

    remote_ref = _resolve_remote_ref(branch)
    remote_name = remote_ref.split("/", 1)[0] if "/" in remote_ref else "origin"

    _run(_git_command("fetch", "--quiet", remote_name))
    remote_commit = _run(_git_command("rev-parse", remote_ref))

    ahead = 0
    behind = 0
    counts = _run(_git_command("rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"))
    try:
        ahead_str, behind_str = counts.split()
        ahead = int(ahead_str)
        behind = int(behind_str)
    except Exception:
        ahead = 0
        behind = 0

    return {
        "branch": branch,
        "local_commit": local_commit,
        "remote_commit": remote_commit or None,
        "ahead": ahead,
        "behind": behind,
        "update_available": bool(behind > 0),
        "repo_path": str(REPO_ROOT),
    }


def apply_update() -> dict:
    _git_available()

    if not _update_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Update is already in progress")

    try:
        before = get_update_status()
        if not before["update_available"]:
            return {
                "ok": True,
                "updated": False,
                "message": "Already up to date",
                "status": before,
                "output": "",
            }

        pull_output = _run_pull(before["branch"])
        build_output = _run_frontend_build()
        after = get_update_status()
        output = "\n".join(part for part in [pull_output, build_output] if part).strip()
        return {
            "ok": True,
            "updated": True,
            "message": "Update applied",
            "status": after,
            "output": output,
        }
    finally:
        _update_lock.release()
