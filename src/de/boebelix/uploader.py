import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


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
