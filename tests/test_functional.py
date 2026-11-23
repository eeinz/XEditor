"""End-to-end functional tests for XEditor.

Run from the project root:

    python tests/test_functional.py

The test runs with the Qt "offscreen" platform by default, so it does not
open windows or require a display server.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QFontDialog

TMP_ROOT = Path(tempfile.mkdtemp(prefix="xeditor-test-"))
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(TMP_ROOT / "settings"))
QSettings("XEditor", "XEditor").clear()

from xeditor.app import create_app
from xeditor.main_window import MainWindow
from xeditor.renderer import render_document
from xeditor.themes import LIGHT

app = create_app([])
work = TMP_ROOT / "output"
work.mkdir(exist_ok=True)


def wait(ms=150):
    QTest.qWait(ms)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS:", message)


def all_outline_items(window):
    def walk(item):
        count = 1
        for i in range(item.childCount()):
            count += walk(item.child(i))
        return count

    tree = window.outline_panel.tree
    return sum(walk(tree.topLevelItem(i)) for i in range(tree.topLevelItemCount()))


def run():
    window = MainWindow()
    window.resize(1280, 860)
    window.show()
    wait(250)

    try:
        # -- startup -----------------------------------------------------
        check(window.outline_dock.isVisible(), "outline visible at startup")
        check(window.outline_action.isChecked(), "outline action checked")
        check(window.preview.isVisible(), "preview visible")
        check(window.encoding_label.text() == "UTF-8", "welcome encoding is UTF-8")
        check(window.editor.blockCount() > 10, "welcome document loaded")
        check(window.autosave_action.isChecked(), "auto-save enabled by default")
        window.autosave_action.setChecked(False)

        # -- open demo ---------------------------------------------------
        sample = ROOT / "samples" / "demo.md"
        check(window.open_path(str(sample)), "open demo file")
        wait(500)
        check(window._current_path == sample, "current path recorded")
        check("demo.md" in window.windowTitle() and "*" not in window.windowTitle(), "clean title after open")
        check(window.encoding_label.text() == "UTF-8", "demo file has no false BOM label")
        check(all_outline_items(window) >= 7, f"outline populated ({all_outline_items(window)} items)")
        check("实时预览" in window.editor.toPlainText(), "sample content loaded")

        rendered = render_document(sample.read_text(encoding="utf-8"), LIGHT, str(sample.parent), max_image_width=560)
        check("list-style-type: none" in rendered.body, "task list bullets removed")
        check("xeditor.png" in rendered.body and 'width="140"' in rendered.body, "image tag with explicit width")
        check('<td style="background-color:' in rendered.body, "code block panel rendered")
        check("id=" in rendered.body, "heading anchors generated")
        embedded = render_document(
            sample.read_text(encoding="utf-8"),
            LIGHT,
            str(sample.parent),
            embed_images=True,
        )
        check("data:image/png;base64," in embedded.html, "standalone HTML embeds images")

        unsafe_source = (
            "裸链接 https://example.com/a?x=1&y=2，以及 www.example.org。\n\n"
            "`https://inside.code`\n\n"
            "<script>alert('xss')</script>\n"
            "<iframe src=\"https://evil.example\"></iframe>\n"
            "<embed src=\"evil.swf\">after-embed\n"
            "<a href=\"javascript:alert(1)\" onclick=\"evil()\">bad</a>\n"
            "<img src=\"x.png\" onerror=\"alert(1)\" alt=\"x\">\n"
            "<div style=\"position:fixed; z-index:9; color: red;\">styled</div>\n"
        )
        sanitized = render_document(unsafe_source, LIGHT).body
        check("<script" not in sanitized and "iframe" not in sanitized, "dangerous HTML removed")
        check("after-embed" in sanitized, "void dangerous tag does not swallow following content")
        check("onerror=" not in sanitized and "onclick=" not in sanitized, "event handlers removed")
        check("javascript:" not in sanitized, "javascript URLs removed")
        check('href="https://example.com/a?x=1&amp;y=2"' in sanitized, "bare URL auto-linked")
        check('href="http://www.example.org"' in sanitized, "www URL auto-linked")
        check("<code>https://inside.code</code>" in sanitized and 'href="https://inside.code"' not in sanitized, "code spans not auto-linked")
        check('<div style="color: red">styled</div>' in sanitized, "safe inline styles preserved")
        highlighted = render_document("高亮 ==重点== 和 `==代码==`\n", LIGHT).body
        check("background-color:" in highlighted and ">重点</span>" in highlighted, "highlight syntax rendered")
        check("<code>==代码==</code>" in highlighted, "highlight inside code untouched")

        # -- theme -------------------------------------------------------
        window._apply_theme("dark")
        wait(300)
        check(window._theme.key == "dark", "dark theme applied")
        check(window.outline_dock.isVisible(), "outline stays visible after theme switch")
        check(window.outline_action.isChecked(), "outline action stays checked after theme switch")
        window._apply_theme("light")
        wait(250)
        check(window._theme.key == "light", "light theme applied")
        check(window.outline_dock.isVisible(), "outline stays visible after switching back")

        # -- outline dock close / reopen ---------------------------------
        window.outline_dock.close()
        wait(100)
        check(not window.outline_action.isChecked(), "closing dock unchecks outline action")
        check(not window.settings.bool("view/outline_visible"), "closing dock persists hidden state")
        window.outline_action.trigger()
        wait(100)
        check(window.outline_dock.isVisible(), "outline action reopens dock")
        check(window.outline_action.isChecked(), "outline action checked again")

        # -- word wrap / zoom --------------------------------------------
        window.wrap_action.setChecked(False)
        check(
            window.editor.lineWrapMode() == window.editor.LineWrapMode.NoWrap,
            "word wrap off",
        )
        window.wrap_action.setChecked(True)
        check(
            window.editor.lineWrapMode() == window.editor.LineWrapMode.WidgetWidth,
            "word wrap on",
        )
        old_size = window.editor.font().pointSize()
        window.zoom_in_action.trigger()
        check(window.editor.font().pointSize() == old_size + 1, "editor zoom in")
        window.zoom_reset_action.trigger()
        check(window.editor.font().pointSize() == 11, "editor zoom reset")
        window.preview.set_zoom_steps(0)
        window.preview.zoom_by(2)
        check(window.preview._zoom_steps == 2, "preview zoom steps")
        window.preview.reset_zoom()
        check(window.preview._zoom_steps == 0, "preview zoom reset")
        with patch.object(
            QFontDialog, "getFont", return_value=(True, QFont("Consolas", 12))
        ):
            window._choose_font()
        check(window.editor.font().pointSize() == 12, "font dialog applies editor font")
        window.zoom_reset_action.trigger()

        # -- find --------------------------------------------------------
        window.editor.setPlainText("alpha beta Alpha gamma alpha\nline two alpha")
        window.editor.document().setModified(False)
        wait(250)
        bar = window.find_bar
        bar.open_replace()
        bar.find_edit.setText("alpha")
        bar._refresh(select_first=True)
        check(len(bar._matches) == 4, "find case-insensitive match count")
        check(bar.count_label.text() == "1 / 4", "find current index label")
        check(window.editor.textCursor().selectedText().lower() == "alpha", "find jumps to a match")
        bar.case_btn.setChecked(True)
        check(len(bar._matches) == 3, "find case-sensitive match count")
        bar.word_btn.setChecked(True)
        check(len(bar._matches) == 3, "find whole-word match count")
        bar.case_btn.setChecked(False)
        bar.word_btn.setChecked(False)
        bar.regex_btn.setChecked(True)
        bar.find_edit.setText(r"a\w+")
        wait(250)
        check(len(bar._matches) >= 3, "regex find works")
        bar.find_edit.setText("[")
        bar._refresh()
        check(bar.count_label.text() == "无效", "invalid regex flagged")
        bar.regex_btn.setChecked(False)
        bar.case_btn.setChecked(False)
        bar.find_edit.setText("alpha")
        bar._refresh(select_first=True)
        bar.replace_edit.setText("X")
        bar.replace_current()
        check(window.editor.toPlainText().startswith("X beta"), "replace current works")
        bar.close_bar()

        # -- replace all / regex replace --------------------------------
        window.editor.setPlainText("one two one ONE one")
        bar.open_replace()
        bar.find_edit.setText("one")
        bar.replace_edit.setText("1")
        bar._refresh()
        bar.replace_all()
        wait(100)
        check(window.editor.toPlainText() == "1 two 1 1 1", "replace all works case-insensitively")
        check("已替换 4 处" in bar.count_label.text(), "replace all count shown")

        window.editor.setPlainText("a1 b2 c3")
        bar.regex_btn.setChecked(True)
        bar.find_edit.setText(r"([a-z])(\d)")
        bar.replace_edit.setText(r"\2\1")
        bar._refresh()
        bar.replace_all()
        wait(100)
        check(window.editor.toPlainText() == "1a 2b 3c", "regex groups in replace all")
        bar.close_bar()

        # -- formatting --------------------------------------------------
        window.editor.setPlainText("hello")
        window.editor.selectAll()
        window.bold_action.trigger()
        check(window.editor.toPlainText() == "**hello**", "bold wraps selection")
        window.bold_action.trigger()
        check(window.editor.toPlainText() == "hello", "bold toggles off")
        window.editor.selectAll()
        window.italic_action.trigger()
        check(window.editor.toPlainText() == "*hello*", "italic works")
        window.editor.setPlainText("Title")
        window.editor.moveCursor(window.editor.textCursor().MoveOperation.End)
        window.heading_actions[1].trigger()
        check(window.editor.toPlainText() == "## Title", "heading action works")
        window.clear_heading_action.trigger()
        check(window.editor.toPlainText() == "Title", "clear heading works")
        window.editor.setPlainText("Task")
        window.editor.selectAll()
        window.task_action.trigger()
        check(window.editor.toPlainText() == "- [ ] Task", "task list action works")
        window.editor.setPlainText("x = 1")
        window.editor.selectAll()
        window.code_block_action.trigger()
        check(window.editor.toPlainText() == "```\nx = 1\n```", "code block wraps selection")
        window.editor.setPlainText("")
        window.table_action.trigger()
        check("| 列 1 |" in window.editor.toPlainText(), "table insertion works")

        # -- auto list continuation / indentation ----------------------
        window.editor.setPlainText("- item")
        window.editor.moveCursor(window.editor.textCursor().MoveOperation.End)
        QTest.keyClick(window.editor, Qt.Key.Key_Return)
        check(window.editor.toPlainText() == "- item\n- ", "unordered list continues")
        QTest.keyClick(window.editor, Qt.Key.Key_Return)
        check(window.editor.toPlainText() == "- item\n", "empty list item exits list")

        window.editor.setPlainText("1. first")
        window.editor.moveCursor(window.editor.textCursor().MoveOperation.End)
        QTest.keyClick(window.editor, Qt.Key.Key_Return)
        check(window.editor.toPlainText() == "1. first\n2. ", "ordered list increments")

        window.editor.setPlainText("- [x] done")
        window.editor.moveCursor(window.editor.textCursor().MoveOperation.End)
        QTest.keyClick(window.editor, Qt.Key.Key_Return)
        check(window.editor.toPlainText() == "- [x] done\n- [ ] ", "task list continues")

        window.editor.setPlainText("> quote")
        window.editor.moveCursor(window.editor.textCursor().MoveOperation.End)
        QTest.keyClick(window.editor, Qt.Key.Key_Return)
        check(window.editor.toPlainText() == "> quote\n> ", "blockquote continues")

        window.editor.setPlainText("abc")
        window.editor.moveCursor(window.editor.textCursor().MoveOperation.Start)
        QTest.keyClick(window.editor, Qt.Key.Key_Tab)
        check(window.editor.toPlainText() == "    abc", "tab inserts spaces")
        window.editor.outdent_selection()
        check(window.editor.toPlainText() == "abc", "shift-tab outdents")

        window.editor.setPlainText("a\nb")
        window.editor.selectAll()
        window.editor.indent_selection()
        check(window.editor.toPlainText() == "    a\n    b", "indent selected lines")

        # -- word / char counts -----------------------------------------
        window.editor.setPlainText("中文 test 123")
        with patch.object(window.editor, "textCursor", wraps=window.editor.textCursor):
            window._update_stats()
        check("4" in window.counts_label.text(), f"word count handles CJK + latin ({window.counts_label.text()})")

        # -- save / reopen / encodings ---------------------------------
        doc_path = work / "saved.md"
        window.editor.setPlainText("你好\nsecond line\n")
        window._encoding = "utf-8"
        window._newline = "\r\n"
        window.editor.document().setModified(True)
        check(window._write_to(doc_path), "write UTF-8 with CRLF")
        data = doc_path.read_bytes()
        check(b"\r\n" in data and data.startswith("你好".encode("utf-8")), "CRLF and UTF-8 bytes on disk")
        check(not window.editor.document().isModified(), "document clean after save")
        check(window._current_path == doc_path, "path updated after save")
        check(str(doc_path) in window.settings.recent_files(), "file added to recent list")
        window.editor.document().setModified(False)
        check(window.open_path(str(doc_path)), "reopen saved file")
        check(window._newline == "\r\n", "CRLF style detected on open")
        check(window.editor.toPlainText() == "你好\nsecond line\n", "content preserved after reopen")

        # -- auto save ---------------------------------------------------
        window.autosave_action.setChecked(True)
        window.editor.moveCursor(window.editor.textCursor().MoveOperation.End)
        window.editor.insertPlainText("自动保存")
        wait(2600)
        saved_text = doc_path.read_bytes().decode("utf-8")
        check("自动保存" in saved_text, "auto-save writes existing file")
        check(not window.editor.document().isModified(), "document clean after auto-save")
        window.autosave_action.setChecked(False)
        window.editor.insertPlainText("MANUAL-ONLY")
        window._autosave()
        check("MANUAL-ONLY" not in doc_path.read_bytes().decode("utf-8"), "auto-save toggle respected")
        window.editor.document().setModified(False)

        bom_path = work / "bom.md"
        bom_path.write_bytes(b"\xef\xbb\xbf" + "# BOM 文档\n".encode("utf-8"))
        window.editor.document().setModified(False)
        check(window.open_path(str(bom_path)), "open BOM file")
        check(window.encoding_label.text() == "UTF-8 BOM", "BOM encoding detected")
        check(window._write_to(bom_path), "save BOM file")
        check(bom_path.read_bytes().startswith(b"\xef\xbb\xbf"), "BOM preserved on save")

        gbk_path = work / "gbk.md"
        gbk_path.write_bytes("# 中文编码\n".encode("gb18030"))
        window.editor.document().setModified(False)
        check(window.open_path(str(gbk_path)), "open GB18030 file")
        check(window.encoding_label.text() == "GB18030", "GB18030 detected")
        check(window.editor.toPlainText() == "# 中文编码\n", "GB18030 text decoded")

        # -- export HTML / PDF ------------------------------------------
        window.editor.document().setModified(False)
        html_path = work / "export.html"
        pdf_path = work / "export.pdf"
        window._show_export_result = lambda path, title: None
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(html_path), "")):
            window._export_html()
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(pdf_path), "")):
            window._export_pdf()
        check(html_path.exists() and "<style>" in html_path.read_text(encoding="utf-8"), "HTML exported")
        check(pdf_path.exists() and pdf_path.stat().st_size > 1000, "PDF exported")
        check(pdf_path.read_bytes().startswith(b"%PDF"), "PDF has valid header")

        # -- reading mode -------------------------------------------------
        window._set_reading_mode(True)
        wait(120)
        check(not window.editor_container.isVisible(), "reading mode hides editor")
        check(not window.toolbar.isVisible(), "reading mode hides toolbar")
        check(window.preview.isVisible(), "reading mode shows preview")
        window._set_reading_mode(False)
        wait(120)
        check(window.editor_container.isVisible(), "reading mode restores editor")
        check(window.toolbar.isVisible(), "reading mode restores toolbar")

        # -- outline jump --------------------------------------------------
        window.open_path(str(sample))
        wait(300)
        first_heading = None
        tree = window.outline_panel.tree
        stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        while stack:
            item = stack.pop(0)
            line = item.data(0, Qt.ItemDataRole.UserRole)
            if line and line > 0:
                first_heading = item
                break
            stack.extend(item.child(i) for i in range(item.childCount()))
        check(first_heading is not None, "outline item found")
        window.outline_panel.headingActivated.emit(
            int(first_heading.data(0, Qt.ItemDataRole.UserRole)),
            str(first_heading.data(0, Qt.ItemDataRole.UserRole + 1) or ""),
        )
        wait(100)
        check(window.editor.textCursor().blockNumber() > 0, "outline jump moves editor cursor")

        # -- scroll sync ------------------------------------------------
        window.sync_action.setChecked(True)
        bar = window.editor.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        wait(120)
        editor_ratio = bar.value() / max(1, bar.maximum())
        check(
            abs(window.preview.scroll_ratio() - editor_ratio) < 0.08,
            "editor scroll syncs preview",
        )
        window.sync_action.setChecked(False)
        frozen = window.preview.scroll_ratio()
        bar.setValue(0)
        wait(120)
        check(abs(window.preview.scroll_ratio() - frozen) < 0.02, "sync off keeps preview position")
        window.sync_action.setChecked(True)

        # -- close ---------------------------------------------------------
        window.editor.document().setModified(False)
        window.close()
        wait(100)
        check(not window.isVisible(), "window closes cleanly")
        print("ALL FUNCTIONAL TESTS PASSED")
    except Exception:
        traceback.print_exc()
        window.editor.document().setModified(False)
        window.close()
        raise
    finally:
        app.quit()


if __name__ == "__main__":
    print(f"Test workspace: {TMP_ROOT}")
    run()
