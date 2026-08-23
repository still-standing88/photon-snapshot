"""Application-wide logging + fault capture, adapted from playForm's
``log_handler/manager.py``.

Three things get wired up here, all writing under ``get_logs_dir()``:

* ``errors.log`` - a rotating file handler on the root logger, so any module's
  ``logging.getLogger(__name__)`` output lands somewhere durable.
* ``faults.log`` - Python's own ``faulthandler``, for hard interpreter crashes
  that never reach an ``except`` block. ``utilities.crash_handler`` appends
  native (SEH) crash summaries to the same file.
* ``sys.excepthook`` - so an uncaught Python exception is recorded with a full
  traceback instead of vanishing (in a windowed build there is no console for
  it to print to).

playForm's version also feeds a QTextEdit log console in its tools dialog;
Photon Snapshot has no such widget, so that handler is left out rather than
ported dead.
"""

from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from utilities.functions import get_logs_dir

_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5


def _safe_console_write(msg: str) -> None:
    """Write to the real stdout if there is one.

    A plain ``print()`` here would be a bug: this module's failure paths run
    in windowed builds too (``--windows-console-mode=disable``), where
    ``sys.stdout`` is None and ``print`` raises AttributeError - turning a
    logged warning into a fresh exception. playForm guards the same way with
    its ``_log()`` helper in ``app_init.py``.
    """
    out = sys.__stdout__
    if out is not None:
        try:
            out.write(msg if msg.endswith("\n") else msg + "\n")
            out.flush()
        except Exception:
            pass


class LoggingSetup:
    """Idempotent singleton - constructing it twice reconfigures nothing."""

    _instance: "LoggingSetup | None" = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: Path | str | None = None):
        if getattr(self, "initialized", False):
            return

        self.log_dir = Path(log_dir) if log_dir else Path(get_logs_dir())
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.error_log_file = self.log_dir / "errors.log"
        self.fault_log_file = self.log_dir / "faults.log"
        self.fault_file = None
        self.original_excepthook = None

        self.setup_logging()
        self.setup_fault_handler()
        self.setup_exception_handlers()
        self.initialized = True

    # ------------------------------------------------------------ logging ---
    def setup_logging(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        self.logger = logging.getLogger("AppLogger")
        self.logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        already_attached = any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            and getattr(h, "baseFilename", "") == str(self.error_log_file)
            for h in root_logger.handlers
        )
        if already_attached:
            return

        try:
            file_handler = logging.handlers.RotatingFileHandler(
                self.error_log_file,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError as e:
            # get_logs_dir() already falls back through LOCALAPPDATA and TEMP,
            # so this is close to unreachable - but a logger that cannot open
            # its file must not take the app down with it.
            _safe_console_write(f"Failed to open {self.error_log_file}: {e}")
            return

        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        # Root only: "AppLogger" propagates to root, and attaching the same
        # handler to both (as playForm does) writes every AppLogger record to
        # errors.log twice.
        root_logger.addHandler(file_handler)

    # ------------------------------------------------------------- faults ---
    def setup_fault_handler(self):
        try:
            self.fault_file = open(
                self.fault_log_file, "a", encoding="utf-8", errors="replace"
            )
            # all_threads=True walks every thread's Python frame stack from
            # inside the fatal-error handler, without the protections a
            # running thread would normally have; playForm hit crashes inside
            # faulthandler's own dump that way and restricted it to the
            # faulting thread. --debug (see app.py) sets PHOTON_DEBUG=1 to opt
            # back into the full cross-thread dump when actually hunting a bug.
            debug_mode = os.environ.get("PHOTON_DEBUG") == "1"
            faulthandler.enable(file=self.fault_file, all_threads=debug_mode)
            self.fault_file.write(f"\n{'=' * 50}\n")
            self.fault_file.write(f"Application started - {datetime.now().isoformat()}\n")
            self.fault_file.write(f"{'=' * 50}\n")
            self.fault_file.flush()
        except Exception as e:
            _safe_console_write(f"Failed to setup fault handler: {e}")

    # --------------------------------------------------------- excepthook ---
    def setup_exception_handlers(self):
        self.original_excepthook = sys.excepthook
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            self.logger.error("Uncaught exception:\n%s", error_msg)
        except Exception:
            pass

        try:
            with open(self.error_log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"\n{'=' * 50}\n")
                f.write(f"UNCAUGHT EXCEPTION - {datetime.now().isoformat()}\n")
                f.write(f"{'=' * 50}\n")
                f.write(error_msg)
                f.write(f"\n{'=' * 50}\n")
        except Exception as e:
            _safe_console_write(f"Failed to write exception log: {e}")

        # sys.stderr can be None in a windowed build, which would make the
        # original hook raise on top of the exception it is reporting.
        saved_stderr = sys.stderr
        try:
            sys.stderr = sys.__stderr__
            if sys.stderr is not None and self.original_excepthook is not None:
                self.original_excepthook(exc_type, exc_value, exc_traceback)
        except Exception:
            pass
        finally:
            sys.stderr = saved_stderr

    # ------------------------------------------------------------ cleanup ---
    def cleanup(self):
        if self.fault_file:
            try:
                self.fault_file.write(f"\n{'=' * 50}\n")
                self.fault_file.write(f"Application closed - {datetime.now().isoformat()}\n")
                self.fault_file.write(f"{'=' * 50}\n")
                self.fault_file.close()
            except Exception:
                pass
            self.fault_file = None

    @staticmethod
    def get_logger() -> logging.Logger:
        return logging.getLogger("AppLogger")
