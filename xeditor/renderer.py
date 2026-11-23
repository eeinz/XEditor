"""Markdown -> HTML rendering tuned for Qt's rich text engine."""

from __future__ import annotations

import base64
import html as html_lib
import mimetypes
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

import markdown
from markdown.inlinepatterns import SimpleTagInlineProcessor
from markdown.treeprocessors import Treeprocessor

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImageReader

from .html_process import apply_highlights, linkify_bare_urls, sanitize_html
from .themes import Theme, build_preview_css


@dataclass(frozen=True)
class TocEntry:
    level: int
    text: str
    anchor: str


@dataclass
class RenderedDocument:
    html: str
    body: str
    toc: list[TocEntry] = field(default_factory=list)
    base_dir: str | None = None


_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_TASK_RE = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+)\[([ xX])\]\s+")
_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.IGNORECASE)
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_SIZE_ATTR_RE = re.compile(r'\s(?:width|height)="[^"]*"', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_CODEHILITE_RE = re.compile(
    r'<div class="codehilite" style="background: (#[0-9a-fA-F]{3,8});?">(.*?)</div>',
    re.DOTALL,
)


class _TaskListTreeprocessor(Treeprocessor):
    """Drop list bullets for task-list items while keeping nesting intact."""

    def run(self, root):
        for element in root.iter():
            if element.tag not in ("ul", "ol"):
                continue
            children = element.findall("li")
            if any((child.text or "").lstrip().startswith(("☐", "☑")) for child in children):
                style = element.get("style", "")
                if "list-style-type" not in style:
                    element.set(
                        "style",
                        (style + ";" if style else "") + "list-style-type: none",
                    )
        return root


def _preprocess_tasks(source: str) -> str:
    """Turn GFM task list markers into checkbox glyphs (outside code fences)."""
    lines = source.splitlines(keepends=True)
    result: list[str] = []
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        if fence is None:
            match = _FENCE_RE.match(line)
            if match:
                fence = match.group(1)[0]
                result.append(line)
                continue
            task = _TASK_RE.match(line)
            if task:
                checked = task.group(2).lower() == "x"
                line = f"{task.group(1)}{'☑' if checked else '☐'} {line[task.end():]}"
            result.append(line)
        else:
            if stripped.startswith(fence * 3):
                fence = None
            result.append(line)
    return "".join(result)


def _build_markdown(pygments_style: str) -> markdown.Markdown:
    md = markdown.Markdown(
        extensions=[
            "meta",
            "toc",
            "codehilite",
            "extra",
            "sane_lists",
        ],
        extension_configs={
            "toc": {
                "permalink": False,
                "toc_depth": "1-6",
            },
            "codehilite": {
                "noclasses": True,
                "guess_lang": False,
                "pygments_style": pygments_style,
                "linenums": False,
                "css_class": "codehilite",
            },
        },
        output_format="html5",
    )
    md.inlinePatterns.register(
        SimpleTagInlineProcessor(r"(~~)(.+?)~~", "s"), "xeditor-strikethrough", 175
    )
    md.treeprocessors.register(
        _TaskListTreeprocessor(md), "xeditor-tasklists", 5
    )
    return md


@lru_cache(maxsize=4)
def _markdown_for_style(pygments_style: str) -> markdown.Markdown:
    return _build_markdown(pygments_style)


def _flatten_toc(tokens: list[dict]) -> list[TocEntry]:
    entries: list[TocEntry] = []
    for token in tokens:
        name = _TAG_RE.sub("", token.get("name", ""))
        name = name.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        entries.append(
            TocEntry(
                level=int(token.get("level", 1)),
                text=name.strip(),
                anchor=str(token.get("id", "")),
            )
        )
        entries.extend(_flatten_toc(token.get("children", [])))
    return entries


def _absolutize_images(html: str, base_dir: str | None) -> str:
    if not base_dir:
        return html

    root = Path(base_dir)

    def replace(match: re.Match[str]) -> str:
        prefix, src, suffix = match.groups()
        if not src or src.startswith(("data:", "http://", "https://", "file:", "qrc:")):
            return match.group(0)
        path = Path(unquote(src))
        if not path.is_absolute():
            path = root / path
        try:
            resolved = path.resolve()
        except OSError:
            return match.group(0)
        if not resolved.exists():
            return match.group(0)
        return f"{prefix}{resolved.as_uri()}{suffix}"

    return _IMG_SRC_RE.sub(replace, html)


def _constrain_images(html: str, max_width: int | None) -> str:
    """Scale down oversized local images, respecting explicit width attributes."""
    if not max_width:
        return html

    def replace(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r'\bwidth="', tag, re.IGNORECASE):
            return tag
        src = re.search(r'\bsrc="([^"]+)"', tag, re.IGNORECASE)
        if not src:
            return tag
        url = QUrl(src.group(1))
        if not url.isLocalFile():
            return tag
        size = QImageReader(url.toLocalFile()).size()
        if not size.isValid() or size.width() <= max_width:
            return tag
        height = max(1, round(size.height() * max_width / size.width()))
        stripped = tag.rstrip()
        self_closing = stripped.endswith("/>")
        body = stripped[:-2] if self_closing else stripped[:-1]
        body = _SIZE_ATTR_RE.sub("", body)
        ending = "/>" if self_closing else ">"
        return f'{body} width="{max_width}" height="{height}"{ending}'

    return _IMG_TAG_RE.sub(replace, html)


def _wrap_code_blocks(html: str, theme: Theme) -> str:
    """Render highlighted code as a single-cell table for a continuous panel."""

    def replace(match: re.Match[str]) -> str:
        inner = match.group(2)
        inner = re.sub(r"<pre[^>]*>", '<pre style="margin: 0; background-color: transparent; white-space: pre-wrap; line-height: 125%;">', inner, count=1)
        inner = re.sub(
            r"<code([^>]*)>",
            r'<code\1 style="background-color: transparent;">',
            inner,
            count=1,
        )
        return (
            '<table width="100%" cellspacing="0" cellpadding="0" '
            'style="margin: 12px 0; border-collapse: collapse;">'
            f'<tr><td style="background-color: {theme.code_bg}; '
            f'border: 1px solid {theme.border}; padding: 10px 12px;">'
            f"{inner}</td></tr></table>"
        )

    return _CODEHILITE_RE.sub(replace, html)


def _embed_images(html: str) -> str:
    """Inline local images as data URIs for truly standalone HTML exports."""

    def replace(match: re.Match[str]) -> str:
        tag = match.group(0)
        src = re.search(r'\bsrc="([^"]+)"', tag, re.IGNORECASE)
        if not src:
            return tag
        url = QUrl(src.group(1))
        if not url.isLocalFile():
            return tag
        path = Path(url.toLocalFile())
        try:
            data = path.read_bytes()
        except OSError:
            return tag
        mime, _ = mimetypes.guess_type(path.name)
        if not mime:
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".svg": "image/svg+xml",
            }.get(path.suffix.lower(), "application/octet-stream")
        encoded = base64.b64encode(data).decode("ascii")
        return tag.replace(src.group(1), f"data:{mime};base64,{encoded}", 1)

    return _IMG_TAG_RE.sub(replace, html)


def render_document(
    source: str,
    theme: Theme,
    base_dir: str | None = None,
    font_size: int = 15,
    max_image_width: int | None = None,
    embed_images: bool = False,
) -> RenderedDocument:
    """Convert Markdown source into a complete HTML document for QTextBrowser."""
    md = _markdown_for_style(theme.pygments_style)
    md.reset()
    prepared = _preprocess_tasks(source)
    try:
        body = md.convert(prepared)
    except Exception as exc:  # never let a bad document break the preview
        body = (
            '<div style="color: #cf222e; font-weight: 600;">'
            "Markdown 渲染失败</div>"
            f"<pre>{html_lib.escape(str(exc))}</pre>"
        )
    toc = _flatten_toc(getattr(md, "toc_tokens", []))
    body = _absolutize_images(body, base_dir)
    body = sanitize_html(body)
    body = linkify_bare_urls(body)
    body = apply_highlights(body, theme.mark_bg)
    body = _constrain_images(body, max_image_width)
    if embed_images:
        body = _embed_images(body)
    body = _wrap_code_blocks(body, theme)
    css = build_preview_css(theme, font_size)
    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<style>{css}</style></head><body>{body}</body></html>"
    )
    return RenderedDocument(html=html, body=body, toc=toc, base_dir=base_dir)
