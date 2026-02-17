"""
Pipeline Logging Utilities

Provides centralized logging to console and file.
"""

import sys
import time
import threading
from pathlib import Path


class TeeLogger:
    """
    Write to a terminal stream and a shared log file simultaneously.

    Used by TeeLogManager to capture stdout/stderr.
    """

    def __init__(self, terminal, log_handle, lock, line_buffered=True):
        self.terminal = terminal
        self.log = log_handle
        self._lock = lock
        self._line_buffered = line_buffered
        self.encoding = getattr(terminal, "encoding", "utf-8") or "utf-8"
        self.errors = getattr(terminal, "errors", "replace") or "replace"

    def write(self, message):
        if not message:
            return 0
        if isinstance(message, bytes):
            message = message.decode(self.encoding, errors=self.errors)
        with self._lock:
            self.terminal.write(message)
            self.log.write(message)
            if self._line_buffered and "\n" in message:
                self.terminal.flush()
                self.log.flush()
        return len(message)

    def flush(self):
        with self._lock:
            self.terminal.flush()
            self.log.flush()

    def close(self):
        # Managed by TeeLogManager
        pass

    def fileno(self):
        return self.terminal.fileno()

    def isatty(self):
        return self.terminal.isatty()

    def writable(self):
        return True

    def readable(self):
        return False

    def seekable(self):
        return False

    def __getattr__(self, name):
        return getattr(self.terminal, name)


class TeeLogManager:
    """
    Install stdout/stderr tee streams with a shared log file.

    Usage:
        log_manager = TeeLogManager("run.log")
        log_manager.install()
        # ... all print() and stderr output goes to both console and file ...
        log_manager.close()
    """

    def __init__(self, log_file):
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        encoding = getattr(self._orig_stdout, "encoding", "utf-8") or "utf-8"
        self._log_handle = open(log_file, "w", encoding=encoding, errors="replace", buffering=1)
        self._lock = threading.Lock()
        self.stdout = TeeLogger(self._orig_stdout, self._log_handle, self._lock)
        self.stderr = TeeLogger(self._orig_stderr, self._log_handle, self._lock)
        self._closed = False

    def install(self):
        """Replace sys.stdout and sys.stderr with tee loggers."""
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def flush(self):
        """Flush both streams."""
        self.stdout.flush()
        self.stderr.flush()

    def close(self):
        """Restore original streams and close log file."""
        if self._closed:
            return
        self.flush()
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        self._log_handle.close()
        self._closed = True


class PipelineLogger:
    """
    Logger that writes to both console and session log file.

    Usage:
        logger = PipelineLogger(log_dir="debug_logs", session_name="my_session")
        logger.log("Starting pipeline...")
    """

    def __init__(self, log_dir="debug_logs", session_name=None):
        """
        Initialize logger.

        Args:
            log_dir: Directory for log files
            session_name: Optional session name prefix. If None, uses timestamp.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        self.session_ts = time.strftime("%Y%m%d_%H%M%S")
        session_prefix = session_name or "continuous_session"
        self.session_log = self.log_dir / f"{session_prefix}_{self.session_ts}.log"

    def log(self, msg):
        """Log message to console and file."""
        print(msg, flush=True)
        with open(self.session_log, 'a') as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

    @property
    def timestamp(self):
        """Get current timestamp string."""
        return time.strftime("%Y%m%d_%H%M%S")
