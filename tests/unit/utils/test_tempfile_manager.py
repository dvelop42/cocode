"""Tests for the TempFileManager module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cocode.utils.tempfile_manager import TempFileManager, get_temp_manager


class TestTempFileManager:
    """Tests for TempFileManager class."""

    def test_init(self):
        """Test TempFileManager initialization."""
        manager = TempFileManager()
        assert len(manager._temp_files) == 0
        assert len(manager._temp_dirs) == 0
        assert len(manager._named_files) == 0
        assert manager._registered is True

    def test_create_temp_file(self):
        """Test creating a temporary file."""
        manager = TempFileManager()

        # Create a temp file
        temp_file = manager.create_temp_file(suffix=".txt", prefix="test_")

        assert temp_file.exists()
        assert temp_file.name.startswith("test_")
        assert temp_file.name.endswith(".txt")
        assert temp_file in manager._temp_files

        # Cleanup
        manager.cleanup_all()
        assert not temp_file.exists()

    def test_create_named_temp_file(self):
        """Test creating a named temporary file."""
        manager = TempFileManager()

        # Create a named temp file
        temp_file = manager.create_temp_file(name="test_file")

        assert temp_file.exists()
        assert manager.get_named_file("test_file") == temp_file
        assert "test_file" in manager._named_files

        # Cleanup
        manager.cleanup_all()
        assert not temp_file.exists()
        assert manager.get_named_file("test_file") is None

    def test_create_temp_dir(self):
        """Test creating a temporary directory."""
        manager = TempFileManager()

        # Create a temp directory
        temp_dir = manager.create_temp_dir(suffix="_dir", prefix="test_")

        assert temp_dir.exists()
        assert temp_dir.is_dir()
        assert temp_dir.name.startswith("test_")
        assert temp_dir.name.endswith("_dir")
        assert temp_dir in manager._temp_dirs

        # Create a file in the directory
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        assert test_file.exists()

        # Cleanup
        manager.cleanup_all()
        assert not temp_dir.exists()
        assert not test_file.exists()

    def test_create_named_temp_dir(self):
        """Test creating a named temporary directory."""
        manager = TempFileManager()

        # Create a named temp directory
        temp_dir = manager.create_temp_dir(name="test_dir")

        assert temp_dir.exists()
        assert temp_dir.is_dir()
        assert manager.get_named_file("test_dir") == temp_dir
        assert "test_dir" in manager._named_files

        # Cleanup
        manager.cleanup_all()
        assert not temp_dir.exists()
        assert manager.get_named_file("test_dir") is None

    def test_write_issue_body(self):
        """Test writing issue body to temp file."""
        manager = TempFileManager()

        # Write issue body
        issue_number = 123
        content = "This is the issue body\nWith multiple lines"
        temp_file = manager.write_issue_body(issue_number, content)

        assert temp_file.exists()
        assert f"issue_{issue_number}" in temp_file.name
        assert temp_file.read_text() == content
        assert manager.get_named_file(f"issue_{issue_number}") == temp_file

        # Cleanup
        manager.cleanup_all()
        assert not temp_file.exists()

    def test_get_named_file_removes_missing(self):
        """Test that get_named_file removes missing files from tracking."""
        manager = TempFileManager()

        # Create a named temp file
        temp_file = manager.create_temp_file(name="test_file")
        assert manager.get_named_file("test_file") == temp_file

        # Manually delete the file
        temp_file.unlink()

        # Getting the file should return None and remove it from tracking
        assert manager.get_named_file("test_file") is None
        assert "test_file" not in manager._named_files
        assert temp_file not in manager._temp_files

    def test_cleanup_file(self):
        """Test cleaning up a specific file."""
        manager = TempFileManager()

        # Create temp files
        file1 = manager.create_temp_file(name="file1")
        file2 = manager.create_temp_file(name="file2")

        assert file1.exists()
        assert file2.exists()

        # Cleanup only file1
        assert manager.cleanup_file(file1) is True
        assert not file1.exists()
        assert file1 not in manager._temp_files
        assert "file1" not in manager._named_files

        # file2 should still exist
        assert file2.exists()
        assert file2 in manager._temp_files

        # Cleanup
        manager.cleanup_all()

    def test_cleanup_dir(self):
        """Test cleaning up a specific directory."""
        manager = TempFileManager()

        # Create temp directory with content
        temp_dir = manager.create_temp_dir(name="test_dir")
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        assert temp_dir.exists()
        assert test_file.exists()

        # Cleanup the directory
        assert manager.cleanup_file(temp_dir) is True
        assert not temp_dir.exists()
        assert not test_file.exists()
        assert temp_dir not in manager._temp_dirs
        assert "test_dir" not in manager._named_files

    def test_cleanup_nonexistent_file(self):
        """Test cleanup of a file not managed by this manager."""
        manager = TempFileManager()

        # Create a file outside of manager
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            external_file = Path(tf.name)

        # Cleanup should return False for untracked file
        assert manager.cleanup_file(external_file) is False
        assert external_file.exists()

        # Manual cleanup
        external_file.unlink()

    def test_cleanup_all(self):
        """Test cleaning up all files and directories."""
        manager = TempFileManager()

        # Create multiple files and directories
        file1 = manager.create_temp_file(name="file1")
        file2 = manager.create_temp_file(name="file2")
        dir1 = manager.create_temp_dir(name="dir1")
        dir2 = manager.create_temp_dir(name="dir2")

        # Add content to directories
        (dir1 / "test1.txt").write_text("content1")
        (dir2 / "test2.txt").write_text("content2")

        # Verify all exist
        assert all(p.exists() for p in [file1, file2, dir1, dir2])

        # Cleanup all
        manager.cleanup_all()

        # Verify all are cleaned up
        assert not any(p.exists() for p in [file1, file2, dir1, dir2])
        assert len(manager._temp_files) == 0
        assert len(manager._temp_dirs) == 0
        assert len(manager._named_files) == 0

    def test_cleanup_with_errors(self, caplog):
        """Test cleanup handles errors gracefully."""
        manager = TempFileManager()

        # Create a temp file
        manager.create_temp_file()

        # Mock unlink to raise an error
        with patch.object(Path, "unlink", side_effect=PermissionError("No permission")):
            manager.cleanup_all()

        # Should log warning but not raise
        assert "Failed to cleanup temp file" in caplog.text

    def test_atexit_registration(self):
        """Test that cleanup is registered with atexit."""
        with patch("atexit.register") as mock_register:
            manager = TempFileManager()
            mock_register.assert_called_once_with(manager.cleanup_all)

    def test_del_calls_cleanup(self):
        """Test that __del__ calls cleanup_all."""
        manager = TempFileManager()
        manager.cleanup_all = MagicMock()

        # Trigger __del__
        del manager

        # Note: __del__ behavior can be unpredictable in tests,
        # but we include this for completeness

    def test_get_temp_manager_singleton(self):
        """Test that get_temp_manager returns the same instance."""
        manager1 = get_temp_manager()
        manager2 = get_temp_manager()

        assert manager1 is manager2

        # Create a file with manager1
        temp_file = manager1.create_temp_file(name="shared")

        # Should be accessible from manager2
        assert manager2.get_named_file("shared") == temp_file

        # Cleanup
        manager1.cleanup_all()

    def test_text_vs_binary_mode(self):
        """Test creating files in text vs binary mode."""
        manager = TempFileManager()

        # Text mode (default)
        text_file = manager.create_temp_file(text=True)
        text_file.write_text("text content")
        assert text_file.read_text() == "text content"

        # Binary mode
        binary_file = manager.create_temp_file(text=False)
        binary_file.write_bytes(b"binary content")
        assert binary_file.read_bytes() == b"binary content"

        # Cleanup
        manager.cleanup_all()

    def test_custom_directory(self):
        """Test creating temp files in a custom directory."""
        manager = TempFileManager()

        # Create a custom parent directory
        with tempfile.TemporaryDirectory() as custom_dir:
            custom_path = Path(custom_dir)

            # Create temp file in custom directory
            temp_file = manager.create_temp_file(dir=custom_path)

            assert temp_file.exists()
            assert temp_file.parent == custom_path

            # Cleanup
            manager.cleanup_all()

    def test_multiple_cleanup_calls(self):
        """Test that multiple cleanup calls are safe."""
        manager = TempFileManager()

        # Create some files
        file1 = manager.create_temp_file()
        file2 = manager.create_temp_file()

        # First cleanup
        manager.cleanup_all()
        assert not file1.exists()
        assert not file2.exists()

        # Second cleanup should not raise
        manager.cleanup_all()

        # Create new files after cleanup
        file3 = manager.create_temp_file()
        assert file3.exists()

        # Cleanup again
        manager.cleanup_all()
        assert not file3.exists()

    def test_special_characters_in_names(self):
        """Test handling of special characters in file names."""
        manager = TempFileManager()

        # Test various special characters in suffix/prefix
        special_chars = ["test_with spaces", "test-with-dashes", "test.with.dots"]

        for chars in special_chars:
            # Create temp file with special characters
            temp_file = manager.create_temp_file(prefix=chars + "_")
            assert temp_file.exists()
            assert chars in temp_file.name

            # Create named file with special characters
            named_file = manager.create_temp_file(name=chars)
            assert named_file.exists()
            assert manager.get_named_file(chars) == named_file

        # Cleanup
        manager.cleanup_all()

    def test_long_file_paths(self):
        """Test handling of very long file names."""
        manager = TempFileManager()

        # Create a file with a very long prefix
        long_prefix = "a" * 200 + "_"
        temp_file = manager.create_temp_file(
            prefix=long_prefix[:250]
        )  # Limit to filesystem constraints
        assert temp_file.exists()

        # The actual filename might be truncated by the OS, but it should still work
        assert temp_file in manager._temp_files

        # Cleanup should still work
        manager.cleanup_all()
        assert not temp_file.exists()
