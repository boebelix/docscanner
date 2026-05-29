from dataclasses import dataclass
from pathlib import Path

from . import PROJECT_ROOT


@dataclass
class ScanConfig:
    """Scanner configuration for device, paths and scan behaviour. Overridable via .env file."""

    device_id: str = "fujitsu:fi-6130Zdj:404446"
    temp_dir: Path = PROJECT_ROOT / "tmp" / "scan_session"
    queue_dir: Path = PROJECT_ROOT / "queue"
    remote_share: Path = Path("/mnt/scans")
    log_file: Path = PROJECT_ROOT / "scanner.log"
    min_storage_mb: int = 500
    button_option: str = "scan"
    poll_interval_s: float = 1.0
    upload_check_interval_s: int = 300
