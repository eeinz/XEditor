"""Markdown syntax highlighting for QPlainTextEdit."""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from .themes import Theme

_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^(\s{0,3})(#{1,6})(\s+.*)?$")
_SETEXT_RE = re.compile(r"^\s{0,3}(=+|-{3,})\s*$")
_HR_RE = re.compile(r"^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$")
_QUOTE_RE = re.compile(r"^(\s{0,3})(>+)(\s?)")
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s+)")
_TASK_RE = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+)([☐☑])")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")

_BOLD_RES = (
    re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"),
    re.compile(r"(?<![\w_])__(?=\S)(.+?)(?<=\S)__(?![\w_])"),
)
_ITALIC_RES = (
    re.compile(r"(?<!\*)\*(?!\*)(?=\S)([^*\n]+?)(?<=\S)\*(?!\*)"),
    re.compile(r"(?<![\w_])_(?!_)(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])"),
)
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_INLINE_CODE_RE = re.compile(r"(`+)([^`\n]+?)\1(?!`)")
_LINK_RE = re.compile(r"(!?)\[([^\]\n]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_AUTOLINK_RE = re.compile(r"<(https?://[^>\s]+)>")
_TASK_BOX_RE = re.compile(r"[☐☑]")


class MarkdownHighlighter(QSyntaxHighlighter):
    """A lightweight, single-pass Markdown highlighter."""

    FENCE_BACKTICK = 1
    FENCE_TILDE = 2

    def __init__(self, document: QTextDocument, theme: Theme, mono_family: str) -> None:
        super().__init__(document)
        self._theme = theme
        self._mono = mono_family
        self._build_formats()

    # ------------------------------------------------------------------
    def _fmt(
        self,
        color: str | None = None,
        *,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strike: bool = False,
        background: str | None = None,
        mono: bool = False,
    ) -> QTextCharFormat:
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(QColor(color))
        if background:
            fmt.setBackground(QColor(background))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        else:
            fmt.setFontWeight(QFont.Weight.Normal)
        fmt.setFontItalic(italic)
        fmt.setFontUnderline(underline)
        fmt.setFontStrikeOut(strike)
        if mono:
            fmt.setFontFamilies([self._mono])
        return fmt

    def _build_formats(self) -> None:
        t = self._theme
        self.f_heading = self._fmt(t.heading, bold=True)
        self.f_heading_small = self._fmt(t.heading, bold=False)
        self.f_bold = self._fmt(t.text, bold=True)
        self.f_italic = self._fmt(t.text, italic=True)
        self.f_strike = self._fmt(t.muted, strike=True)
        self.f_code_inline = self._fmt(
            t.code_text, mono=True, background=t.code_bg
        )
        self.f_code_block = self._fmt(t.code_text, mono=True, background=t.code_bg)
        self.f_fence = self._fmt(t.muted, mono=True)
        self.f_quote = self._fmt(t.quote, italic=True)
        self.f_quote_mark = self._fmt(t.accent, bold=True)
        self.f_list = self._fmt(t.accent, bold=True)
        self.f_hr = self._fmt(t.muted, bold=True)
        self.f_link = self._fmt(t.link, underline=True)
        self.f_url = self._fmt(t.muted, underline=True)
        self.f_image = self._fmt(t.accent, bold=True)
        self.f_autolink = self._fmt(t.link, underline=True)
        self.f_table = self._fmt(t.muted)
        self.f_task = self._fmt(t.accent, bold=True)

    def set_theme(self, theme: Theme, mono_family: str | None = None) -> None:
        self._theme = theme
        if mono_family:
            self._mono = mono_family
        self._build_formats()
        self.rehighlight()

    # ------------------------------------------------------------------
    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        previous = self.previousBlockState()
        stripped = text.lstrip()

        if previous in (self.FENCE_BACKTICK, self.FENCE_TILDE):
            marker = "```" if previous == self.FENCE_BACKTICK else "~~~"
            if stripped.startswith(marker):
                self.setFormat(0, len(text), self.f_fence)
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), self.f_code_block)
                self.setCurrentBlockState(previous)
            return

        fence = _FENCE_RE.match(text)
        if fence:
            self.setFormat(0, len(text), self.f_fence)
            self.setCurrentBlockState(
                self.FENCE_BACKTICK if fence.group(1)[0] == "`" else self.FENCE_TILDE
            )
            return

        self.setCurrentBlockState(0)

        heading = _HEADING_RE.match(text)
        if heading:
            level = len(heading.group(2))
            self.setFormat(
                0,
                len(text),
                self.f_heading if level <= 2 else self.f_heading_small,
            )
        elif _SETEXT_RE.match(text) and text.strip():
            self.setFormat(0, len(text), self.f_hr)
        elif _HR_RE.match(text):
            self.setFormat(0, len(text), self.f_hr)
        elif _TABLE_RE.match(text):
            self.setFormat(0, len(text), self.f_table)

        quote = _QUOTE_RE.match(text)
        if quote:
            self.setFormat(0, len(text), self.f_quote)
            self.setFormat(
                len(quote.group(1)), len(quote.group(2)), self.f_quote_mark
            )

        task = _TASK_RE.match(text)
        if task:
            self.setFormat(len(task.group(1)), len(task.group(2)), self.f_task)
        else:
            list_match = _LIST_RE.match(text)
            if list_match:
                self.setFormat(
                    len(list_match.group(1)),
                    len(list_match.group(2)),
                    self.f_list,
                )

        self._apply_inline(text)

    def _apply_inline(self, text: str) -> None:
        for pattern in _BOLD_RES:
            for match in pattern.finditer(text):
                self.setFormat(match.start(1), len(match.group(1)), self.f_bold)

        for pattern in _ITALIC_RES:
            for match in pattern.finditer(text):
                self.setFormat(match.start(1), len(match.group(1)), self.f_italic)

        for match in _STRIKE_RE.finditer(text):
            self.setFormat(match.start(1), len(match.group(1)), self.f_strike)

        for match in _LINK_RE.finditer(text):
            is_image = bool(match.group(1))
            self.setFormat(
                match.start(0), len(match.group(0)), self.f_image if is_image else self.f_link
            )
            self.setFormat(match.start(3), len(match.group(3)), self.f_url)

        for match in _AUTOLINK_RE.finditer(text):
            self.setFormat(match.start(0), len(match.group(0)), self.f_autolink)

        # Inline code is applied last so it overrides emphasis inside code spans.
        for match in _INLINE_CODE_RE.finditer(text):
            self.setFormat(match.start(1), len(match.group(1)), self.f_fence)
            self.setFormat(match.start(2), len(match.group(2)), self.f_code_inline)
            self.setFormat(match.end(2), len(match.group(1)), self.f_fence)

        for match in _TASK_BOX_RE.finditer(text):
            self.setFormat(match.start(0), 1, self.f_task)
