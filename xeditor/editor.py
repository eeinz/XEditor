"""The Markdown source editor widget."""

from __future__ import annotations

import datetime as _dt
import re

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QPalette,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from .themes import MONO_FONT_CANDIDATES, Theme


def pick_mono_font(size: int = 11) -> QFont:
    families = set(QFontDatabase.families())
    for name in MONO_FONT_CANDIDATES:
        if name in families:
            font = QFont(name)
            font.setPointSize(size)
            font.setStyleHint(QFont.StyleHint.Monospace)
            return font
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(size)
    return font


class LineNumberArea(QWidget):
    def __init__(self, editor: "MarkdownEditor") -> None:
        super().__init__(editor)
        self._editor = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self._editor.paint_line_numbers(event)


class MarkdownEditor(QPlainTextEdit):
    fileDropped = Signal(str)
    zoomChanged = Signal(int)

    INDENT = "    "

    def __init__(self, theme: Theme, font: QFont | None = None, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._line_color = QColor(theme.panel)
        self._line_number_bg = QColor(theme.surface)
        self._line_number_fg = QColor(theme.muted)
        self._line_number_current = QColor(theme.accent)
        self._search_selections: list[QTextEdit.ExtraSelection] = []

        self.setFont(font or pick_mono_font())
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setCenterOnScroll(True)
        self.setTabChangesFocus(False)
        self.setUndoRedoEnabled(True)
        self.setPlaceholderText("在此开始写作，或打开一个 Markdown 文件……")
        self.setAcceptDrops(True)

        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._on_update_request)
        self.cursorPositionChanged.connect(self._update_extra_selections)

        self._update_tab_stop()
        self._update_line_number_width()
        self._apply_palette()
        self._update_extra_selections()

    # -- theming -----------------------------------------------------------
    def _apply_palette(self) -> None:
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor(self._theme.surface))
        pal.setColor(QPalette.ColorRole.Text, QColor(self._theme.text))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(self._theme.selection_bg))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(self._theme.selection_fg))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(self._theme.muted))
        self.setPalette(pal)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._line_color = QColor(theme.panel)
        self._line_number_bg = QColor(theme.surface)
        self._line_number_fg = QColor(theme.muted)
        self._line_number_current = QColor(theme.accent)
        self._apply_palette()
        self._update_extra_selections()
        self.line_number_area.update()

    # -- font / zoom -------------------------------------------------------
    def _update_tab_stop(self) -> None:
        metrics = QFontMetricsF(self.font())
        self.setTabStopDistance(metrics.horizontalAdvance(" ") * 4)

    def set_editor_font(self, font: QFont) -> None:
        self.setFont(font)
        self._update_tab_stop()
        self._update_line_number_width()
        self.line_number_area.update()

    def zoom(self, delta: int) -> None:
        size = self.font().pointSize()
        new_size = max(8, min(36, size + delta))
        if new_size == size:
            return
        font = QFont(self.font())
        font.setPointSize(new_size)
        self.set_editor_font(font)
        self.zoomChanged.emit(new_size)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)

    # -- line numbers ------------------------------------------------------
    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _on_update_request(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self._line_number_bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        offset = self.contentOffset()
        top = round(self.blockBoundingGeometry(block).translated(offset).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current_block = self.textCursor().blockNumber()
        line_height = self.fontMetrics().height()
        width = self.line_number_area.width() - 10

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                color = self._line_number_current if block_number == current_block else self._line_number_fg
                painter.setPen(color)
                painter.drawText(
                    0,
                    top,
                    width,
                    line_height,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    # -- extra selections --------------------------------------------------
    def _update_extra_selections(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        if not self.textCursor().hasSelection():
            selection = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(self._line_color)
            fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.format = fmt
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        selections.extend(self._search_selections)
        self.setExtraSelections(selections)
        self.line_number_area.update()

    def set_search_selections(self, selections: list[QTextEdit.ExtraSelection]) -> None:
        self._search_selections = selections
        self._update_extra_selections()

    # -- navigation --------------------------------------------------------
    def goto_line(self, line_number: int, select: bool = False) -> None:
        block = self.document().findBlockByNumber(max(0, line_number - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        if select:
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # -- keyboard behaviour ------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Tab and not (
            event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        ):
            if self.textCursor().hasSelection():
                self.indent_selection()
            else:
                self._insert_tab_spaces()
            return
        if event.key() == Qt.Key.Key_Backtab:
            self.outdent_selection()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._continue_markdown_block():
                return
        super().keyPressEvent(event)

    def _insert_tab_spaces(self) -> None:
        cursor = self.textCursor()
        column = cursor.positionInBlock()
        spaces = 4 - (column % 4)
        cursor.insertText(" " * spaces)
        self.setTextCursor(cursor)

    def _selected_blocks(self) -> list[QTextCursor]:
        cursor = self.textCursor()
        doc = self.document()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if start == end:
            return [QTextCursor(cursor.block())]
        first = doc.findBlock(start)
        last = doc.findBlock(end)
        if end > start and last.position() == end and last != first:
            last = last.previous()
        blocks: list[QTextCursor] = []
        block = first
        while block.isValid():
            blocks.append(QTextCursor(block))
            if block == last:
                break
            block = block.next()
        return blocks

    def indent_selection(self) -> None:
        blocks = self._selected_blocks()
        if not blocks:
            return
        cursor = self.textCursor()
        anchor, position = cursor.anchor(), cursor.position()
        handle = self.textCursor()
        handle.beginEditBlock()
        for block_cursor in reversed(blocks):
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.insertText(self.INDENT)
        handle.endEditBlock()
        inserted = len(self.INDENT)
        new_anchor = anchor + (inserted if anchor > 0 else 0)
        new_position = position + inserted * len(blocks) if cursor.hasSelection() else position + inserted
        self._set_selection(new_anchor, new_position)

    def outdent_selection(self) -> None:
        blocks = self._selected_blocks()
        if not blocks:
            return
        cursor = self.textCursor()
        anchor, position = cursor.anchor(), cursor.position()
        intervals: list[tuple[int, int]] = []
        edit = self.textCursor()
        edit.beginEditBlock()
        for block_cursor in blocks:
            text = block_cursor.block().text()
            if text.startswith("\t"):
                count = 1
            else:
                count = len(text) - len(text.lstrip(" "))
                count = min(count, 4)
            if not count:
                continue
            start = block_cursor.block().position()
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.movePosition(
                QTextCursor.MoveOperation.NextCharacter,
                QTextCursor.MoveMode.KeepAnchor,
                count,
            )
            block_cursor.removeSelectedText()
            intervals.append((start, count))
        edit.endEditBlock()
        if not intervals:
            return
        new_anchor = self._shift_position(anchor, intervals)
        new_position = self._shift_position(position, intervals)
        self._set_selection(new_anchor, new_position)

    @staticmethod
    def _shift_position(position: int, removed: list[tuple[int, int]]) -> int:
        shift = 0
        for start, count in removed:
            if position >= start + count:
                shift -= count
            elif position > start:
                return start + shift
        return position + shift

    def _set_selection(self, anchor: int, position: int) -> None:
        limit = max(0, self.document().characterCount() - 1)
        anchor = max(0, min(limit, anchor))
        position = max(0, min(limit, position))
        cursor = QTextCursor(self.document())
        if anchor <= position:
            cursor.setPosition(anchor)
            cursor.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(anchor)
            cursor.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    _LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s+)(.*)$")
    _TASK_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s+)(\[[ xX]\])(\s+)(.*)$")
    _QUOTE_RE = re.compile(r"^(\s{0,3})(>+)(\s?)(.*)$")

    def _continue_markdown_block(self) -> bool:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        block_text = cursor.block().text()
        if cursor.positionInBlock() != len(block_text):
            return False

        task = self._TASK_RE.match(block_text)
        if task:
            indent, marker, spacing, _checkbox, box_space, content = task.groups()
            if not content.strip():
                self._clear_current_line(indent)
                return True
            new_marker = self._next_list_marker(marker)
            cursor.insertText(f"\n{indent}{new_marker}{spacing}[ ]{box_space}")
            self.ensureCursorVisible()
            return True

        item = self._LIST_RE.match(block_text)
        if item:
            indent, marker, spacing, content = item.groups()
            if not content.strip():
                self._clear_current_line(indent)
                return True
            new_marker = self._next_list_marker(marker)
            cursor.insertText(f"\n{indent}{new_marker}{spacing}")
            self.ensureCursorVisible()
            return True

        quote = self._QUOTE_RE.match(block_text)
        if quote:
            indent, markers, space, content = quote.groups()
            if not content.strip():
                self._clear_current_line(indent)
                return True
            cursor.insertText(f"\n{indent}{markers}{space or ' '}")
            self.ensureCursorVisible()
            return True
        return False

    @staticmethod
    def _next_list_marker(marker: str) -> str:
        if marker[-1] in ".)":
            number = marker[:-1]
            if number.isdigit():
                return f"{int(number) + 1}{marker[-1]}"
        return marker

    def _clear_current_line(self, indent: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.insertText(indent)

    # -- formatting helpers ------------------------------------------------
    def wrap_selection(self, prefix: str, suffix: str, placeholder: str) -> None:
        cursor = self.textCursor()
        start = cursor.selectionStart()
        if cursor.hasSelection():
            selected = cursor.selection().toPlainText()
            stripped = selected
            if (
                stripped.startswith(prefix)
                and stripped.endswith(suffix)
                and len(stripped) >= len(prefix) + len(suffix)
            ):
                replacement = stripped[len(prefix) : len(stripped) - len(suffix)]
                cursor.beginEditBlock()
                cursor.insertText(replacement)
                cursor.endEditBlock()
                new_cursor = QTextCursor(self.document())
                new_cursor.setPosition(start)
                new_cursor.setPosition(start + len(replacement), QTextCursor.MoveMode.KeepAnchor)
                self.setTextCursor(new_cursor)
                return

            end = cursor.selectionEnd()
            full_text = self.document().toPlainText()
            surrounded = (
                start >= len(prefix)
                and full_text[:start].endswith(prefix)
                and full_text[end:].startswith(suffix)
            )
            if surrounded and prefix == "*":
                # Do not treat one half of "**" as an italic marker.
                if (
                    full_text[start - 2 : start - 1] == "*"
                    or full_text[end + 1 : end + 2] == "*"
                ):
                    surrounded = False
            if surrounded:
                edit = QTextCursor(self.document())
                edit.beginEditBlock()
                edit.setPosition(start - len(prefix))
                edit.setPosition(end + len(suffix), QTextCursor.MoveMode.KeepAnchor)
                edit.insertText(selected)
                edit.endEditBlock()
                new_cursor = QTextCursor(self.document())
                new_cursor.setPosition(start - len(prefix))
                new_cursor.setPosition(
                    start - len(prefix) + len(selected), QTextCursor.MoveMode.KeepAnchor
                )
                self.setTextCursor(new_cursor)
                return

            replacement = prefix + selected + suffix
            cursor.beginEditBlock()
            cursor.insertText(replacement)
            cursor.endEditBlock()
            new_cursor = QTextCursor(self.document())
            new_cursor.setPosition(start + len(prefix))
            new_cursor.setPosition(start + len(prefix) + len(selected), QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(new_cursor)
            return

        replacement = prefix + placeholder + suffix
        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()
        new_cursor = QTextCursor(self.document())
        new_cursor.setPosition(start + len(prefix))
        new_cursor.setPosition(start + len(prefix) + len(placeholder), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(new_cursor)

    def toggle_inline(self, marker: str, placeholder: str) -> None:
        self.wrap_selection(marker, marker, placeholder)

    def insert_link(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selection().toPlainText()
            start = cursor.selectionStart()
            cursor.beginEditBlock()
            cursor.insertText(f"[{text}](https://)")
            cursor.endEditBlock()
            new_cursor = QTextCursor(self.document())
            new_cursor.setPosition(start + len(text) + 3)
            new_cursor.setPosition(start + len(text) + 11, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(new_cursor)
        else:
            start = cursor.position()
            cursor.beginEditBlock()
            cursor.insertText("[链接文字](https://)")
            cursor.endEditBlock()
            new_cursor = QTextCursor(self.document())
            new_cursor.setPosition(start + 1)
            new_cursor.setPosition(start + 5, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(new_cursor)

    def insert_image(self) -> None:
        cursor = self.textCursor()
        start = cursor.position()
        cursor.insertText("![图片说明](images/picture.png)")
        new_cursor = QTextCursor(self.document())
        new_cursor.setPosition(start + 2)
        new_cursor.setPosition(start + 6, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(new_cursor)

    def insert_code_block(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selection().toPlainText()
            start = cursor.selectionStart()
            cursor.beginEditBlock()
            cursor.insertText(f"```\n{text}\n```")
            cursor.endEditBlock()
            new_cursor = QTextCursor(self.document())
            new_cursor.setPosition(start + 4)
            new_cursor.setPosition(start + 4 + len(text), QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(new_cursor)
            return
        start = cursor.position()
        cursor.insertText("```\n\n```")
        new_cursor = QTextCursor(self.document())
        new_cursor.setPosition(start + 4)
        self.setTextCursor(new_cursor)

    def insert_block(self, text: str) -> None:
        cursor = self.textCursor()
        block = cursor.block()
        if block.text().strip():
            prefix = "\n\n"
        else:
            prefix = ""
        if cursor.positionInBlock() != len(block.text()):
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText(prefix + text)
        self.setTextCursor(cursor)

    def apply_heading(self, level: int) -> None:
        blocks = self._selected_blocks()
        edit = self.textCursor()
        edit.beginEditBlock()
        for block_cursor in blocks:
            text = block_cursor.block().text()
            new_text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text)
            if level > 0:
                new_text = "#" * level + " " + new_text
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            block_cursor.insertText(new_text)
        edit.endEditBlock()

    def toggle_line_prefix(self, prefix: str) -> None:
        blocks = self._selected_blocks()
        if not blocks:
            return
        present = all(
            b.block().text().lstrip().startswith(prefix)
            for b in blocks
            if b.block().text().strip()
        )
        edit = self.textCursor()
        edit.beginEditBlock()
        for block_cursor in blocks:
            text = block_cursor.block().text()
            indent = text[: len(text) - len(text.lstrip())]
            body = text.lstrip()
            if present and body.startswith(prefix):
                body = body[len(prefix) :]
            elif not present:
                body = prefix + body
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            block_cursor.insertText(indent + body)
        edit.endEditBlock()

    def toggle_task_list(self) -> None:
        blocks = self._selected_blocks()
        if not blocks:
            return
        task_prefix = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\]\s+")
        all_tasks = all(
            task_prefix.match(b.block().text()) for b in blocks if b.block().text().strip()
        )
        edit = self.textCursor()
        edit.beginEditBlock()
        for block_cursor in blocks:
            text = block_cursor.block().text()
            if all_tasks:
                new_text = task_prefix.sub("", text)
            else:
                indent = text[: len(text) - len(text.lstrip())]
                body = text.lstrip()
                marker = re.match(r"^(?:[-*+]|\d+[.)])\s+", body)
                if marker:
                    body = body[marker.end() :]
                new_text = f"{indent}- [ ] {body}"
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            block_cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            block_cursor.insertText(new_text)
        edit.endEditBlock()

    def insert_table(self) -> None:
        text = (
            "| 列 1 | 列 2 | 列 3 |\n"
            "| --- | --- | --- |\n"
            "| 内容 | 内容 | 内容 |\n"
            "| 内容 | 内容 | 内容 |"
        )
        self.insert_block(text)

    def insert_horizontal_rule(self) -> None:
        self.insert_block("---")

    def insert_date(self) -> None:
        self.insert_block(_dt.date.today().strftime("%Y-%m-%d"))

    # -- drag & drop -------------------------------------------------------
    @staticmethod
    def _dropped_file(event) -> str | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if url.isLocalFile():
                return url.toLocalFile()
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._dropped_file(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._dropped_file(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        path = self._dropped_file(event)
        if path:
            event.acceptProposedAction()
            self.fileDropped.emit(path)
            return
        super().dropEvent(event)
