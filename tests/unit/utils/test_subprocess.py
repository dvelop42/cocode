"""Tests for streaming subprocess execution."""

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from cocode.utils.subprocess import StreamingSubprocess, run_with_streaming


class TestStreamingSubprocess:
    """Test the StreamingSubprocess class."""

    def test_basic_execution(self, tmp_path: Path):
        """Test basic command execution."""
        command = [sys.executable, "-c", "print('hello'); print('world')"]
        runner = StreamingSubprocess(command, cwd=tmp_path)
        
        stdout_lines = []
        
        def capture_stdout(line: str) -> None:
            stdout_lines.append(line)
        
        exit_code = runner.run(stdout_callback=capture_stdout)
        
        assert exit_code == 0
        assert stdout_lines == ["hello", "world"]
    
    def test_stderr_handling(self, tmp_path: Path):
        """Test stderr is captured separately."""
        command = [
            sys.executable,
            "-c",
            "import sys; print('stdout'); sys.stderr.write('stderr\\n')"
        ]
        runner = StreamingSubprocess(command, cwd=tmp_path)
        
        stdout_lines = []
        stderr_lines = []
        
        def capture_stdout(line: str) -> None:
            stdout_lines.append(line)
        
        def capture_stderr(line: str) -> None:
            stderr_lines.append(line)
        
        exit_code = runner.run(
            stdout_callback=capture_stdout,
            stderr_callback=capture_stderr
        )
        
        assert exit_code == 0
        assert stdout_lines == ["stdout"]
        assert stderr_lines == ["stderr"]
    
    def test_line_by_line_streaming(self, tmp_path: Path):
        """Test that output is streamed line by line."""
        # Script that outputs lines with delays
        command = [
            sys.executable,
            "-c",
            "import time; print('line1', flush=True); time.sleep(0.1); print('line2', flush=True)"
        ]
        
        runner = StreamingSubprocess(command, cwd=tmp_path)
        
        received_times = []
        
        def capture_with_timing(line: str) -> None:
            received_times.append((time.time(), line))
        
        start_time = time.time()
        exit_code = runner.run(stdout_callback=capture_with_timing)
        
        assert exit_code == 0
        assert len(received_times) == 2
        
        # Verify lines were received with delay between them
        assert received_times[0][1] == "line1"
        assert received_times[1][1] == "line2"
        
        # There should be at least 0.05 seconds between lines
        time_diff = received_times[1][0] - received_times[0][0]
        assert time_diff >= 0.05
    
    def test_timeout_handling(self, tmp_path: Path):
        """Test timeout terminates the process."""
        # Script that runs indefinitely
        command = [
            sys.executable,
            "-c",
            "import time; time.sleep(10)"
        ]
        
        runner = StreamingSubprocess(command, cwd=tmp_path, timeout=0.5)
        
        with pytest.raises(subprocess.TimeoutExpired) as exc_info:
            runner.run()
        
        assert exc_info.value.timeout == 0.5
    
    def test_cancellation(self, tmp_path: Path):
        """Test process cancellation."""
        # Script that runs for a while
        command = [
            sys.executable,
            "-c",
            "import time; time.sleep(5)"
        ]
        
        runner = StreamingSubprocess(command, cwd=tmp_path)
        
        def cancel_after_delay():
            time.sleep(0.2)
            runner.cancel()
        
        # Start cancellation in background
        cancel_thread = threading.Thread(target=cancel_after_delay)
        cancel_thread.start()
        
        with pytest.raises(KeyboardInterrupt) as exc_info:
            runner.run()
        
        assert "cancelled" in str(exc_info.value).lower()
        cancel_thread.join()
    
    def test_environment_variables(self, tmp_path: Path):
        """Test environment variables are passed correctly."""
        command = [
            sys.executable,
            "-c",
            "import os; print(os.environ.get('TEST_VAR', 'not_found'))"
        ]
        
        env = {"TEST_VAR": "test_value"}
        runner = StreamingSubprocess(command, cwd=tmp_path, env=env)
        
        stdout_lines = []
        
        def capture_stdout(line: str) -> None:
            stdout_lines.append(line)
        
        exit_code = runner.run(stdout_callback=capture_stdout)
        
        assert exit_code == 0
        assert stdout_lines == ["test_value"]
    
    def test_working_directory(self, tmp_path: Path):
        """Test working directory is set correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        command = [
            sys.executable,
            "-c",
            "import os; print(os.path.exists('test.txt'))"
        ]
        
        runner = StreamingSubprocess(command, cwd=tmp_path)
        
        stdout_lines = []
        
        def capture_stdout(line: str) -> None:
            stdout_lines.append(line)
        
        exit_code = runner.run(stdout_callback=capture_stdout)
        
        assert exit_code == 0
        assert stdout_lines == ["True"]
    
    def test_non_zero_exit_code(self, tmp_path: Path):
        """Test handling of non-zero exit codes."""
        command = [
            sys.executable,
            "-c",
            "import sys; print('error'); sys.exit(42)"
        ]
        
        runner = StreamingSubprocess(command, cwd=tmp_path)
        
        stdout_lines = []
        
        def capture_stdout(line: str) -> None:
            stdout_lines.append(line)
        
        exit_code = runner.run(stdout_callback=capture_stdout)
        
        assert exit_code == 42
        assert stdout_lines == ["error"]
    
    def test_get_output_method(self, tmp_path: Path):
        """Test the get_output method returns all captured lines."""
        command = [
            sys.executable,
            "-c",
            "import sys; print('out1'); sys.stderr.write('err1\\n'); print('out2')"
        ]
        
        runner = StreamingSubprocess(command, cwd=tmp_path)
        exit_code = runner.run()
        
        assert exit_code == 0
        
        output = runner.get_output()
        assert len(output) == 3
        
        # Check we have both stdout and stderr entries
        stdout_entries = [o for o in output if o[0] == "stdout"]
        stderr_entries = [o for o in output if o[0] == "stderr"]
        
        assert len(stdout_entries) == 2
        assert len(stderr_entries) == 1
        assert stderr_entries[0][1] == "err1"
    
    def test_multiline_output(self, tmp_path: Path):
        """Test handling of multiline output."""
        command = [
            sys.executable,
            "-c",
            "for i in range(5): print(f'line{i}')"
        ]
        
        runner = StreamingSubprocess(command, cwd=tmp_path)
        
        stdout_lines = []
        
        def capture_stdout(line: str) -> None:
            stdout_lines.append(line)
        
        exit_code = runner.run(stdout_callback=capture_stdout)
        
        assert exit_code == 0
        assert stdout_lines == ["line0", "line1", "line2", "line3", "line4"]


class TestRunWithStreaming:
    """Test the convenience function run_with_streaming."""
    
    def test_convenience_function(self, tmp_path: Path):
        """Test the run_with_streaming convenience function."""
        command = [
            sys.executable,
            "-c",
            "import sys; print('stdout1'); sys.stderr.write('stderr1\\n'); print('stdout2')"
        ]
        
        callback_stdout = []
        callback_stderr = []
        
        def stdout_cb(line: str) -> None:
            callback_stdout.append(line)
        
        def stderr_cb(line: str) -> None:
            callback_stderr.append(line)
        
        exit_code, stdout_lines, stderr_lines = run_with_streaming(
            command,
            cwd=tmp_path,
            stdout_callback=stdout_cb,
            stderr_callback=stderr_cb
        )
        
        assert exit_code == 0
        assert stdout_lines == ["stdout1", "stdout2"]
        assert stderr_lines == ["stderr1"]
        assert callback_stdout == stdout_lines
        assert callback_stderr == stderr_lines
    
    def test_convenience_function_with_timeout(self, tmp_path: Path):
        """Test run_with_streaming with timeout."""
        command = [
            sys.executable,
            "-c",
            "import time; time.sleep(10)"
        ]
        
        with pytest.raises(subprocess.TimeoutExpired):
            run_with_streaming(command, cwd=tmp_path, timeout=0.5)
    
    def test_convenience_function_no_callbacks(self, tmp_path: Path):
        """Test run_with_streaming without callbacks."""
        command = [
            sys.executable,
            "-c",
            "print('hello')"
        ]
        
        exit_code, stdout_lines, stderr_lines = run_with_streaming(
            command,
            cwd=tmp_path
        )
        
        assert exit_code == 0
        assert stdout_lines == ["hello"]
        assert stderr_lines == []