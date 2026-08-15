from __future__ import annotations

"""Compatibility entry point for the Kids Animation Studio.

The production implementation lives in :mod:`cartoon_engine`. Keeping this
small wrapper avoids two competing renderers in the repository.
"""

from cartoon_engine import main


if __name__ == "__main__":
    raise SystemExit(main())
