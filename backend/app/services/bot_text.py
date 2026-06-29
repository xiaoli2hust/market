from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002
        if tag.lower() in {"script", "style", "iframe", "object", "embed"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "iframe", "object", "embed"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", unescape(data)).strip()
        if text:
            self.parts.append(text)


def extract_text_from_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return "\n".join(extractor.parts)

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    clean = _normalize_text(text)
    chunks = []
    start = 0
    while start < len(clean):
        chunk = clean[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += max(200, chunk_size - overlap)
    return chunks[:500]
