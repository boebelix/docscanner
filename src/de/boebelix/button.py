import logging
import signal
import time
from typing import Callable

import sane

from .config import ScanConfig
from .uploader import Uploader


class ButtonMonitor:
    """Daemon that polls for a scanner button press and retries pending uploads periodically."""

    def __init__(
        self,
        config: ScanConfig,
        on_press: Callable[[], None],
        uploader: Uploader | None = None,
    ) -> None:
        self.config = config
        self.on_press = on_press
        self.uploader = uploader
        self._running = False

    def _is_pressed(self, dev) -> bool:
        """Reads the button state directly via the SANE C extension.

        dev['scan'] returns the method of the same name due to a name conflict
        in python-sane — option index access bypasses this.
        """
        try:
            opt = dev.opt[self.config.button_option]
            return bool(dev.dev.get_option(opt.index))
        except Exception:
            return False

    def _try_upload(self) -> None:
        """Attempts to upload pending files from the queue directory."""
        if self.uploader:
            try:
                self.uploader.upload(self.config.queue_dir)
            except Exception as e:
                logging.error("Upload failed: %s", e)

    def stop(self, *_) -> None:
        """Stops the daemon loop. Registered as SIGTERM/SIGINT handler."""
        logging.info("Shutting down daemon ...")
        self._running = False

    def run(self) -> None:
        """Starts the daemon loop. Blocks until SIGTERM or SIGINT is received."""
        self._running = True
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        sane.init()

        last_upload_check = 0.0

        try:
            logging.info("Waiting for scanner button (%s) ...", self.config.button_option)
            while self._running:
                try:
                    dev = sane.open(self.config.device_id)
                    pressed = self._is_pressed(dev)
                    dev.close()

                    if pressed:
                        logging.info("Button pressed – starting scan")
                        self.on_press()
                        self._try_upload()
                        last_upload_check = time.monotonic()
                        if self._running:
                            logging.info("Scan complete, waiting for next button press ...")
                    else:
                        elapsed = time.monotonic() - last_upload_check
                        if elapsed >= self.config.upload_check_interval_s:
                            self._try_upload()
                            last_upload_check = time.monotonic()

                except Exception as e:
                    if self._running:
                        logging.error("Error: %s", e)

                time.sleep(self.config.poll_interval_s)
        finally:
            sane.exit()

        logging.info("Daemon stopped.")
