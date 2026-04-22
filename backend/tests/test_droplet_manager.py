"""Backend tests for Droplet Manager API (DigitalOcean proxy + Windows install generator)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fall back to reading frontend/.env
    from pathlib import Path
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Basic service status ----------
class TestRoot:
    def test_root_status(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "service" in data


# ---------- Windows versions listing ----------
class TestWindowsVersions:
    def test_windows_versions_list(self, client):
        r = client.get(f"{API}/do/windows-versions")
        assert r.status_code == 200
        data = r.json()
        versions = data.get("versions")
        assert isinstance(versions, list)
        assert len(versions) == 8
        keys = [v["key"] for v in versions]
        for expected in ["win10pro", "win11pro", "win2012", "win2016",
                         "win2019", "win2022", "win2025", "win10ltsc"]:
            assert expected in keys
        for v in versions:
            assert "key" in v and "label" in v and "mode" in v


# ---------- Windows script generator ----------
class TestWindowsScript:
    def test_valid_win11pro(self, client):
        body = {"version": "win11pro", "password": "Test1234!", "rdp_port": 33890}
        r = client.post(f"{API}/do/windows-script", json=body)
        assert r.status_code == 200
        data = r.json()
        cmd = data["command"]
        assert "reinstall.sh windows" in cmd
        assert "--image-name" in cmd
        assert "--password" in cmd
        assert "--rdp-port 33890" in cmd
        assert "--allow-ping" in cmd
        assert "reboot" in cmd
        assert data["version"] == "win11pro"
        assert data["rdp_port"] == 33890

    def test_invalid_version(self, client):
        r = client.post(f"{API}/do/windows-script",
                        json={"version": "winXP", "password": "Test1234!", "rdp_port": 3389})
        assert r.status_code == 400

    def test_short_password(self, client):
        r = client.post(f"{API}/do/windows-script",
                        json={"version": "win11pro", "password": "abc", "rdp_port": 3389})
        assert r.status_code == 400

    def test_rdp_port_too_high(self, client):
        r = client.post(f"{API}/do/windows-script",
                        json={"version": "win11pro", "password": "Test1234!", "rdp_port": 70000})
        assert r.status_code == 400

    def test_rdp_port_zero(self, client):
        r = client.post(f"{API}/do/windows-script",
                        json={"version": "win11pro", "password": "Test1234!", "rdp_port": 0})
        assert r.status_code == 400

    def test_win10ltsc_dd_mode(self, client):
        r = client.post(f"{API}/do/windows-script",
                        json={"version": "win10ltsc", "password": "Test1234!", "rdp_port": 3389})
        assert r.status_code == 200
        cmd = r.json()["command"]
        assert "reinstall.sh dd" in cmd
        assert "--img" in cmd


# ---------- Token requirement on all /do/* proxy endpoints ----------
NO_TOKEN_GET_ENDPOINTS = [
    "/do/account",
    "/do/droplets",
    "/do/droplets/123",
    "/do/regions",
    "/do/sizes",
    "/do/images",
    "/do/ssh_keys",
    "/do/droplets/123/snapshots",
]


class TestTokenRequired:
    @pytest.mark.parametrize("path", NO_TOKEN_GET_ENDPOINTS)
    def test_get_missing_token(self, client, path):
        # Use a fresh session without default headers to guarantee no token
        r = requests.get(f"{API}{path}")
        assert r.status_code == 401, f"{path} -> {r.status_code}"
        detail = r.json().get("detail", "")
        assert "Missing DigitalOcean API token" in detail

    def test_post_create_droplet_missing_token(self):
        r = requests.post(f"{API}/do/droplets",
                          json={"name": "x", "region": "nyc3", "size": "s-1vcpu-1gb",
                                "image": "ubuntu-22-04-x64"})
        assert r.status_code == 401
        assert "Missing DigitalOcean API token" in r.json().get("detail", "")

    def test_post_droplet_action_missing_token(self):
        r = requests.post(f"{API}/do/droplets/123/actions",
                          json={"action_type": "power_on"})
        assert r.status_code == 401
        assert "Missing DigitalOcean API token" in r.json().get("detail", "")

    def test_delete_droplet_missing_token(self):
        r = requests.delete(f"{API}/do/droplets/123")
        assert r.status_code == 401
        assert "Missing DigitalOcean API token" in r.json().get("detail", "")


# ---------- Action allow-list & rebuild validation (fire before DO call) ----------
class TestActionValidation:
    def test_invalid_action_type(self):
        r = requests.post(f"{API}/do/droplets/123/actions",
                          headers={"X-DO-Token": "dop_v1_dummy_token", "Content-Type": "application/json"},
                          json={"action_type": "invalid_action"})
        assert r.status_code == 400
        assert "Unsupported action" in r.json().get("detail", "")

    def test_rebuild_missing_image(self):
        r = requests.post(f"{API}/do/droplets/123/actions",
                          headers={"X-DO-Token": "dop_v1_dummy_token", "Content-Type": "application/json"},
                          json={"action_type": "rebuild"})
        assert r.status_code == 400
        assert "image is required for rebuild" in r.json().get("detail", "")


# ---------- DigitalOcean forwarded auth error ----------
class TestDOForwardedAuth:
    def test_account_with_invalid_token(self):
        r = requests.get(f"{API}/do/account",
                         headers={"X-DO-Token": "dop_v1_invalid_token_for_test"})
        # DO will return 401 for an invalid token, our proxy forwards it
        assert 400 <= r.status_code < 500
        # most likely 401
        assert r.status_code in (401, 403)
