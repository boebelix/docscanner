import logging
import signal
import time
from typing import Callable

import sane

from .config import ScanConfig
from .uploader import Uploader

_SANE_REINIT_THRESHOLD = 10  # reinit SANE after this many consecutive poll errors
_MAX_BACKOFF_S = 60.0        # maximum retry interval after repeated failures


class ButtonMonitor:
    """Daemon that polls for a scanner button press and retries pending uploads periodically.

    The SANE device is opened once and kept open across polls to minimise USB churn.
    On error the device is closed and reopened next iteration. Consecutive errors trigger
    exponential backoff (up to _MAX_BACKOFF_S) and, after _SANE_REINIT_THRESHOLD failures,
    a full SANE reinit.
    """

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
        except KeyError:
            return False
        return bool(dev.dev.get_option(opt.index))

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
        dev = None
        consec_errors = 0
        backoff = self.config.poll_interval_s

        try:
            logging.info("Waiting for scanner button (%s) ...", self.config.button_option)
            while self._running:
                try:
                    if dev is None:
                        dev = sane.open(self.config.device_id)

                    pressed = self._is_pressed(dev)
                    consec_errors = 0
                    backoff = self.config.poll_interval_s

                    if pressed:
                        dev.close()
                        dev = None
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
                    if dev is not None:
                        try:
                            dev.close()
                        except Exception:
                            pass
                        dev = None
                    consec_errors += 1
                    backoff = min(backoff * 2, _MAX_BACKOFF_S)

                    if consec_errors >= _SANE_REINIT_THRESHOLD:
                        logging.warning("Reinitializing SANE after %d consecutive errors", consec_errors)
                        try:
                            sane.exit()
                        except Exception:
                            pass
                        try:
                            sane.init()
                        except Exception as reinit_err:
                            logging.error("SANE reinit failed: %s", reinit_err)
                        consec_errors = 0

                time.sleep(backoff)
        finally:
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
            sane.exit()

        logging.info("Daemon stopped.")
