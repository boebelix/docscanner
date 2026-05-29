import logging
from pathlib import Path

from wand.image import Image


def process_image(file_path: Path) -> None:
    """Optimizes a scanned JPEG: deskew, level adjustment, white threshold."""
    try:
        with Image(filename=str(file_path)) as img:
            img.deskew(0.4 * img.quantum_range)
            img.level(black=0.1, white=0.9, gamma=1.2)
            img.white_threshold(color="white", threshold=0.85)
            img.save(filename=str(file_path))
        logging.info("Optimized: %s", file_path.name)
    except Exception as e:
        logging.error("Failed to process %s: %s", file_path.name, e)
