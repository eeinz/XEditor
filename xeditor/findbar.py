"""Inline find / replace bar for the Markdown editor."""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QRegularExpression, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .themes import Theme


class FindBar(QWidget):
    closed = Signal()

    MAX_MATCHES = 5000

    def __init__(self, editor, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("FindBar")
        self.editor = editor
        self._theme = theme
        self._matches: list[QTextCursor] = []
        self._index = -1
        self._dirty = True
        self._replace_mode = False

        self._build_ui()
        self._connect()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(160)
        self._refresh_timer.timeout.connect(self._refresh_live)
        self.hide()

    # -- UI ----------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(6)

        find_row = QHBoxLayout()
        find_row.setSpacing(5)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("查找内容")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMinimumWidth(180)
        find_row.addWidget(self.find_edit, 1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("FindStatus")
        self.count_label.setMinimumWidth(92)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        find_row.addWidget(self.count_label)

        self.case_btn = self._tool_button("Aa", "区分大小写", checkable=True)
        self.word_btn = self._tool_button("词", "全词匹配", checkable=True)
        self.regex_btn = self._tool_button(".*", "使用正则表达式", checkable=True)
        find_row.addWidget(self.case_btn)
        find_row.addWidget(self.word_btn)
        find_row.addWidget(self.regex_btn)

        self.prev_btn = self._tool_button("↑", "上一个匹配 (Shift+Enter)")
        self.next_btn = self._tool_button("↓", "下一个匹配 (Enter)")
        find_row.addWidget(self.prev_btn)
        find_row.addWidget(self.next_btn)

        self.close_btn = self._tool_button("✕", "关闭 (Esc)")
        find_row.addWidget(self.close_btn)
        layout.addLayout(find_row)

        replace_row = QHBoxLayout()
        replace_row.setSpacing(5)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("替换为")
        self.replace_edit.setClearButtonEnabled(True)
        replace_row.addWidget(self.replace_edit, 1)
        self.replace_btn = QPushButton("替换")
        self.replace_btn.setToolTip("替换当前匹配")
        self.replace_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.replace_btn.setAutoDefault(False)
        replace_row.addWidget(self.replace_btn)
        self.replace_all_btn = QPushButton("全部替换")
        self.replace_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.replace_all_btn.setAutoDefault(False)
        replace_row.addWidget(self.replace_all_btn)
        layout.addLayout(replace_row)
        self._replace_widgets = (self.replace_edit, self.replace_btn, self.replace_all_btn)
        self._set_replace_visible(False)

    def _tool_button(self, text: str, tip: str, checkable: bool = False) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tip)
        button.setCheckable(checkable)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    # -- events ------------------------------------------------------------
    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close_bar()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and watched is self.find_edit:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.find_previous()
                else:
                    self.find_next()
                return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.close_bar()
        event.ignore()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
            return
        super().keyPressEvent(event)

    # -- public API ---------------------------------------------------------
    def open_find(self) -> None:
        self.open(find_only=True)

    def open_replace(self) -> None:
        self.open(find_only=False)

    def open(self, find_only: bool) -> None:
        self._replace_mode = not find_only
        self._set_replace_visible(not find_only)
        selected = self.editor.textCursor().selection().toPlainText()
        if selected and "\n" not in selected and len(selected) < 300:
            self.find_edit.setText(selected)
        self.show()
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self._refresh(select_first=True)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self.isVisible():
            self._update_highlights()

    def close_bar(self) -> None:
        if not self.isVisible():
            return
        self.hide()
        self._matches.clear()
        self._index = -1
        self._dirty = True
        self.editor.set_search_selections([])
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self.closed.emit()

    # -- actions -----------------------------------------------------------
    def find_next(self) -> None:
        if self._dirty:
            self._refresh()
        self._advance(1)

    def find_previous(self) -> None:
        if self._dirty:
            self._refresh()
        self._advance(-1)

    def _advance(self, step: int) -> None:
        if not self._matches:
            return
        self._sync_index()
        if self._index < 0:
            cursor = self.editor.textCursor()
            position = cursor.selectionStart()
            if step > 0:
                index = 0
                for i, match in enumerate(self._matches):
                    if match.selectionStart() >= position:
                        index = i
                        break
            else:
                index = len(self._matches) - 1
                for i in range(len(self._matches) - 1, -1, -1):
                    if self._matches[i].selectionStart() < position:
                        index = i
                        break
            self._jump_to(index)
            return
        self._index = (self._index + step) % len(self._matches)
        self._jump_to(self._index)

    def _sync_index(self) -> None:
        cursor = self.editor.textCursor()
        current_start = cursor.selectionStart()
        for i, match in enumerate(self._matches):
            if match.selectionStart() <= current_start <= match.selectionEnd():
                self._index = i
                return
        self._index = -1

    def _jump_to(self, index: int) -> None:
        if not (0 <= index < len(self._matches)):
            return
        self._index = index
        self.editor.setTextCursor(self._matches[index])
        self.editor.centerCursor()
        self.count_label.setText(f"{index + 1} / {len(self._matches)}")

    def _refresh_live(self) -> None:
        if self.isVisible():
            self._refresh(select_first=False)

    # -- search ------------------------------------------------------------
    def _flags(self) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self.case_btn.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.word_btn.isChecked() and not self.regex_btn.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        return flags

    def _query(self) -> str:
        return self.find_edit.text()

    def _pattern(self) -> re.Pattern | None:
        query = self._query()
        if not query:
            return None
        flags = 0 if self.case_btn.isChecked() else re.IGNORECASE
        try:
            if self.regex_btn.isChecked():
                pattern = query
            else:
                pattern = re.escape(query)
            if self.word_btn.isChecked():
                pattern = rf"\b(?:{pattern})\b"
            return re.compile(pattern, flags)
        except re.error:
            return None

    def _collect_matches(self) -> list[QTextCursor]:
        query = self._query()
        if not query:
            return []
        doc = self.editor.document()
        matches: list[QTextCursor] = []
        if self.regex_btn.isChecked():
            pattern = self._pattern()
            if pattern is None:
                return []
            text = query
            if self.word_btn.isChecked():
                text = rf"\b(?:{text})\b"
            options = QRegularExpression.PatternOption.NoPatternOption
            if not self.case_btn.isChecked():
                options |= QRegularExpression.PatternOption.CaseInsensitiveOption
            regular_expression = QRegularExpression(text, options)
            if not regular_expression.isValid():
                return []
            iterator = regular_expression.globalMatch(doc.toPlainText())
            while iterator.hasNext():
                match = iterator.next()
                start, end = match.capturedStart(0), match.capturedEnd(0)
                if start < 0 or start == end:
                    continue
                cursor = QTextCursor(doc)
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                matches.append(cursor)
                if len(matches) >= self.MAX_MATCHES:
                    break
            return matches

        flags = self._flags()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        while len(matches) < self.MAX_MATCHES:
            found = doc.find(query, cursor, flags)
            if found.isNull():
                break
            matches.append(found)
            cursor.setPosition(found.selectionEnd())
            if found.selectionStart() == found.selectionEnd():
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
        return matches

    def _refresh(self, select_first: bool = False) -> None:
        query = self._query()
        if not query:
            self._matches = []
            self._index = -1
            self._dirty = False
            self.count_label.setText("")
            self._set_error(False)
            self.editor.set_search_selections([])
            return

        pattern = self._pattern()
        if pattern is None:
            self._matches = []
            self._index = -1
            self._dirty = False
            self.count_label.setText("无效")
            self._set_error(True)
            self.editor.set_search_selections([])
            return

        self._set_error(False)
        self._matches = self._collect_matches()
        self._index = -1
        self._dirty = False
        if not self._matches:
            self.count_label.setText("无结果")
        elif select_first:
            self.count_label.setText(f"0 / {len(self._matches)}")
        else:
            self._sync_index()
            if self._index >= 0:
                self.count_label.setText(f"{self._index + 1} / {len(self._matches)}")
            else:
                self.count_label.setText(f"{len(self._matches)} 个匹配")
        self._update_highlights()

        if select_first and self._matches:
            cursor = self.editor.textCursor()
            start = cursor.selectionStart()
            index = 0
            for i, match in enumerate(self._matches):
                if match.selectionStart() >= start:
                    index = i
                    break
            self._jump_to(index)

    def _set_error(self, error: bool) -> None:
        if self.find_edit.property("error") == error:
            return
        self.find_edit.setProperty("error", error)
        self.find_edit.style().unpolish(self.find_edit)
        self.find_edit.style().polish(self.find_edit)

    def _update_highlights(self) -> None:
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(self._theme.mark_bg))
        fmt.setForeground(QColor(self._theme.text))
        selections = []
        for match in self._matches[:2000]:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = match
            selection.format = fmt
            selections.append(selection)
        self.editor.set_search_selections(selections)

    # -- replace -----------------------------------------------------------
    def replace_current(self) -> None:
        if self._dirty:
            self._refresh()
        if not self._matches:
            return
        self._sync_index()
        cursor = self.editor.textCursor()
        index = -1
        for i, match in enumerate(self._matches):
            if match.selectionStart() == cursor.selectionStart() and match.selectionEnd() == cursor.selectionEnd():
                index = i
                break
        if index < 0:
            self._jump_to(max(0, self._index))
            return

        replacement = self.replace_edit.text()
        selected = cursor.selection().toPlainText()
        if self.regex_btn.isChecked():
            pattern = self._pattern()
            if pattern is not None:
                try:
                    replacement = pattern.sub(replacement, selected, count=1)
                except re.error:
                    replacement = self.replace_edit.text()
        edit = self.editor.textCursor()
        edit.beginEditBlock()
        edit.insertText(replacement)
        edit.endEditBlock()

        position = edit.position()
        self._refresh(select_first=False)
        self._dirty = False
        index = 0
        for i, match in enumerate(self._matches):
            if match.selectionStart() >= position:
                index = i
                break
        else:
            if self._matches:
                index = 0
        if self._matches:
            self._jump_to(index)

    def replace_all(self) -> None:
        query = self._query()
        if not query:
            return
        pattern = self._pattern()
        if pattern is None:
            self._set_error(True)
            self.count_label.setText("无效")
            return

        text = self.editor.toPlainText()
        replacement = self.replace_edit.text()
        try:
            if self.regex_btn.isChecked():
                new_text, count = pattern.subn(replacement, text)
            else:
                new_text, count = pattern.subn(lambda _m: replacement, text)
        except re.error:
            self._set_error(True)
            return

        if count == 0:
            self.count_label.setText("无结果")
            return

        edit = QTextCursor(self.editor.document())
        edit.beginEditBlock()
        edit.select(QTextCursor.SelectionType.Document)
        edit.insertText(new_text)
        edit.endEditBlock()
        self.editor.setTextCursor(edit)
        self.editor.document().setModified(True)
        self._refresh(select_first=False)
        self.count_label.setText(f"已替换 {count} 处")

    # -- connections -------------------------------------------------------
    def _connect(self) -> None:
        self.find_edit.textChanged.connect(self._on_query_changed)
        self.find_edit.installEventFilter(self)
        self.replace_edit.installEventFilter(self)
        self.find_edit.returnPressed.connect(self.find_next)
        self.replace_edit.returnPressed.connect(self.replace_current)
        self.next_btn.clicked.connect(self.find_next)
        self.prev_btn.clicked.connect(self.find_previous)
        self.close_btn.clicked.connect(self.close_bar)
        self.replace_btn.clicked.connect(self.replace_current)
        self.replace_all_btn.clicked.connect(self.replace_all)
        self.case_btn.toggled.connect(self._on_option_changed)
        self.word_btn.toggled.connect(self._on_option_changed)
        self.regex_btn.toggled.connect(self._on_option_changed)
        self.editor.textChanged.connect(self._on_editor_changed)
        self.editor.cursorPositionChanged.connect(self._on_editor_cursor_changed)

    def _on_query_changed(self, _text: str) -> None:
        self._dirty = True
        self._refresh_timer.start()
        self._set_error(False)

    def _on_option_changed(self, _checked: bool) -> None:
        self._dirty = True
        self._refresh(select_first=True)

    def _on_editor_changed(self) -> None:
        if self.isVisible():
            self._dirty = True
            self._refresh_timer.start()

    def _on_editor_cursor_changed(self) -> None:
        if self.isVisible() and not self._dirty:
            self._sync_index()
            if self._matches and self._index >= 0:
                self.count_label.setText(f"{self._index + 1} / {len(self._matches)}")

    def _set_replace_visible(self, visible: bool) -> None:
        for widget in self._replace_widgets:
            widget.setVisible(visible)
