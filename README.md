# docscanner

Daemon that listens for a button press on a Fujitsu fi-series scanner and automatically scans, optimizes, and uploads documents as a PDF.

![Fujitsu fi-6130Z](doc/images/Gemini_Generated_Image_5hb2r85hb2r85hb2.png)

---

## Table of contents

- [Scanner](#scanner)
- [Workflow](#workflow)
- [Design decisions](#design-decisions)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Upload targets](#upload-targets)
- [Usage](#usage)
- [Run as a systemd service](#run-as-a-systemd-service)
- [Project structure](#project-structure)

---

## Scanner

```
        ___________________________
       |  _______________________  |
       | |                       | |
       | |   FUJITSU  fi-6130Z   | |
       | |_______________________| |
       |  _________________________|
       | |  ADF                    |
       | |  +---------+            |
       | |  | [pages] |            |
       | |  +---------+            |
       |_|_________________________|
       |   [ ] [ SCAN ] [ ] [ ]    |
       |___________________________|
              |           |
           USB / Network
```

---

## Workflow

```
  ┌─────────────┐
  │  SCAN button│  press
  │  on scanner │────────────────────────────────────┐
  └─────────────┘                                    │
                                                     ▼
                                          ┌─────────────────────┐
                                          │   ButtonMonitor      │
                                          │   polls every 1s    │
                                          └────────┬────────────┘
                                                   │ on_press()
                                                   ▼
                                          ┌─────────────────────┐
                                          │    Orchestrator      │
                                          └────────┬────────────┘
                                                   │
                          ┌────────────────────────┼────────────────────────┐
                          ▼                        ▼                        ▼
               ┌──────────────────┐    ┌───────────────────┐    ┌──────────────────┐
               │  scanimage       │    │  ImageOptimizer    │    │  img2pdf         │
               │  ADF Duplex      │───▶│  deskew            │───▶│  merge pages     │
               │  600 dpi / JPEG  │    │  level / threshold │    │  → Scan_*.pdf    │
               └──────────────────┘    └───────────────────┘    └────────┬─────────┘
                                                                          │
                                                              ┌───────────▼──────────┐
                                                              │     Uploader          │
                                                              │  NFS / SMB / Rsync    │
                                                              └──────────────────────┘
```

---

## Design decisions

### Why not scanbd?

[scanbd](https://scanbd.sourceforge.net/) is a dedicated daemon for polling scanner buttons and triggering actions. It works, but was deliberately not used here:

- Requires system-level configuration (`/etc/scanbd/scanbd.conf`, `scanbm` wrapper, udev rules)
- SANE must be proxied through `saned` so scanbd can hold the device — this adds another moving part
- Difficult to reproduce on a fresh system; debugging involves multiple interacting daemons
- Hard to integrate cleanly with a Python-only project

Instead, button polling is done directly in Python via `python-sane`, keeping the entire stack in one place and reproducible with a single `uv sync`.

---

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- `scanimage` (SANE utils)
- `rsync`
- Fujitsu fi-series scanner accessible via SANE

Python dependencies (installed automatically via `uv sync`):

- `img2pdf` — PDF creation
- `python-dotenv` — `.env` support
- `wand` — image optimization (requires ImageMagick)
- `watchdog` — filesystem event monitoring
- `python-sane` — SANE button polling

Install system dependencies on Debian/Raspberry Pi OS:

```bash
sudo apt install sane-utils img2pdf rsync libmagickwand-dev
```

---

## Installation

```bash
git clone https://github.com/boebelix/docscanner.git
cd docscanner
uv sync
```

---

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable           | Default                        | Description                        |
|--------------------|--------------------------------|------------------------------------|
| `SCAN_DEVICE`      | `fujitsu:fi-6130Zdj:404446`    | SANE device ID                     |
| `SCAN_QUEUE_DIR`   | `<project>/queue`              | Output directory for PDFs          |
| `SCAN_REMOTE_SHARE`| `/mnt/scans`                   | Mount point for network share      |
| `SCAN_LOG_FILE`    | `<project>/scanner.log`        | Log file path                      |

To find your scanner's SANE device ID:

```bash
$ scanimage -L
device `fujitsu:fi-6130Zdj:404446' is a FUJITSU fi-6130Zdj scanner
```

To find the correct button option name for your scanner:

```bash
$ scanimage --device "<device-id>" --all-options 2>&1 | grep -i button

Example:
$ scanimage --device "fujitsu:fi-6130Zdj:404446" --all-options 2>&1 | grep -i button
        Email button
        Scan button
```

The SANE option name is the lowercase version without spaces — `scan` or `email`. Set it in `config.py` or `.env`:

```bash
# .env
SCAN_BUTTON=scan
```

### USB permissions for local scanners

Some scanners are only visible to root unless your user has permission to access the USB device. Debian/Ubuntu systems normally create a `scanner` group for this purpose.

If `scanimage -L` only lists the scanner as root, add your user to the group and then log out/in:

```bash
sudo adduser $USER scanner
```

After that, check again with:

```bash
scanimage -L
```

If the Fujitsu scanner appears, update `.env` with the reported device ID and rerun the app.

---

## Upload targets

The uploader is configured entirely via `.env` — no code changes required.

| Variable            | Default | Description                                      |
|---------------------|---------|--------------------------------------------------|
| `SCAN_UPLOADER`     | `nfs`   | Uploader type: `nfs`, `smb`, `rsync`, `none`     |
| `SCAN_REMOTE_SHARE` | `/mnt/scans` | Mount point for NFS or SMB              |
| `SCAN_RSYNC_TARGET` | —       | Rsync target URI, e.g. `user@host:/path`         |

### Single uploader

```bash
# NFS — share must be mounted at SCAN_REMOTE_SHARE
# /etc/fstab: 192.168.1.10:/scans /mnt/nas/scans nfs defaults 0 0
SCAN_UPLOADER=nfs
SCAN_REMOTE_SHARE=/mnt/nas/scans

# SMB/CIFS — share must be mounted at SCAN_REMOTE_SHARE
# /etc/fstab: //192.168.1.10/scans /mnt/nas/scans cifs credentials=/etc/samba/creds 0 0
SCAN_UPLOADER=smb
SCAN_REMOTE_SHARE=/mnt/nas/scans

# Rsync over SSH
SCAN_UPLOADER=rsync
SCAN_RSYNC_TARGET=user@nas:/scans

# No upload
SCAN_UPLOADER=none
```

### Multiple uploaders

`SCAN_UPLOADER` accepts a comma-separated list. All configured uploaders run in sequence — if one fails, the others still run.

```bash
# NFS + Rsync as backup
SCAN_UPLOADER=nfs,rsync
SCAN_REMOTE_SHARE=/mnt/nas/scans
SCAN_RSYNC_TARGET=user@backup:/scans

# All three
SCAN_UPLOADER=nfs,smb,rsync
```

NFS and SMB uploaders skip silently if the mount point is not active.

### Rsync — SSH key setup

Rsync over SSH requires passwordless authentication so the daemon can upload without user interaction. Set up a key pair once:

```bash
# Generate key (no passphrase)
ssh-keygen -t ed25519 -f ~/.ssh/docscanner_rsa -N ""

# Copy public key to target host
ssh-copy-id -i ~/.ssh/docscanner_rsa.pub user@nas
```

Then tell SSH to use that key for the target host in `~/.ssh/config`:

```
Host nas
    HostName 192.168.1.10
    User user
    IdentityFile ~/.ssh/docscanner_rsa
    IdentitiesOnly yes
```

After that `SCAN_RSYNC_TARGET=user@nas:/scans` works without any password prompt.

---

## Usage

Start the daemon:

```bash
uv run docscanner
```

Stop with `Ctrl+C` or `kill <pid>` (SIGTERM).

Place documents in the ADF and press the **Scan** button on the scanner. The daemon will:

1. Detect the button press via SANE polling
2. Scan all pages from the ADF at 600 dpi
3. Optimize each page (deskew, contrast, white threshold)
4. Merge all pages into a timestamped PDF
5. Upload the PDF to the configured target

---

## Run as a systemd service

Create `/etc/systemd/system/docscanner.service`:
Change the default user <user>
```ini
[Unit]
Description=Document Scanner Daemon
After=network.target

[Service]
ExecStart=/home/<user>/dev/docscanner/.venv/bin/docscanner
WorkingDirectory=/home/<user>/dev/docscanner
Restart=on-failure
User=<user>

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now docscanner
sudo systemctl status docscanner
```

---

## Project structure

```
src/de/boebelix/
├── __init__.py      # PROJECT_ROOT
├── config.py        # ScanConfig dataclass
├── button.py        # ButtonMonitor – SANE button polling daemon
├── scanner.py       # Orchestrator + ScanHandler
├── image.py         # process_image – deskew / level / threshold
├── uploader.py      # Uploader base class + NFS / SMB / Rsync implementations
└── main.py          # Entry point – wires everything together
```
