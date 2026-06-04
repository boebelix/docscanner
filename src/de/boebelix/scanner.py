import logging
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import img2pdf

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import ScanConfig
from .image import process_image
from .uploader import Uploader


def _check_storage(config: ScanConfig) -> None:
    """Raises MemoryError if free disk space drops below config.min_storage_mb."""
    usage = shutil.disk_usage("/")
    free_mb = usage.free / (1024**2)
    if free_mb < config.min_storage_mb:
        raise MemoryError("Low storage: only %.1f MB free!" % free_mb)


class ScanHandler(FileSystemEventHandler):
    """Watchdog handler that submits newly written JPEG files for image optimization."""

    def __init__(self, executor: ProcessPoolExecutor) -> None:
        self.executor = executor
        self.futures = []

    def on_closed(self, event) -> None:
        """Submits each completed JPEG file to the image optimizer."""
        if not event.is_directory and event.src_path.endswith(".jpg"):
            self.futures.append(self.executor.submit(process_image, Path(event.src_path)))


class Orchestrator:
    """Coordinates a full scan job: hardware scan → image optimization → PDF → upload."""

    def __init__(self, config: ScanConfig, uploader: Uploader | None = None) -> None:
        self.config = config
        self.uploader = uploader

    def run(self) -> None:
        """Runs a single scan job. Blocks until complete."""
        try:
            _check_storage(self.config)
            self.config.temp_dir.mkdir(parents=True, exist_ok=True)
            self.config.queue_dir.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")

            with ProcessPoolExecutor(max_workers=3) as executor:
                handler = ScanHandler(executor)
                observer = Observer()
                observer.schedule(handler, str(self.config.temp_dir), recursive=False)
                observer.start()

                try:  # finally ensures observer is stopped even if scanimage fails
                    logging.info("Hardware scan starting...")
                    subprocess.run(
                        [
                            "scanimage",
                            "--device", self.config.device_id,
                            "--source", "ADF Duplex",
                            "--mode", "Color",
                            "--resolution", "600",
                            "--page-width", "210",
                            "--page-height", "297",
                            "--brightness", "20",
                            "--contrast", "10",
                            "--format=jpeg",
                            f"--batch={self.config.temp_dir}/page%03d.jpg",
                        ],
                        check=True,
                    )

                    while any(not f.done() for f in handler.futures):
                        time.sleep(0.5)

                    self._finalize(timestamp)
                finally:
                    observer.stop()
                    observer.join()

        except subprocess.CalledProcessError as e:
            if e.returncode in (-2, 130):
                raise
            logging.error("Scan failed: %s", e)
        except Exception as e:
            logging.error("Critical error: %s", e)
        finally:
            shutil.rmtree(self.config.temp_dir, ignore_errors=True)

    def _finalize(self, timestamp: str) -> None:
        """Merges scanned pages into a PDF and uploads via the configured uploader."""
        pdf_path = self.config.queue_dir / f"Scan_{timestamp}.pdf"
        files = sorted(str(f) for f in self.config.temp_dir.glob("*.jpg"))

        if files:
            logging.info("Creating PDF: %s", pdf_path.name)
            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(files))
            if self.uploader:
                self.uploader.upload(self.config.queue_dir)
