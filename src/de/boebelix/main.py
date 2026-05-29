import logging

from dotenv import load_dotenv

from .button import ButtonMonitor
from .config import ScanConfig
from .scanner import Orchestrator
from .uploader import create_uploader


def main() -> None:
    load_dotenv()
    config = ScanConfig()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(),
        ],
    )

    uploader = create_uploader(config)
    orchestrator = Orchestrator(config, uploader)
    monitor = ButtonMonitor(config, orchestrator.run, uploader)
    monitor.run()

if __name__ == "__main__":
    main()
