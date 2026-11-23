"""Document outline (table of contents) panel."""

from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

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


class OutlinePanel(QWidget):
    headingActivated = Signal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: dict[int, QTreeWidgetItem] = {}
        self._signature: tuple | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(13)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree, 1)

        self.empty_label = QLabel("文档中暂无标题", self)
        self.empty_label.setObjectName("WelcomeHint")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label, 1)
        self.empty_label.hide()

    # ------------------------------------------------------------------
    def set_content(self, source: str, toc: list[TocEntry]) -> None:
        headings = extract_headings(source)
        signature = tuple(headings)
        if signature == self._signature and self._items:
            return
        self._signature = signature
        self.tree.clear()
        self._items.clear()
        if not headings:
            self.tree.hide()
            self.empty_label.show()
            return

        self.empty_label.hide()
        self.tree.show()

        if len(toc) == len(headings):
            anchors = [entry.anchor for entry in toc]
        else:
            anchors = [""] * len(headings)
            remaining = iter(toc)
            for i, (_, _, text) in enumerate(headings):
                for entry in remaining:
                    if entry.text == text:
                        anchors[i] = entry.anchor
                        break
                else:
                    break

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
            self._items[line] = item

        self.tree.expandAll()

    def set_current_line(self, line: int) -> None:
        if not self._items:
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
        self.tree.setCurrentItem(target)
        self.tree.scrollToItem(target, QTreeWidget.ScrollHint.EnsureVisible)
        self.tree.blockSignals(False)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        line = int(item.data(0, Qt.ItemDataRole.UserRole))
        anchor = str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "")
        self.headingActivated.emit(line, anchor)
