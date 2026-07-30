from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_path: Path | None = None) -> None:
    target = log_path or Path(__file__).resolve().parent / "newbec.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(target, encoding="utf-8")],
        force=True,
    )
