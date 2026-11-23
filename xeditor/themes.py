"""Themes, palettes, Qt stylesheets and preview CSS for XEditor."""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    is_dark: bool

    window: str
    panel: str
    surface: str
    input_bg: str
    border: str
    hover: str
    scroll: str

    text: str
    muted: str
    accent: str
    accent_soft: str
    accent_fg: str
    selection_bg: str
    selection_fg: str

    heading: str
    link: str
    quote: str
    code_bg: str
    code_text: str
    mark_bg: str
    pygments_style: str


LIGHT = Theme(
    key="light",
    name="浅色",
    is_dark=False,
    window="#ffffff",
    panel="#f6f8fa",
    surface="#ffffff",
    input_bg="#ffffff",
    border="#d8dee4",
    hover="#eaeef2",
    scroll="#d0d7de",
    text="#1f2328",
    muted="#656d76",
    accent="#0969da",
    accent_soft="#ddf4ff",
    accent_fg="#ffffff",
    selection_bg="#b6d7ff",
    selection_fg="#1f2328",
    heading="#0a3069",
    link="#0969da",
    quote="#57606a",
    code_bg="#f2f4f7",
    code_text="#1f2328",
    mark_bg="#fff8c5",
    pygments_style="friendly",
)

DARK = Theme(
    key="dark",
    name="深色",
    is_dark=True,
    window="#0d1117",
    panel="#161b22",
    surface="#0d1117",
    input_bg="#0d1117",
    border="#30363d",
    hover="#21262d",
    scroll="#3b434d",
    text="#e6edf3",
    muted="#8b949e",
    accent="#2f81f7",
    accent_soft="#1b2d44",
    accent_fg="#ffffff",
    selection_bg="#264f78",
    selection_fg="#ffffff",
    heading="#79c0ff",
    link="#58a6ff",
    quote="#9aa4af",
    code_bg="#161b22",
    code_text="#e6edf3",
    mark_bg="#4a3b00",
    pygments_style="monokai",
)

THEMES = {"light": LIGHT, "dark": DARK}

UI_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Segoe UI",
    "PingFang SC",
    "Noto Sans CJK SC",
    "Noto Sans",
    "DejaVu Sans",
)

MONO_FONT_CANDIDATES = (
    "Cascadia Mono",
    "Cascadia Code",
    "JetBrains Mono",
    "Consolas",
    "SF Mono",
    "Menlo",
    "DejaVu Sans Mono",
    "Courier New",
)

PREVIEW_FONT_STACK = (
    '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", '
    '"PingFang SC", "Noto Sans CJK SC", sans-serif'
)
PREVIEW_MONO_STACK = (
    '"Cascadia Mono", "Cascadia Code", "Consolas", '
    '"DejaVu Sans Mono", "Courier New", monospace'
)


def resolve_theme(preference: str) -> Theme:
    """Resolve 'system' / 'light' / 'dark' into a concrete Theme."""
    if preference == "dark":
        return DARK
    if preference == "light":
        return LIGHT
    scheme = Qt.ColorScheme.Unknown
    app = QGuiApplication.instance()
    if app is not None:
        try:
            scheme = app.styleHints().colorScheme()
        except Exception:
            scheme = Qt.ColorScheme.Unknown
    return DARK if scheme == Qt.ColorScheme.Dark else LIGHT


def build_palette(theme: Theme) -> QPalette:
    palette = QPalette()
    c = QColor
    palette.setColor(QPalette.ColorRole.Window, c(theme.window))
    palette.setColor(QPalette.ColorRole.WindowText, c(theme.text))
    palette.setColor(QPalette.ColorRole.Base, c(theme.surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, c(theme.panel))
    palette.setColor(QPalette.ColorRole.Text, c(theme.text))
    palette.setColor(QPalette.ColorRole.Button, c(theme.panel))
    palette.setColor(QPalette.ColorRole.ButtonText, c(theme.text))
    palette.setColor(QPalette.ColorRole.BrightText, c("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, c(theme.selection_bg))
    palette.setColor(QPalette.ColorRole.HighlightedText, c(theme.selection_fg))
    palette.setColor(QPalette.ColorRole.ToolTipBase, c(theme.panel))
    palette.setColor(QPalette.ColorRole.ToolTipText, c(theme.text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, c(theme.muted))
    palette.setColor(QPalette.ColorRole.Link, c(theme.link))
    palette.setColor(QPalette.ColorRole.Mid, c(theme.border))
    palette.setColor(QPalette.ColorRole.Dark, c(theme.border))
    palette.setColor(QPalette.ColorRole.Light, c(theme.surface))
    return palette


_QSS = Template(
    """
QMainWindow, QDialog { background-color: $window; }
QWidget { selection-background-color: $accent; selection-color: $accent_fg; }

QMenuBar {
    background-color: $panel;
    border: none;
    border-bottom: 1px solid $border;
    padding: 2px 5px;
}
QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
    border-radius: 5px;
    color: $text;
}
QMenuBar::item:selected { background-color: $hover; }
QMenuBar::item:pressed { background-color: $accent_soft; color: $accent; }

QMenu {
    background-color: $panel;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    color: $text;
    padding: 6px 30px 6px 24px;
    border-radius: 5px;
}
QMenu::item:selected { background-color: $accent; color: $accent_fg; }
QMenu::item:disabled { color: $muted; }
QMenu::separator { height: 1px; background-color: $border; margin: 5px 8px; }

QToolBar {
    background-color: $panel;
    border: none;
    border-bottom: 1px solid $border;
    padding: 4px 8px;
    spacing: 3px;
}
QToolBar::separator {
    width: 1px;
    background-color: $border;
    margin: 4px 7px;
}
QToolButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
    color: $text;
}
QToolButton:hover { background-color: $hover; }
QToolButton:pressed { background-color: $accent_soft; }
QToolButton:checked { background-color: $accent_soft; color: $accent; }
QToolButton::menu-indicator { image: none; }

QDockWidget { color: $text; }
QDockWidget::title {
    background-color: $panel;
    padding: 8px 10px;
    border-bottom: 1px solid $border;
    text-align: left;
}
QDockWidget::close-button, QDockWidget::float-button {
    background: transparent;
    border: none;
    padding: 3px;
    border-radius: 4px;
}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: $hover;
}

QTreeWidget {
    background-color: $surface;
    border: none;
    padding: 6px;
    outline: 0;
    color: $text;
}
QTreeWidget::item {
    padding: 5px 4px;
    border-radius: 5px;
}
QTreeWidget::item:hover { background-color: $hover; }
QTreeWidget::item:selected {
    background-color: $accent_soft;
    color: $accent;
}

QSplitter::handle { background-color: $border; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }
QSplitter::handle:hover { background-color: $accent; }

QLineEdit {
    background-color: $input_bg;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 5px 9px;
    selection-background-color: $accent;
    selection-color: $accent_fg;
}
QLineEdit:focus { border: 1px solid $accent; }
QLineEdit[error="true"] { border: 1px solid #cf222e; }

QPushButton {
    background-color: $panel;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 6px 15px;
}
QPushButton:hover { background-color: $hover; }
QPushButton:pressed { background-color: $accent_soft; }
QPushButton:default {
    background-color: $accent;
    color: $accent_fg;
    border: 1px solid $accent;
}
QPushButton:default:hover { background-color: $accent; color: $accent_fg; }

QStatusBar {
    background-color: $panel;
    border-top: 1px solid $border;
    color: $muted;
}
QStatusBar::item { border: none; }
QStatusBar QLabel {
    color: $muted;
    padding: 0 7px;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: $scroll;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover { background-color: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background-color: $scroll;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover { background-color: $muted; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QPlainTextEdit {
    background-color: $surface;
    color: $text;
    border: none;
    selection-background-color: $selection_bg;
    selection-color: $selection_fg;
}
QTextBrowser {
    background-color: $surface;
    border: none;
    selection-background-color: $selection_bg;
    selection-color: $selection_fg;
}

#EditorContainer { background-color: $surface; }
#FindBar {
    background-color: $panel;
    border-bottom: 1px solid $border;
}
#FindBar QLabel { color: $muted; }
#FindBar QToolButton {
    padding: 4px 7px;
    border-radius: 5px;
    color: $muted;
}
#FindBar QToolButton:checked { background-color: $accent_soft; color: $accent; }
#FindStatus { color: $muted; padding: 0 4px; }
#WelcomeHint { color: $muted; padding: 24px; }

QToolTip {
    background-color: $panel;
    color: $text;
    border: 1px solid $border;
    padding: 4px 7px;
}

QMessageBox { background-color: $window; }
QMessageBox QLabel { color: $text; }
"""
)


def build_stylesheet(theme: Theme) -> str:
    values = {field: getattr(theme, field) for field in theme.__dataclass_fields__}
    return _QSS.substitute(values)


_PREVIEW_CSS = Template(
    """
html, body {
    background-color: $surface;
    color: $text;
}
body {
    font-family: $preview_font;
    font-size: ${font_size}px;
}
p { margin: 9px 0; }
h1, h2, h3, h4, h5, h6 {
    color: $heading;
    font-weight: 600;
}
h1 { font-size: 29px; margin: 24px 0 10px 0; }
h2 { font-size: 23px; margin: 22px 0 9px 0; }
h3 { font-size: 19px; margin: 20px 0 8px 0; }
h4 { font-size: 17px; margin: 16px 0 6px 0; }
h5 { font-size: 15px; margin: 14px 0 6px 0; }
h6 { font-size: 14px; margin: 14px 0 6px 0; color: $muted; }
strong { font-weight: 600; color: $text; }
a { color: $link; text-decoration: none; }
ul, ol { margin: 8px 0; }
li { margin: 3px 0; }
blockquote {
    margin: 12px 0;
    padding: 8px 14px;
    border-left: 4px solid $border;
    background-color: $panel;
    color: $quote;
}
code {
    font-family: $preview_mono;
    font-size: 13px;
    background-color: $code_bg;
    color: $code_text;
}
pre {
    font-family: $preview_mono;
    font-size: 13px;
    background-color: $code_bg;
    color: $text;
    padding: 12px;
    margin: 10px 0;
    white-space: pre-wrap;
}
.codehilite {
    background-color: $code_bg;
    margin: 12px 0;
}
.codehilite pre { background-color: $code_bg; }
.codehilite code { background-color: transparent; }
table {
    border-collapse: collapse;
    margin: 12px 0;
}
th, td {
    border: 1px solid $border;
    padding: 6px 11px;
}
th {
    background-color: $panel;
    color: $text;
    font-weight: 600;
}
hr {
    border: none;
    border-top: 1px solid $border;
    margin: 18px 0;
}
img { margin: 6px 0; }
.footnote { color: $muted; font-size: 13px; }
.footnote-ref { color: $link; }
.toc { background-color: $panel; padding: 10px 16px; margin: 12px 0; }
.toc ul { margin: 2px 0; }
mark { background-color: $mark_bg; }
kbd {
    font-family: $preview_mono;
    font-size: 12px;
    background-color: $panel;
    border: 1px solid $border;
    padding: 1px 5px;
}
"""
)


def build_preview_css(theme: Theme, font_size: int = 15) -> str:
    return _PREVIEW_CSS.substitute(
        surface=theme.surface,
        text=theme.text,
        heading=theme.heading,
        muted=theme.muted,
        link=theme.link,
        border=theme.border,
        quote=theme.quote,
        code_bg=theme.code_bg,
        code_text=theme.code_text,
        mark_bg=theme.mark_bg,
        panel=theme.panel,
        preview_font=PREVIEW_FONT_STACK,
        preview_mono=PREVIEW_MONO_STACK,
        font_size=font_size,
    )


def apply_theme(app: QApplication, theme: Theme) -> None:
    app.setPalette(build_palette(theme))
    app.setStyleSheet(build_stylesheet(theme))
