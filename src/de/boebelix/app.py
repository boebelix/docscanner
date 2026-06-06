import logging
import os
import threading

from dotenv import load_dotenv

from .button import ButtonMonitor
from .config import ScanConfig
from .consume_sync import ConsumeSync
from .scanner import Orchestrator
from .uploader import create_uploader


def main() -> None:
    load_dotenv(dotenv_path=os.getenv("DOTENV_PATH"))
    config = ScanConfig()
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    config.queue_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(),
        ],
    )

    sync_thread = threading.Thread(target=ConsumeSync(config).run, daemon=True, name="consume-sync")
    sync_thread.start()

    uploader = create_uploader(config)
    orchestrator = Orchestrator(config, uploader)
    monitor = ButtonMonitor(config, orchestrator.run, uploader)
    monitor.run()

if __name__ == "__main__":
    main()
