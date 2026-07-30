from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
REQUEST_TIMEOUT = 20

# Standard guitar, high E to low E. MIDI pitches for open strings.
STANDARD_TUNING = (64, 59, 55, 50, 45, 40)
MAX_FRET = 20
