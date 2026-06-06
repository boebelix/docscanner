import os
from dataclasses import dataclass, field
from pathlib import Path

from . import PROJECT_ROOT


@dataclass
class ScanConfig:
    """Scanner configuration for device, paths and scan behaviour. Overridable via .env file."""

    device_id: str = field(default_factory=lambda: os.getenv("SCAN_DEVICE", "fujitsu:fi-6130Zdj:404446"))
    temp_dir: Path = field(default_factory=lambda: Path(os.getenv("SCAN_TEMP_DIR", str(PROJECT_ROOT / "tmp" / "scan_session"))))
    queue_dir: Path = field(default_factory=lambda: Path(os.getenv("SCAN_QUEUE_DIR", str(PROJECT_ROOT / "queue"))))
    remote_share: Path = field(default_factory=lambda: Path(os.getenv("SCAN_REMOTE_SHARE", "/mnt/scans")))
    log_file: Path = field(default_factory=lambda: Path(os.getenv("SCAN_LOG_FILE", str(PROJECT_ROOT / "scanner.log"))))
    min_storage_mb: int = 500
    button_option: str = field(default_factory=lambda: os.getenv("SCAN_BUTTON", "scan"))
    uploader_type: str = field(default_factory=lambda: os.getenv("SCAN_UPLOADER", "nfs"))
    rsync_target: str = field(default_factory=lambda: os.getenv("SCAN_RSYNC_TARGET", ""))
    consume_dir: Path = field(default_factory=lambda: Path(os.getenv("SCAN_CONSUME_DIR", "/mnt/paperless/consume")))
    sync_interval_s: int = field(default_factory=lambda: int(os.getenv("SCAN_SYNC_INTERVAL", "30")))
    poll_interval_s: float = 1.0
    upload_check_interval_s: int = 300
