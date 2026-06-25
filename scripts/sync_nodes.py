#!/usr/bin/env python3
"""Entry point for deputy — delegates to src/deputy/core/sync.py."""

import sys
from pathlib import Path

# Make the src/ layout importable when run as ``python scripts/sync_nodes.py``
# without ``uv run`` (which would otherwise install the package).
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from deputy.core.sync import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
