from typing import Any
from fastapi import HTTPException

WINDOWS_VERSIONS: dict[str, dict[str, Any]] = {
    "win10pro": {
        "label": "Windows 10 Pro",
        "image_name": "Windows 10 Pro",
        "iso": "https://fafda.to/d/fuxscqu93mnn?v=Vp6_aNhhYS79d6Q2fRUQOaZ2wJct9EsnrCVq8-GHjGrgS_TRciyd4VFeKYHBGOZp6xO42x8i24hJMAaLHJrTUeGrryy8jOn20HSvsc2eKb_jNhnIumZidL5VuQVky5GEXM5VWvU7X_5Wn2_Iu4Nk6oigtevIUwBAhMEvfq7EchuUy2b_mO9Ry0cK9xc7dlys-PIUHmjsQjwG5MGoVxO8Ip12ASnT02V0oCb0hotUsQR4wtk4wGe3h5mwsvV2r5J4Jg82U_kGnFqmQzxJGog35Ty_opN9mFUIYNzRkVw78dPM2OPoamqlRp1oqgFMut4e8VC8sYz--cOTr0RNUkY",
    },
    "win11pro": {
        "label": "Windows 11 Pro",
        "image_name": "Windows 11 Pro",
        "iso": "https://dl.zerofs.link/dl/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJidWNrZXQiOiJhc3NldHMtYW1zIiwia2V5Ijoib05xNVlUcml4ekJlZGtoRzJxZXl2cS80M2I3YzZkMDRmY2Q0ZDNhOGJjZjQ1NTA3MTlhOTI4ZiIsImZpbGVuYW1lIjoiZW4tdXNfd2luZG93c18xMV9jb25zdW1lcl9lZGl0aW9uc192ZXJzaW9uXzI1aDJfdXBkYXRlZF9tYXJjaF8yMDI2X3g2NF9kdmRfYTFjZjZjMzYuaXNvIiwiYnVja2V0X2NvZGUiOiJldSIsImVuZHBvaW50IjoiczMuZXUtY2VudHJhbC0wMDMuYmFja2JsYXplYjIuY29tIiwiZXhwIjoxNzc0OTgxNjYzLCJrZXlfYjY0IjoicURpemVNSENxQllDUEdPZDN3NFZXallIbGhVU3dXZ1M3YXkrb1dISWJKVT0iLCJrZXlfbWQ1IjoiNzg4STdydzl6ZTQwQnNHKzZCYzZGZz09In0.MOY-rYGRk9HxowAFD3DuDXl9XesgMai4yYOgsNv5h4Q",
    },
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
