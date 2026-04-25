import base64
from typing import Any
from fastapi import HTTPException

WINDOWS_VERSIONS: dict[str, dict[str, Any]] = {
    "win2012": {
        "label": "Windows Server 2012 R2 DC",
        "image_name": "Windows Server 2012 R2 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195443",
    },
    "win2016": {
        "label": "Windows Server 2016 DC",
        "image_name": "Windows Server 2016 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195174",
    },
    "win2019": {
        "label": "Windows Server 2019 DC",
        "image_name": "Windows Server 2019 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195167",
    },
    "win2022": {
        "label": "Windows Server 2022 DC",
        "image_name": "Windows Server 2022 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195280",
    },
    "win2025": {
        "label": "Windows Server 2025 DC",
        "image_name": "Windows Server 2025 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2293312",
    },
    "win10ltsc": {
        "label": "Windows 10 LTSC (DD template)",
        "image_name": "Windows 10 LTSC",
        "iso": "https://cp.akumalabs.com/storage/images/win-10-ltsc.xz",
        "mode": "dd",
    },
}


def build_windows_command(version: str, password: str, rdp_port: int) -> str:
    meta = WINDOWS_VERSIONS.get(version)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unknown Windows version: {version}")
    safe_pw = password.replace("'", "'\\''")
    safe_img = str(meta["image_name"]).replace("'", "'\\''")
    iso = str(meta["iso"])
    base = (
        "curl -O https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh || "
        "wget -O reinstall.sh https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh && "
    )
    if meta.get("mode") == "dd":
        return base + f"bash reinstall.sh dd --img '{iso}' --password '{safe_pw}' --rdp-port {int(rdp_port)} --allow-ping && reboot"
    return base + (
        f"bash reinstall.sh windows --image-name='{safe_img}' --iso='{iso}' "
        f"--password '{safe_pw}' --rdp-port {int(rdp_port)} --allow-ping && reboot"
    )


def build_windows_user_data(version: str, password: str, rdp_port: int) -> str:
    command = build_windows_command(version, password, rdp_port)
    encoded = base64.b64encode(command.encode("utf-8")).decode("utf-8")
    return f"""#!/bin/bash
set -e
LOG_FILE=/var/log/droger-autowin.log
PROGRESS_DIR=/var/www/droger-progress
exec > >(tee -a "$LOG_FILE") 2>&1

mkdir -p "$PROGRESS_DIR"
cat <<'EOF' > "$PROGRESS_DIR/index.html"
<html><body style="background:#050505;color:#e5e5e5;font-family:monospace;"><h3>Droger Windows auto-install</h3><p>Initializing...</p></body></html>
EOF

if command -v python3 >/dev/null 2>&1; then
  nohup python3 -m http.server 80 --directory "$PROGRESS_DIR" >/var/log/droger-progress-http.log 2>&1 &
fi

(
  while true; do
    if [ -f "$LOG_FILE" ]; then
      {{
        echo '<html><body style="background:#050505;color:#e5e5e5;font-family:monospace;"><h3>Droger Windows auto-install</h3><pre>'
        sed 's/&/\\&amp;/g; s/</\\&lt;/g' "$LOG_FILE"
        echo '</pre></body></html>'
      }} > "$PROGRESS_DIR/index.html"
    fi
    sleep 5
  done
) >/dev/null 2>&1 &

ATTEMPTS=0
until [ $ATTEMPTS -ge 24 ]
do
  if curl -fsS https://api.ipify.org >/dev/null 2>&1; then
    break
  fi
  ATTEMPTS=$((ATTEMPTS + 1))
  sleep 10
done

cat <<'EOF' >/root/.droger_autowin_cmd.b64
{encoded}
EOF
base64 -d /root/.droger_autowin_cmd.b64 >/root/.droger_autowin_cmd.sh
chmod 700 /root/.droger_autowin_cmd.sh
bash /root/.droger_autowin_cmd.sh
"""
