"""Boche backend. The draw engine lives beside it at the repo root (engine/), shared with the Verifier,
so make it importable however the server is started."""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.append(_REPO_ROOT)
