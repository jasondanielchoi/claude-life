"""
BaseScript — abstract base class for all Life Ops automation scripts.

Provides:
  - Rotating file logger + stdout handler, scoped to ~/life/logs/<script>.log
  - Abstract run() method that must return a JSON-serialisable dict
  - main() classmethod: parses --debug flag, runs the script, prints JSON to stdout
  - Automatic elapsed-time logging

Subclass usage:
    class MyScript(BaseScript):
        def run(self) -> dict:
            self.logger.info("doing work...")
            return {"result": "done"}

    if __name__ == "__main__":
        MyScript.main()
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from abc import ABC, abstractmethod
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

LOGS_DIR = Path("~/life/logs").expanduser()


class BaseScript(ABC):
    """Abstract base for all Life Ops automation scripts."""

    def __init__(self, log_level: int = logging.INFO) -> None:
        # Derive script name from the concrete class name (lowercased)
        self.script_name: str = type(self).__name__.lower()
        self.logger: logging.Logger = self._setup_logger(log_level)

    # ── Logging ───────────────────────────────────────────────────────────────

    def _setup_logger(self, log_level: int) -> logging.Logger:
        """
        Configure a logger that writes to both:
          - ~/life/logs/<script_name>.log  (rotating, max 2 MB × 5 backups)
          - stdout
        """
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(self.script_name)
        logger.setLevel(log_level)

        # Avoid adding duplicate handlers if the module is re-imported
        if logger.handlers:
            return logger

        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = RotatingFileHandler(
            LOGS_DIR / f"{self.script_name}.log",
            maxBytes=2_000_000,   # 2 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        return logger

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def run(self) -> dict[str, Any]:
        """
        Execute the script.

        Must return a dict that is JSON-serialisable (str keys, JSON-safe values).
        This dict is printed to stdout so Claude can consume it programmatically.
        datetime objects are serialised via default=str.
        """

    # ── CLI entrypoint ────────────────────────────────────────────────────────

    @classmethod
    def main(cls) -> None:
        """
        Standard CLI entrypoint. Wire up as:
            if __name__ == "__main__":
                MyScript.main()

        Parses --debug flag, instantiates the script, calls run(), prints JSON.
        """
        doc = (cls.__doc__ or cls.__name__).strip().splitlines()[0]
        parser = argparse.ArgumentParser(description=doc)
        parser.add_argument(
            "--debug", action="store_true", help="Enable DEBUG-level logging"
        )
        # parse_known_args lets subclasses add their own args without conflicting
        args, _ = parser.parse_known_args()

        log_level = logging.DEBUG if args.debug else logging.INFO
        script = cls(log_level=log_level)

        t0 = time.monotonic()
        try:
            result = script.run()
            elapsed = time.monotonic() - t0
            script.logger.info("Completed in %.2fs", elapsed)
            # Emit structured JSON to stdout (Claude reads this in future sessions)
            print(json.dumps(result, indent=2, default=str))
        except Exception:
            elapsed = time.monotonic() - t0
            script.logger.exception("Script failed after %.2fs", elapsed)
            raise
