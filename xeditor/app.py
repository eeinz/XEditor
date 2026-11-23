"""Application bootstrap for XEditor."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from . import APP_NAME, ORG_NAME, __version__
from .icons import app_icon
from .themes import UI_FONT_CANDIDATES


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("XEditor")
    app.setStyle("Fusion")
    families = set(QFontDatabase.families())
    for family in UI_FONT_CANDIDATES:
        if family in families:
            font = QFont(family)
            font.setPointSize(10)
            app.setFont(font)
            break
    app.setWindowIcon(app_icon())
    return app


def run() -> int:
    app = create_app()
    # Imported after QApplication exists so platform integration is ready.
    from .main_window import MainWindow

    window = MainWindow()
    window.show()

    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if args:
        candidate = Path(args[0])
        if candidate.is_file():
            QTimer.singleShot(0, lambda: window.open_path(str(candidate)))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
