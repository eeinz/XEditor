"""Small, dependency-free HTML sanitizer and bare-URL linkifier.

The preview is rendered with Qt's rich text engine, which does not execute
JavaScript. Sanitizing still matters for exported HTML, and for keeping raw
Markdown HTML from smuggling in scripts, remote frames or event handlers.
"""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

_ALLOWED_TAGS = frozenset(
    {
        "a",
        "abbr",
        "address",
        "b",
        "big",
        "blockquote",
        "br",
        "caption",
        "center",
        "cite",
        "code",
        "dd",
        "del",
        "details",
        "dfn",
        "div",
        "dl",
        "dt",
        "em",
        "figcaption",
        "figure",
        "font",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "ins",
        "kbd",
        "li",
        "mark",
        "ol",
        "p",
        "pre",
        "q",
        "s",
        "samp",
        "small",
        "span",
        "strike",
        "strong",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "tt",
        "u",
        "ul",
        "var",
        "wbr",
    }
)

_VOID_TAGS = frozenset({"br", "hr", "img", "wbr"})
_VOID_DROP_CONTENT_TAGS = frozenset({"embed", "param", "source", "track", "frame"})

# Tags whose entire content is discarded.
_DROP_CONTENT_TAGS = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "applet",
        "svg",
        "math",
        "template",
        "noscript",
        "canvas",
        "video",
        "audio",
        "source",
        "track",
        "param",
        "frameset",
        "frame",
        "noframes",
    }
)

# Tags that are removed while their text children are kept.
_DROP_TAGS = frozenset(
    {
        "html",
        "head",
        "title",
        "body",
        "meta",
        "link",
        "base",
        "form",
        "input",
        "textarea",
        "select",
        "option",
        "optgroup",
        "button",
        "colgroup",
        "col",
    }
)

_GLOBAL_ATTRS = frozenset(
    {
        "class",
        "style",
        "id",
        "title",
        "align",
        "dir",
        "lang",
    }
)

_TAG_ATTRS = {
    "a": {"href", "name", "title", "rel"},
    "img": {"src", "alt", "title", "width", "height", "align"},
    "font": {"color", "face", "size"},
    "table": {"border", "cellpadding", "cellspacing", "width", "height", "bgcolor", "align"},
    "td": {"colspan", "rowspan", "valign", "bgcolor", "width", "height"},
    "th": {"colspan", "rowspan", "valign", "bgcolor", "width", "height"},
    "ol": {"start", "type", "reversed"},
    "ul": {"type"},
    "li": {"value"},
    "details": {"open"},
}

_SAFE_LINK_SCHEMES = frozenset({"http", "https", "mailto", "file"})
_SAFE_IMAGE_SCHEMES = frozenset({"http", "https", "file", "data"})
_SAFE_DATA_IMAGE_RE = re.compile(
    r"^data:image/(?:png|jpe?g|gif|webp|bmp|avif);base64,[a-z0-9+/=\s]+$", re.IGNORECASE
)
_STYLE_DANGER_RE = re.compile(
    r"(?i)(?:expression|javascript|vbscript|@import|behavior|-moz-binding)\s*[:(]"
)
_STYLE_BLOCKED_PROPERTIES = ("position", "z-index", "inset", "float")


def _safe_url(value: str, tag: str, attr: str) -> str | None:
    if not value:
        return None
    raw = html_lib.unescape(value).strip()
    collapsed = re.sub(r"[\x00-\x20]+", "", raw).lower()
    if not collapsed:
        return None

    if tag == "img" and attr == "src" and collapsed.startswith("data:"):
        return raw if _SAFE_DATA_IMAGE_RE.match(collapsed) else None

    # Reject obfuscated script schemes before URL parsing.
    if collapsed.startswith(("javascript:", "vbscript:", "data:", "about:")):
        return None

    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme:
        allowed = _SAFE_LINK_SCHEMES if tag == "a" else _SAFE_IMAGE_SCHEMES
        if scheme not in allowed:
            return None
    return raw


def _safe_style(value: str) -> str:
    if not value:
        return ""
    if _STYLE_DANGER_RE.search(value) or re.search(r"(?i)url\s*\(", value):
        return ""
    declarations = []
    for declaration in value.split(";"):
        declaration = declaration.strip()
        if not declaration:
            continue
        name = declaration.split(":", 1)[0].strip().lower()
        if name in _STYLE_BLOCKED_PROPERTIES:
            continue
        declarations.append(declaration)
    return "; ".join(declarations)


def _attr_allowed(tag: str, name: str) -> bool:
    if name.startswith("on"):
        return False
    if name in _GLOBAL_ATTRS:
        return True
    return name in _TAG_ATTRS.get(tag, set())


def _render_start_tag(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    parts = [tag]
    for raw_name, raw_value in attrs:
        name = (raw_name or "").lower()
        if not _attr_allowed(tag, name):
            continue
        value = raw_value
        if name == "style":
            value = _safe_style(value or "")
            if not value:
                continue
        elif name in ("href", "src"):
            value = _safe_url(value or "", tag, name)
            if value is None:
                continue
        elif name == "rel":
            value = "noopener noreferrer"
        if value is None:
            parts.append(name)
        else:
            parts.append(f'{name}="{html_lib.escape(value, quote=True)}"')
    return "<" + " ".join(parts) + ">"


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.output: list[str] = []
        self._skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: N802
        tag = tag.lower()
        if self._skip_stack:
            if tag in _DROP_CONTENT_TAGS and tag not in _VOID_DROP_CONTENT_TAGS:
                self._skip_stack.append(tag)
            return
        if tag in _DROP_CONTENT_TAGS:
            if tag not in _VOID_DROP_CONTENT_TAGS:
                self._skip_stack.append(tag)
            return
        if tag in _DROP_TAGS or tag not in _ALLOWED_TAGS:
            return
        self.output.append(_render_start_tag(tag, list(attrs)))
        if tag in _VOID_TAGS:
            return

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: N802
        tag = tag.lower()
        if self._skip_stack or tag in _DROP_CONTENT_TAGS or tag in _DROP_TAGS:
            return
        if tag not in _ALLOWED_TAGS:
            return
        self.output.append(_render_start_tag(tag, list(attrs)))
        if tag not in _VOID_TAGS:
            self.output.append(f"</{tag}>")

    def handle_endtag(self, tag: str) -> None:  # noqa: N802
        tag = tag.lower()
        if self._skip_stack:
            if tag in self._skip_stack:
                index = len(self._skip_stack) - 1 - self._skip_stack[::-1].index(tag)
                del self._skip_stack[index:]
            return
        if tag in _VOID_TAGS or tag not in _ALLOWED_TAGS:
            return
        self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_stack:
            self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._skip_stack:
            self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._skip_stack:
            self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        return

    def handle_decl(self, decl: str) -> None:
        return

    def handle_pi(self, data: str) -> None:
        return

    def unknown_decl(self, data: str) -> None:
        return


def sanitize_html(html: str) -> str:
    """Return HTML with dangerous tags, attributes and URL schemes removed."""
    parser = _Sanitizer()
    parser.feed(html)
    parser.close()
    return "".join(parser.output)


# ---------------------------------------------------------------------------
# Bare URL auto-linking (applied to plain text segments only)
# ---------------------------------------------------------------------------

_TAG_SPLIT_RE = re.compile(r"(<[^>]*>)")
_BARE_URL_RE = re.compile(
    r"(?<![A-Za-z0-9_/=\"'])"
    r"((?:https?://|www\.)[^\s<>\"'，。；：！？、（）【】《》「」“”‘’\u3000-\u303f\uff01-\uff65\u4e00-\u9fff]+)",
    re.IGNORECASE,
)
_LINK_SKIP_TAGS = frozenset(
    {"a", "code", "pre", "script", "style", "textarea", "kbd", "samp"}
)


def _linkify_segment(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        url = match.group(1)
        trailing = ""
        while url and url[-1] in ".,;:!?，。；：！？、":
            trailing = url[-1] + trailing
            url = url[:-1]
        while url.endswith(")") and url.count(")") > url.count("("):
            trailing = ")" + trailing
            url = url[:-1]
        while url.endswith("]") and url.count("]") > url.count("["):
            trailing = "]" + trailing
            url = url[:-1]
        if not url or url.lower() in {"http://", "https://", "www."}:
            return match.group(0)
        raw = html_lib.unescape(url)
        href = raw if raw.lower().startswith("http") else f"http://{raw}"
        safe_href = html_lib.escape(href, quote=True)
        label = html_lib.escape(raw, quote=False)
        return f'<a href="{safe_href}" rel="noopener noreferrer">{label}</a>{trailing}'

    return _BARE_URL_RE.sub(replace, text)


def linkify_bare_urls(html: str) -> str:
    """Wrap bare http(s)/www URLs in anchors, leaving tags and code untouched."""
    parts = _TAG_SPLIT_RE.split(html)
    output: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        tag_match = re.match(r"<\s*(/?)\s*([a-zA-Z0-9]+)", part)
        if tag_match:
            closing = bool(tag_match.group(1))
            tag = tag_match.group(2).lower()
            if tag in _LINK_SKIP_TAGS:
                if closing:
                    if tag in skip_stack:
                        index = len(skip_stack) - 1 - skip_stack[::-1].index(tag)
                        del skip_stack[index:]
                elif not part.rstrip().endswith("/>"):
                    skip_stack.append(tag)
            output.append(part)
            continue
        output.append(part if skip_stack else _linkify_segment(part))

    return "".join(output)


_HIGHLIGHT_RE = re.compile(r"==(?=\S)(.+?)(?<=\S)==")
_HIGHLIGHT_SKIP_TAGS = frozenset({"code", "pre", "script", "style", "textarea"})


def apply_highlights(html: str, color: str) -> str:
    """Turn ==highlight== into a themed inline background span."""
    if "==" not in html:
        return html
    parts = _TAG_SPLIT_RE.split(html)
    output: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        tag_match = re.match(r"<\s*(/?)\s*([a-zA-Z0-9]+)", part)
        if tag_match:
            closing = bool(tag_match.group(1))
            tag = tag_match.group(2).lower()
            if tag in _HIGHLIGHT_SKIP_TAGS:
                if closing:
                    if tag in skip_stack:
                        index = len(skip_stack) - 1 - skip_stack[::-1].index(tag)
                        del skip_stack[index:]
                elif not part.rstrip().endswith("/>"):
                    skip_stack.append(tag)
            output.append(part)
            continue
        if skip_stack or "==" not in part:
            output.append(part)
            continue
        output.append(
            _HIGHLIGHT_RE.sub(
                lambda m: f'<span style="background-color: {color};">{m.group(1)}</span>',
                part,
            )
        )

    return "".join(output)
