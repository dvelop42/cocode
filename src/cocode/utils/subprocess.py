"""Subprocess execution with streaming output support.

This module provides utilities for running subprocesses with line-by-line
streaming output, proper timeout handling, and cancellation support.
"""

import logging
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class StreamingSubprocess:
    """Execute subprocess with streaming line-by-line output.
    
    Provides:
    - Real-time line-by-line output streaming
    - Separate handling of stdout and stderr
    - Timeout support with proper cleanup
    - Thread-safe cancellation
    """

    def __init__(
        self,
        command: list[str],
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """Initialize a streaming subprocess.
        
        Args:
            command: Command and arguments to execute
            cwd: Working directory for the subprocess
            env: Environment variables for the subprocess
            timeout: Maximum execution time in seconds
        """
        self.command = command
        self.cwd = cwd
        self.env = env
        self.timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False
        self._output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._threads: list[threading.Thread] = []
        
    def run(
        self,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Execute the subprocess with streaming output.
        
        Args:
            stdout_callback: Function called for each stdout line
            stderr_callback: Function called for each stderr line
            
        Returns:
            Exit code of the subprocess
            
        Raises:
            subprocess.TimeoutExpired: If timeout is exceeded
            subprocess.CalledProcessError: If subprocess fails
        """
        logger.debug(f"Starting subprocess: {' '.join(self.command)}")
        
        try:
            self._process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.cwd,
                env=self.env,
                bufsize=1,  # Line buffered
            )
            
            # Start threads to read output
            stdout_thread = threading.Thread(
                target=self._stream_output,
                args=(self._process.stdout, "stdout", stdout_callback),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._stream_output,
                args=(self._process.stderr, "stderr", stderr_callback),
                daemon=True,
            )
            
            self._threads = [stdout_thread, stderr_thread]
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process with timeout
            start_time = time.time()
            while True:
                try:
                    returncode = self._process.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    if self._cancelled:
                        self._process.terminate()
                        try:
                            self._process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            self._process.kill()
                            self._process.wait()
                        raise KeyboardInterrupt("Process cancelled by user")
                    
                    if self.timeout and (time.time() - start_time) > self.timeout:
                        self._process.terminate()
                        try:
                            self._process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            self._process.kill()
                            self._process.wait()
                        raise subprocess.TimeoutExpired(self.command, self.timeout)
            
            # Wait for output threads to finish
            for thread in self._threads:
                thread.join(timeout=1)
            
            logger.debug(f"Subprocess exited with code: {returncode}")
            return returncode
            
        finally:
            self._cleanup()
    
    def _stream_output(
        self,
        pipe: subprocess.PIPE,
        stream_name: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Read lines from a pipe and process them.
        
        Args:
            pipe: The pipe to read from
            stream_name: Name of the stream (stdout/stderr)
            callback: Optional callback for each line
        """
        try:
            for line in pipe:
                if line:
                    line = line.rstrip('\n\r')
                    if callback:
                        callback(line)
                    self._output_queue.put((stream_name, line))
        except Exception as e:
            logger.error(f"Error reading {stream_name}: {e}")
        finally:
            pipe.close()
    
    def cancel(self) -> None:
        """Cancel the running subprocess."""
        self._cancelled = True
        
    def _cleanup(self) -> None:
        """Clean up subprocess resources."""
        if self._process:
            # Ensure process is terminated
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
            
            # Close pipes if still open
            for pipe in [self._process.stdout, self._process.stderr]:
                if pipe and not pipe.closed:
                    pipe.close()
    
    def get_output(self) -> list[tuple[str, str]]:
        """Get all captured output lines.
        
        Returns:
            List of (stream_name, line) tuples
        """
        output = []
        while not self._output_queue.empty():
            try:
                output.append(self._output_queue.get_nowait())
            except queue.Empty:
                break
        return output


def run_with_streaming(
    command: list[str],
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
    stdout_callback: Optional[Callable[[str], None]] = None,
    stderr_callback: Optional[Callable[[str], None]] = None,
) -> tuple[int, list[str], list[str]]:
    """Convenience function to run a subprocess with streaming output.
    
    Args:
        command: Command and arguments to execute
        cwd: Working directory for the subprocess
        env: Environment variables for the subprocess
        timeout: Maximum execution time in seconds
        stdout_callback: Function called for each stdout line
        stderr_callback: Function called for each stderr line
        
    Returns:
        Tuple of (exit_code, stdout_lines, stderr_lines)
        
    Raises:
        subprocess.TimeoutExpired: If timeout is exceeded
    """
    runner = StreamingSubprocess(command, cwd, env, timeout)
    
    stdout_lines = []
    stderr_lines = []
    
    def capture_stdout(line: str) -> None:
        stdout_lines.append(line)
        if stdout_callback:
            stdout_callback(line)
    
    def capture_stderr(line: str) -> None:
        stderr_lines.append(line)
        if stderr_callback:
            stderr_callback(line)
    
    exit_code = runner.run(capture_stdout, capture_stderr)
    
    return exit_code, stdout_lines, stderr_lines