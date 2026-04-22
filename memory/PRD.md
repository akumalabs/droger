# Droplet Manager — PRD

## Problem Statement (verbatim)
Build a web app to manage Digital Ocean droplets using an API token, with the ability to install Windows OS via the akumalabs/reinstall kernel.sh script.

## User Choices (from ask_human)
- API Token handling: Entered in UI, stored per-session (sessionStorage)
- Authentication: None (single-user)
- Droplet operations: Full CRUD + power actions + console link + snapshots
- Windows install: DO Recovery Console / user-data (paste-generated command)
- Windows parameters: Version picker (Win10/11/Server 2012–2025/LTSC), custom RDP port, custom RDP password

## Architecture
- **Backend**: FastAPI thin async proxy over `https://api.digitalocean.com/v2`, `httpx` HTTP client. All endpoints under `/api/do/*`. Token read from `X-DO-Token` header per request, no server-side storage.
- **Frontend**: React (CRA) + react-router + shadcn UI + phosphor-icons + sonner toasts. Dark "Control Room" Swiss aesthetic (Chivo / IBM Plex Sans / JetBrains Mono).
- **Database**: MongoDB present but not used (no persisted state).

## What's been implemented (2026-02-22)
- Token entry landing page with session-scoped storage
- Dashboard: droplet table with status pills, region, size, IP, image, row dropdown actions
- Create Droplet dialog: region/size/image/SSH keys from DO API
- Droplet detail with tabs: Power, Install Windows, Snapshots, Console
- Power panel: on, off (hard), shutdown, reboot, power_cycle, password_reset with confirmations
- Snapshots panel: list, create, delete, restore (rebuild from snapshot)
- Windows install panel: version select, RDP password (with generator + show/hide), RDP port, command preview, copy-to-clipboard, open DO Console link
- Windows script generator backend: handles 8 versions (7 ISO + 1 DD), validates password/port, escapes shell-unsafe quotes
- 22 backend tests passing (token-requirement, allow-list, script validation, DO-forwarded auth)

## Next Action Items / Backlog
- P1: Monitoring graphs (CPU, bandwidth, disk) on droplet detail
- P1: Floating IPs management
- P1: Domains & DNS records management
- P2: Firewalls & VPC
- P2: Persistent settings (remembered preferences) if user opts in to DB
- P2: Long-lived ISO URL hosting for Win11 (current zerofs URL has `exp` timestamp)
- P2: Post-install `--rdp-port` fallback — inject PowerShell post-install if akumalabs kernel ignores flag

## Personas
- DevOps engineer renting DO droplets for Windows workloads (RDP, game/app hosting)
- Sysadmin who wants a fast console to mass-manage fleets without DO web UI
