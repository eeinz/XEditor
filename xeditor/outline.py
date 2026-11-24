"""Document outline (table of contents) panel."""

from __future__ import annotations

import html
import re

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .renderer import TocEntry

_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_ATX_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+\s*)?$")
_SETEXT_RE = re.compile(r"^\s{0,3}(=+|-{3,})\s*$")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_CODE_RE = re.compile(r"`([^`]*)`")
_TAG_RE = re.compile(r"<[^>]+>")


def clean_heading_text(text: str) -> str:
    text = _IMAGE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _CODE_RE.sub(r"\1", text)
    text = _TAG_RE.sub("", text)
    text = text.replace("**", "").replace("__", "")
    text = text.replace("~~", "")
    text = text.replace("*", "").replace("_", " ")
    text = html.unescape(text)
    return " ".join(text.split())


def extract_headings(source: str) -> list[tuple[int, int, str]]:
    """Return (line_index, level, text) for ATX and setext headings."""
    headings: list[tuple[int, int, str]] = []
    lines = source.splitlines()
    fence: str | None = None
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if fence is not None:
            if stripped.startswith(fence * 3):
                fence = None
            continue
        match = _FENCE_RE.match(line)
        if match:
            fence = match.group(1)[0]
            continue
        atx = _ATX_RE.match(line)
        if atx:
            text = clean_heading_text(atx.group(2))
            if text:
                headings.append((index, len(atx.group(1)), text))
            continue
        if (
            line.strip()
            and index + 1 < len(lines)
            and _SETEXT_RE.match(lines[index + 1])
            and not line.lstrip().startswith(("-", "*", "+", "|", ">"))
        ):
            level = 1 if lines[index + 1].strip().startswith("=") else 2
            text = clean_heading_text(line)
            if text:
                headings.append((index, level, text))
    return headings


class OutlineTree(QTreeWidget):
    """QTreeWidget that reports wheel activity to the outline panel."""

    wheelUsed = Signal()

    def wheelEvent(self, event) -> None:  # noqa: N802
        self.wheelUsed.emit()
        super().wheelEvent(event)


class OutlinePanel(QWidget):
    headingActivated = Signal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: dict[int, QTreeWidgetItem] = {}
        self._ordered_items: list[QTreeWidgetItem] = []
        self._item_meta: list[tuple[int, str]] = []
        self._structure: tuple[tuple[int, str], ...] | None = None
        self._pending: tuple[str, list[TocEntry]] | None = None
        self._wheel_active = False

        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.setInterval(80)
        self._pending_timer.timeout.connect(self._apply_pending)

        self._wheel_timer = QTimer(self)
        self._wheel_timer.setSingleShot(True)
        self._wheel_timer.setInterval(350)
        self._wheel_timer.timeout.connect(self._finish_wheel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tree = OutlineTree(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(13)
        self.tree.setAnimated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemActivated.connect(self._on_item_clicked)
        self.tree.wheelUsed.connect(self._on_wheel_used)
        layout.addWidget(self.tree, 1)

        self.empty_label = QLabel("文档中暂无标题", self)
        self.empty_label.setObjectName("WelcomeHint")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label, 1)
        self.empty_label.hide()

    # ------------------------------------------------------------------
    def set_content(self, source: str, toc: list[TocEntry]) -> None:
        # A rebuild that arrives while the user is interacting with the tree is
        # deferred. Clearing a QTreeWidget during a mouse press or wheel scroll
        # can otherwise operate on items that are about to disappear and freeze
        # the UI.
        if self._pending is not None:
            self._pending = (source, toc)
            self._pending_timer.start()
            return

        headings = extract_headings(source)
        structure = tuple((level, text) for _, level, text in headings)

        if not headings:
            if self._structure == ():
                return
            if self._interacting():
                self._defer(source, toc)
                return
            self._rebuild(headings, toc)
            return

        if (
            structure == self._structure
            and len(self._ordered_items) == len(headings)
        ):
            # Typing body text only shifts heading line numbers. Update item
            # metadata in place instead of tearing down the whole tree.
            if self._interacting():
                self._defer(source, toc)
                return
            self._update_item_data(headings, toc)
            return

        if self._interacting():
            self._defer(source, toc)
            return
        self._rebuild(headings, toc)

    @staticmethod
    def _mouse_is_down() -> bool:
        return QApplication.mouseButtons() != Qt.MouseButton.NoButton

    def _interacting(self) -> bool:
        return self._mouse_is_down() or self._wheel_active

    def is_wheel_scrolling(self) -> bool:
        return self._wheel_active

    def _on_wheel_used(self) -> None:
        self._wheel_active = True
        self._wheel_timer.start()

    def _finish_wheel(self) -> None:
        self._wheel_active = False
        if self._pending is not None:
            self._pending_timer.start()

    def _defer(self, source: str, toc: list[TocEntry]) -> None:
        self._pending = (source, toc)
        self._pending_timer.start()

    def _apply_pending(self) -> None:
        if self._pending is None:
            return
        if self._interacting():
            self._pending_timer.start()
            return
        source, toc = self._pending
        self._pending = None
        self.set_content(source, toc)

    # ------------------------------------------------------------------
    def _anchors_for(
        self, headings: list[tuple[int, int, str]], toc: list[TocEntry]
    ) -> list[str]:
        if len(toc) == len(headings):
            return [entry.anchor for entry in toc]
        anchors = [""] * len(headings)
        toc_index = 0
        for index, (_, _, text) in enumerate(headings):
            while toc_index < len(toc):
                entry = toc[toc_index]
                toc_index += 1
                if entry.text == text:
                    anchors[index] = entry.anchor
                    break
        return anchors

    def _update_item_data(
        self, headings: list[tuple[int, int, str]], toc: list[TocEntry]
    ) -> None:
        anchors = self._anchors_for(headings, toc)
        meta = [(line, anchor) for (line, _level, _text), anchor in zip(headings, anchors)]
        if meta == self._item_meta:
            return
        items: dict[int, QTreeWidgetItem] = {}
        for item, (line, _level, _text), anchor in zip(
            self._ordered_items, headings, anchors
        ):
            old_line = item.data(0, Qt.ItemDataRole.UserRole)
            old_anchor = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if old_line != line:
                item.setData(0, Qt.ItemDataRole.UserRole, line)
                item.setToolTip(0, f"第 {line + 1} 行")
            if old_anchor != anchor:
                item.setData(0, Qt.ItemDataRole.UserRole + 1, anchor)
            items[line] = item
        self._items = items
        self._item_meta = meta

    def _rebuild(
        self, headings: list[tuple[int, int, str]], toc: list[TocEntry]
    ) -> None:
        structure = tuple((level, text) for _, level, text in headings)
        self.tree.setUpdatesEnabled(False)
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            self._items.clear()
            self._ordered_items.clear()
            self._item_meta = []
            if not headings:
                self.tree.hide()
                self.empty_label.show()
                self._structure = structure
                return

            self.empty_label.hide()
            self.tree.show()
            anchors = self._anchors_for(headings, toc)

            stack: list[tuple[int, QTreeWidgetItem]] = []
            for (line, level, text), anchor in zip(headings, anchors):
                while stack and stack[-1][0] >= level:
                    stack.pop()
                item = QTreeWidgetItem([text])
                item.setData(0, Qt.ItemDataRole.UserRole, line)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, anchor)
                item.setToolTip(0, f"第 {line + 1} 行")
                if stack:
                    stack[-1][1].addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                stack.append((level, item))
                self._ordered_items.append(item)
                self._items[line] = item
                self._item_meta.append((line, anchor))

            self._structure = structure
        finally:
            self.tree.blockSignals(False)
            self.tree.setUpdatesEnabled(True)

        if headings:
            self.tree.expandAll()

    def set_current_line(self, line: int) -> None:
        if not self._items or self._interacting():
            return
        target: QTreeWidgetItem | None = None
        for heading_line, item in self._items.items():
            if heading_line <= line:
                target = item
            else:
                break
        if target is None:
            return
        if self.tree.currentItem() is target:
            return
        self.tree.blockSignals(True)
        try:
            self.tree.setCurrentItem(target)
            self.tree.scrollToItem(target, QTreeWidget.ScrollHint.EnsureVisible)
        finally:
            self.tree.blockSignals(False)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        line = int(item.data(0, Qt.ItemDataRole.UserRole))
        anchor = str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "")
        self.headingActivated.emit(line, anchor)
