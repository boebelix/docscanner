import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from .config import ScanConfig


class Uploader(ABC):
    """Abstract base class for upload targets."""

    @abstractmethod
    def upload(self, source_dir: Path) -> None:
        """Upload all PDF files from source_dir to the target and remove them afterwards."""
        ...


class RsyncUploader(Uploader):
    """Uploads files via rsync. Target can be a local path or remote URI (user@host:/path)."""

    def __init__(self, target: str) -> None:
        self.target = target

    def upload(self, source_dir: Path) -> None:
        files = list(source_dir.glob("*.pdf"))
        if not files:
            return
        logging.info("Uploading %d file(s) via rsync to %s ...", len(files), self.target)
        subprocess.run(
            ["rsync", "-av", "--remove-source-files", f"{source_dir}/", self.target],
            check=True,
        )


class NfsUploader(Uploader):
    """Moves PDF files to a mounted NFS share. Skips silently if the mount is not active."""

    def __init__(self, mount_point: Path) -> None:
        self.mount_point = mount_point

    def upload(self, source_dir: Path) -> None:
        files = list(source_dir.glob("*.pdf"))
        if not files:
            return
        if not os.path.ismount(self.mount_point):
            logging.warning("NFS mount %s is not active, skipping upload.", self.mount_point)
            return
        logging.info("Moving %d file(s) to NFS share %s ...", len(files), self.mount_point)
        for file in files:
            shutil.move(str(file), self.mount_point / file.name)


class SmbUploader(Uploader):
    """Moves PDF files to a mounted SMB/CIFS share. Skips silently if the mount is not active."""

    def __init__(self, mount_point: Path) -> None:
        self.mount_point = mount_point

    def upload(self, source_dir: Path) -> None:
        files = list(source_dir.glob("*.pdf"))
        if not files:
            return
        if not os.path.ismount(self.mount_point):
            logging.warning("SMB mount %s is not active, skipping upload.", self.mount_point)
            return
        logging.info("Moving %d file(s) to SMB share %s ...", len(files), self.mount_point)
        for file in files:
            shutil.move(str(file), self.mount_point / file.name)


class MultiUploader(Uploader):
    """Runs multiple uploaders in sequence. Each failure is logged but does not stop the others."""

    def __init__(self, uploaders: list[Uploader]) -> None:
        self.uploaders = uploaders

    def upload(self, source_dir: Path) -> None:
        for uploader in self.uploaders:
            try:
                uploader.upload(source_dir)
            except Exception as e:
                logging.error("Uploader %s failed: %s", type(uploader).__name__, e)


_FACTORIES = {
    "nfs": lambda config: NfsUploader(config.remote_share),
    "smb": lambda config: SmbUploader(config.remote_share),
    "rsync": lambda config: RsyncUploader(config.rsync_target),
}


def create_uploader(config: ScanConfig) -> Uploader | None:
    """Creates uploaders based on SCAN_UPLOADER.

    Accepts a single value or a comma-separated list: nfs, smb, rsync, none.
    Multiple values are wrapped in a MultiUploader.
    Raises ValueError for unknown types.
    """
    types = [t.strip().lower() for t in config.uploader_type.split(",") if t.strip()]

    if not types or types == ["none"]:
        return None

    uploaders = []
    for t in types:
        if t == "none":
            continue
        factory = _FACTORIES.get(t)
        if factory is None:
            raise ValueError(
                "Unknown uploader %r in SCAN_UPLOADER — valid values: %s"
                % (t, ", ".join([*_FACTORIES, "none"]))
            )
        uploaders.append(factory(config))

    if len(uploaders) == 1:
        return uploaders[0]
    return MultiUploader(uploaders)
