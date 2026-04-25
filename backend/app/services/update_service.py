from pathlib import Path
import shutil
import subprocess
import threading
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[3]
_update_lock = threading.Lock()


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
        ["git", "pull", "--ff-only", "origin", branch],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise HTTPException(status_code=409, detail=detail or "Failed to apply update")
    return (result.stdout or "").strip()


def get_update_status() -> dict:
    _git_available()

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    local_commit = _run(["git", "rev-parse", "HEAD"])
    remote_line = _run(["git", "ls-remote", "--heads", "origin", branch])
    remote_commit = remote_line.split()[0] if remote_line else ""

    ahead = 0
    behind = 0
    if remote_commit:
        counts = _run(["git", "rev-list", "--left-right", "--count", f"{local_commit}...{remote_commit}"])
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

        output = _run_pull(before["branch"])
        after = get_update_status()
        return {
            "ok": True,
            "updated": True,
            "message": "Update applied",
            "status": after,
            "output": output,
        }
    finally:
        _update_lock.release()
