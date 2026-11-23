"""Small dialogs: Markdown cheat sheet and About."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
)

from . import __author__, __author_email__, __version__
from .icons import app_icon
from .renderer import render_document
from .themes import Theme
from .welcome import CHEATSHEET_MD


class MarkdownCheatSheet(QDialog):
    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Markdown 语法速查")
        self.setWindowIcon(app_icon())
        self.resize(780, 660)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 12)
        layout.setSpacing(8)

        browser = QTextBrowser(self)
        browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(True)
        browser.document().setDocumentMargin(26)
        result = render_document(CHEATSHEET_MD, theme)
        browser.setHtml(result.html)
        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)


def show_about(parent) -> None:
    import markdown
    import PySide6

    box = QMessageBox(parent)
    box.setWindowTitle("关于 XEditor")
    box.setWindowIcon(app_icon())
    box.setIconPixmap(app_icon().pixmap(72, 72))
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(
        f"""
        <h3 style="margin: 2px 0 4px 0;">XEditor {__version__}</h3>
        <p style="margin: 0 0 3px 0;">一个基于 Python + PySide6 的 Markdown 阅读与编辑器。</p>
        <p style="margin: 0 0 3px 0;">
            作者：<b>{__author__}</b><br>
            联系邮箱：<b>{__author_email__}</b>
        </p>
        <p style="color: #8b949e; margin-top: 8px;">
            PySide6 {PySide6.__version__} &nbsp;·&nbsp;
            Python-Markdown {markdown.__version__}
        </p>
        """
    )
    box.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.LinksAccessibleByMouse
    )
    ok = box.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok)
    box.exec()
