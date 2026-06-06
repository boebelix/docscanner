import csv
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from .config import ScanConfig
from .uploader import _is_mounted


class ConsumeSync:
    """Copies PDFs from the NFS docscanner folder to the Paperless consume dir.

    Tracking: every successfully copied file is appended to a CSV log
    (transferred.csv) so it is never copied again.
    """

    def __init__(self, config: ScanConfig) -> None:
        self.source_dir = config.remote_share
        self.consume_dir = config.consume_dir
        self.log_file = config.remote_share / "transferred.csv"
        self.interval = config.sync_interval_s

    def _load_transferred(self) -> set[str]:
        if not self.log_file.exists():
            return set()
        with self.log_file.open(newline="") as f:
            return {row["filename"] for row in csv.DictReader(f)}

    def _record_transferred(self, pdf: Path) -> None:
        write_header = not self.log_file.exists()
        with self.log_file.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "filename", "source", "destination"])
            if write_header:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "filename": pdf.name,
                "source": str(pdf),
                "destination": str(self.consume_dir / pdf.name),
            })

    def _check_mounts(self) -> bool:
        if not _is_mounted(self.source_dir):
            logging.warning("ConsumeSync: NFS source %s not mounted, skipping.", self.source_dir)
            return False
        if not self.consume_dir.exists():
            logging.warning("ConsumeSync: consume dir %s missing, skipping.", self.consume_dir)
            return False
        return True

    def sync_once(self) -> None:
        if not self._check_mounts():
            return

        already_done = self._load_transferred()
        pdfs = [f for f in self.source_dir.glob("*.pdf") if f.is_file() and f.name not in already_done]
        if not pdfs:
            return

        logging.info("ConsumeSync: %d new file(s) to forward.", len(pdfs))
        for pdf in pdfs:
            try:
                shutil.copy2(pdf, self.consume_dir / pdf.name)
                self._record_transferred(pdf)
                logging.info("ConsumeSync: forwarded %s", pdf.name)
            except Exception as exc:
                logging.error("ConsumeSync: failed to forward %s — %s", pdf.name, exc)

    def run(self) -> None:
        logging.info("ConsumeSync started (source=%s, consume=%s, interval=%ds)",
                     self.source_dir, self.consume_dir, self.interval)
        while True:
            try:
                self.sync_once()
            except Exception as exc:
                logging.error("ConsumeSync: unexpected error — %s", exc)
            time.sleep(self.interval)
