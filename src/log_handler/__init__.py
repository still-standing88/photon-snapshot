"""Logging + crash capture, mirroring playForm's ``log_handler`` package.

Typical use::

    from log_handler import LoggingSetup, get_logger
    LoggingSetup()                      # once, early in app.py
    get_logger().info("something")      # anywhere

Module-level ``logging.getLogger(__name__)`` calls also work and land in the
same errors.log, since the handler is attached to the root logger.
"""

from .manager import LoggingSetup


def get_logger():
    return LoggingSetup.get_logger()


__all__ = ["LoggingSetup", "get_logger"]
