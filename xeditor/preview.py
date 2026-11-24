"""Live Markdown preview widget."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPalette, QTextDocument
from PySide6.QtWidgets import QTextBrowser

from .renderer import RenderedDocument, TocEntry, render_document
from .themes import Theme


class MarkdownPreview(QTextBrowser):
    fileLinkClicked = Signal(str, str)  # path, fragment
    zoomChanged = Signal(int)

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._base_dir: str | None = None
        self._zoom_steps = 0
        self._toc: list[TocEntry] = []
        self._anchor_blocks: dict[str, int] = {}

        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.setAcceptDrops(False)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.document().setDocumentMargin(30)
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.set_theme(theme)

    # -- theming -----------------------------------------------------------
    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(theme.surface))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme.text))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.selection_bg))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.selection_fg))
        palette.setColor(QPalette.ColorRole.Link, QColor(theme.link))
        self.setPalette(palette)
        self.viewport().setAutoFillBackground(True)

    # -- rendering ---------------------------------------------------------
    def set_markdown(self, source: str, base_dir: str | None) -> list[TocEntry]:
        self._base_dir = base_dir
        if base_dir:
            self.document().setBaseUrl(QUrl.fromLocalFile(str(Path(base_dir)) + "/"))
        ratio = self.scroll_ratio()
        max_width = max(240, self.viewport().width() - 68)
        result: RenderedDocument = render_document(
            source,
            self._theme,
            base_dir=base_dir,
            font_size=15,
            max_image_width=max_width,
        )
        self._toc = result.toc
        self.setHtml(result.html)
        self._index_anchors()
        self._apply_zoom()
        self._restore_ratio_soon(ratio)
        return result.toc

    def _index_anchors(self) -> None:
        """Map HTML anchor names to QTextDocument block numbers once per render."""
        anchors: dict[str, int] = {}
        block = self.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                fmt = fragment.charFormat()
                if fmt.isAnchor():
                    for name in fmt.anchorNames():
                        if name and name not in anchors:
                            anchors[str(name)] = block.blockNumber()
                iterator += 1
            block = block.next()
        self._anchor_blocks = anchors

    def scroll_ratio(self) -> float:
        bar = self.verticalScrollBar()
        if bar.maximum() <= 0:
            return 0.0
        return bar.value() / bar.maximum()

    def set_scroll_ratio(self, ratio: float) -> None:
        ratio = max(0.0, min(1.0, ratio))
        bar = self.verticalScrollBar()
        bar.setValue(round(bar.maximum() * ratio))

    def scroll_to_line_ratio(self, line: int, line_count: int) -> None:
        if line_count <= 1:
            self.set_scroll_ratio(0.0)
            return
        self.set_scroll_ratio(line / (line_count - 1))

    def _restore_ratio_soon(self, ratio: float) -> None:
        QTimer.singleShot(0, lambda: self.set_scroll_ratio(ratio))

    def scroll_to_anchor(self, anchor: str) -> bool:
        """Scroll to an anchor without relying on QTextBrowser's navigation.

        QTextBrowser.scrollToAnchor can block on some documents; using the
        already-laid-out block geometry is deterministic and cheap.
        """
        if not anchor:
            return False
        block_number = self._anchor_blocks.get(anchor)
        if block_number is None:
            return False
        block = self.document().findBlockByNumber(block_number)
        if not block.isValid():
            return False
        bar = self.verticalScrollBar()
        if bar.maximum() <= 0:
            return True
        rect = self.document().documentLayout().blockBoundingRect(block)
        document_height = max(1.0, self.document().size().height())
        ratio = (rect.top() - 10.0) / document_height
        ratio = max(0.0, min(1.0, ratio))
        bar.setValue(round(bar.maximum() * ratio))
        return True

    # -- zoom --------------------------------------------------------------
    def _apply_zoom(self) -> None:
        if self._zoom_steps > 0:
            super().zoomIn(self._zoom_steps)
        elif self._zoom_steps < 0:
            super().zoomOut(-self._zoom_steps)

    def zoom_by(self, delta: int) -> None:
        new_steps = max(-6, min(14, self._zoom_steps + delta))
        if new_steps == self._zoom_steps:
            return
        self._zoom_steps = new_steps
        if delta > 0:
            super().zoomIn(delta)
        else:
            super().zoomOut(-delta)
        self.zoomChanged.emit(self._zoom_steps)

    def set_zoom_steps(self, steps: int) -> None:
        """Apply a saved zoom level to the current document (after setHtml)."""
        steps = max(-6, min(14, int(steps)))
        if steps == self._zoom_steps:
            return
        delta = steps - self._zoom_steps
        self._zoom_steps = steps
        if delta > 0:
            super().zoomIn(delta)
        elif delta < 0:
            super().zoomOut(-delta)

    def reset_zoom(self) -> None:
        if not self._zoom_steps:
            return
        delta = self._zoom_steps
        self._zoom_steps = 0
        if delta > 0:
            super().zoomOut(delta)
        else:
            super().zoomIn(-delta)
        self.zoomChanged.emit(0)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)

    # -- resource loading --------------------------------------------------
    def loadResource(self, resource_type: int, url: QUrl):  # noqa: N802
        if int(resource_type) == int(QTextDocument.ResourceType.ImageResource):
            if url.scheme().lower() in ("http", "https", "ftp"):
                return None
            path: Path | None = None
            if url.isLocalFile():
                path = Path(url.toLocalFile())
            elif self._base_dir and not url.scheme():
                path = Path(self._base_dir) / unquote(url.path())
            if path is not None:
                try:
                    if path.exists():
                        image = QImage(str(path))
                        if not image.isNull():
                            return image
                except OSError:
                    pass
        return super().loadResource(resource_type, url)

    # -- links -------------------------------------------------------------
    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)
            return
        if url.scheme() == "file":
            path = Path(url.toLocalFile())
            self._open_local_link(path, url.fragment())
            return
        if not url.scheme() and not url.path():
            if url.fragment():
                self.scroll_to_anchor(url.fragment())
            return
        if not url.scheme():
            base = Path(self._base_dir) if self._base_dir else Path.cwd()
            path = (base / unquote(url.path())).resolve()
            self._open_local_link(path, url.fragment())
            return
        QDesktopServices.openUrl(url)

    def _open_local_link(self, path: Path, fragment: str = "") -> None:
        if not path.exists():
            return
        if path.suffix.lower() in {".md", ".markdown", ".mdown", ".mkd", ".txt"}:
            self.fileLinkClicked.emit(str(path), fragment)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
