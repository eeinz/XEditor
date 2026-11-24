"""Allow ``python -m xeditor`` to launch the application."""

from .launch import main


if __name__ == "__main__":
    raise SystemExit(main())
