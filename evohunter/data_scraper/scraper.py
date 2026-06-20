from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


class ScrapeError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    _block_tags = {
        "article",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "tr",
    }
    _ignored_tags = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._ignored_tags:
            self._ignored_depth += 1
        if tag in self._block_tags:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        if tag in self._block_tags:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return " ".join(self._parts)


def scrape_source(source: str, timeout: float = 10.0) -> str:
    if _is_url(source):
        return clean_scraped_text(_read_url(source, timeout))

    source_path = Path(source)
    if not source_path.exists():
        raise ScrapeError(f"source not found: {source}")
    if not source_path.is_file():
        raise ScrapeError(f"source must be a file: {source}")
    return clean_scraped_text(source_path.read_text(encoding="utf-8"))


def scrape_sources(sources: list[str], timeout: float = 10.0) -> list[dict[str, str]]:
    results = []
    for source in sources:
        if not isinstance(source, str) or not source.strip():
            results.append(
                {"source": "", "status": "error", "text": "", "error": "source must be a non-empty string"}
            )
            continue
        normalized_source = source.strip()
        try:
            results.append(
                {
                    "source": normalized_source,
                    "status": "success",
                    "text": scrape_source(normalized_source, timeout=timeout),
                    "error": "",
                }
            )
        except ScrapeError as exc:
            results.append(
                {
                    "source": normalized_source,
                    "status": "error",
                    "text": "",
                    "error": str(exc),
                }
            )
    return results


def clean_scraped_text(raw_text: str) -> str:
    text = _html_to_text(raw_text) if _looks_like_html(raw_text) else raw_text
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _html_to_text(html_text: str) -> str:
    parser = _TextExtractor()
    parser.feed(html_text)
    parser.close()
    return parser.text()


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def _looks_like_html(raw_text: str) -> bool:
    return bool(re.search(r"<\s*(html|body|article|section|div|p|h1|script|style)\b", raw_text, re.I))


def _read_url(url: str, timeout: float) -> str:
    request = Request(url, headers={"User-Agent": "EvoHunter/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except (OSError, URLError) as exc:
        raise ScrapeError(f"failed to read source: {url}") from exc
    return raw.decode(charset, errors="replace")
