"""Allow ``python -m xeditor`` to launch the application."""

from .app import run


if __name__ == "__main__":
    raise SystemExit(run())
