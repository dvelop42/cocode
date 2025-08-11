"""Temporary file management for cocode.

This module provides a centralized temporary file manager that:
- Creates and tracks temporary files
- Ensures cleanup on exit
- Provides lifecycle management for temp files
- Handles issue body temp files and other temporary resources
"""

import atexit
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class TempFileManager:
    """Manages temporary files with automatic cleanup.

    This class provides centralized management of temporary files,
    ensuring they are properly cleaned up on exit or when no longer needed.
    """

    def __init__(self) -> None:
        """Initialize the TempFileManager."""
        self._temp_files: set[Path] = set()
        self._temp_dirs: set[Path] = set()
        self._named_files: dict[str, Path] = {}
        self._registered = False
        self._ensure_cleanup_registered()

    def _ensure_cleanup_registered(self) -> None:
        """Register cleanup handler if not already registered."""
        if not self._registered:
            atexit.register(self.cleanup_all)
            self._registered = True
            logger.debug("Registered atexit cleanup handler")

    def create_temp_file(
        self,
        suffix: str | None = None,
        prefix: str | None = "cocode_",
        dir: Path | None = None,
        text: bool = True,
        name: str | None = None,
    ) -> Path:
        """Create a temporary file that will be automatically cleaned up.

        Args:
            suffix: Optional suffix for the temp file
            prefix: Prefix for the temp file (default: "cocode_")
            dir: Directory to create the file in (default: system temp)
            text: Whether to open in text mode (default: True)
            name: Optional name to register this file under for later retrieval

        Returns:
            Path to the created temporary file
        """
        mode = "w+t" if text else "w+b"

        with tempfile.NamedTemporaryFile(
            mode=mode, suffix=suffix, prefix=prefix, dir=dir, delete=False
        ) as tf:
            temp_path = Path(tf.name)
            self._temp_files.add(temp_path)

            if name:
                self._named_files[name] = temp_path

            logger.debug(f"Created temp file: {temp_path}")
            return temp_path

    def create_temp_dir(
        self,
        suffix: str | None = None,
        prefix: str | None = "cocode_",
        dir: Path | None = None,
        name: str | None = None,
    ) -> Path:
        """Create a temporary directory that will be automatically cleaned up.

        Args:
            suffix: Optional suffix for the temp directory
            prefix: Prefix for the temp directory (default: "cocode_")
            dir: Parent directory to create the temp dir in (default: system temp)
            name: Optional name to register this directory under for later retrieval

        Returns:
            Path to the created temporary directory
        """
        temp_dir = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir))
        self._temp_dirs.add(temp_dir)

        if name:
            self._named_files[name] = temp_dir

        logger.debug(f"Created temp directory: {temp_dir}")
        return temp_dir

    def write_issue_body(self, issue_number: int, content: str) -> Path:
        """Create a temporary file for an issue body.

        Args:
            issue_number: The GitHub issue number
            content: The issue body content

        Returns:
            Path to the created temporary file
        """
        temp_file = self.create_temp_file(
            suffix=f"_issue_{issue_number}.txt", prefix="cocode_", name=f"issue_{issue_number}"
        )

        temp_file.write_text(content, encoding="utf-8")
        logger.debug(f"Wrote issue #{issue_number} body to {temp_file}")
        return temp_file

    def get_named_file(self, name: str) -> Path | None:
        """Get a previously created named temp file or directory.

        Args:
            name: The name the file/directory was registered under

        Returns:
            Path to the file/directory if it exists, None otherwise
        """
        path = self._named_files.get(name)
        if path and path.exists():
            return path
        elif path:
            # File was deleted, remove from tracking
            del self._named_files[name]
            self._temp_files.discard(path)
            self._temp_dirs.discard(path)
        return None

    def cleanup_file(self, path: Path) -> bool:
        """Clean up a specific temporary file or directory.

        Args:
            path: Path to the file or directory to clean up

        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            if path in self._temp_dirs:
                shutil.rmtree(path, ignore_errors=True)
                self._temp_dirs.discard(path)
                logger.debug(f"Cleaned up temp directory: {path}")
            elif path in self._temp_files:
                if path.exists():
                    path.unlink()
                self._temp_files.discard(path)
                logger.debug(f"Cleaned up temp file: {path}")
            else:
                return False

            # Remove from named files if present
            for name, file_path in list(self._named_files.items()):
                if file_path == path:
                    del self._named_files[name]

            return True
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")
            return False

    def cleanup_all(self) -> None:
        """Clean up all tracked temporary files and directories.

        This method is automatically called on exit but can also be
        called manually to clean up resources early.
        """
        logger.debug("Starting cleanup of all temp files")

        def _safe_remove(path: Path, is_dir: bool) -> None:
            try:
                if is_dir:
                    if path.exists():
                        shutil.rmtree(path, ignore_errors=True)
                        logger.debug(f"Cleaned up temp directory: {path}")
                else:
                    if path.exists():
                        path.unlink()
                        logger.debug(f"Cleaned up temp file: {path}")
            except Exception as e:
                kind = "directory" if is_dir else "file"
                logger.warning(f"Failed to cleanup temp {kind} {path}: {e}")

        # Clean directories first, then files
        for temp_dir in list(self._temp_dirs):
            _safe_remove(temp_dir, is_dir=True)

        for temp_file in list(self._temp_files):
            _safe_remove(temp_file, is_dir=False)

        # Clear all tracking
        self._temp_files.clear()
        self._temp_dirs.clear()
        self._named_files.clear()

        logger.debug("Completed cleanup of all temp files")

    def __del__(self) -> None:
        """Ensure cleanup on deletion."""
        self.cleanup_all()


__all__ = ["TempFileManager", "get_temp_manager"]

# Backwards-compatible global singleton (deprecated)
_temp_manager: TempFileManager | None = None


def get_temp_manager() -> TempFileManager:  # pragma: no cover - API compatibility shim
    """Return a module-level TempFileManager singleton.

    Deprecated: prefer injecting a TempFileManager instance where needed.
    Retained for compatibility with existing callers and tests.
    """
    global _temp_manager
    if _temp_manager is None:
        _temp_manager = TempFileManager()
    return _temp_manager
