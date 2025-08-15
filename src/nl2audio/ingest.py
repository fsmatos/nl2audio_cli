from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
import trafilatura
from bs4 import BeautifulSoup
from readability import Document


@dataclass
class IngestResult:
    title: str
    text: str
    source: str


def _html_to_text(html: str) -> str:
    # Try readability first
    try:
        doc = Document(html)
        content_html = doc.summary(html_partial=True)
        # Try different parser backends in order of preference
        soup = None
        for parser in ["html5lib", "html.parser", "lxml"]:
            try:
                soup = BeautifulSoup(content_html, parser)
                break
            except Exception:
                continue

        if soup is None:
            # Last resort: try with basic html.parser
            soup = BeautifulSoup(content_html, "html.parser")

    except Exception:
        # If readability fails, try direct parsing
        soup = None
        for parser in ["html5lib", "html.parser", "lxml"]:
            try:
                soup = BeautifulSoup(html, parser)
                break
            except Exception:
                continue

        if soup is None:
            # Last resort: try with basic html.parser
            soup = BeautifulSoup(html, "html.parser")

    # Clean up the HTML
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    # Basic cleanup
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()
    return text


def from_source(source: str, stdin_text: Optional[str] = None) -> IngestResult:
    # If source looks like URL
    if re.match(r"^https?://", source, flags=re.I):
        r = requests.get(source, timeout=20)
        r.raise_for_status()
        html = r.text
        # Try trafilatura to extract main content
        extracted = trafilatura.extract(
            html, include_comments=False, include_tables=False
        ) or _html_to_text(html)
        title = Document(html).short_title() if html else "Untitled"
        return IngestResult(title=title, text=extracted, source=source)

    p = Path(source).expanduser()
    if p.exists():
        if p.suffix.lower() in {".html", ".htm"}:
            html = p.read_text(encoding="utf-8", errors="ignore")
            extracted = trafilatura.extract(
                html, include_comments=False, include_tables=False
            ) or _html_to_text(html)
            title = Document(html).short_title() or p.stem
            return IngestResult(title=title, text=extracted, source=str(p))
        else:
            # treat as plaintext
            text = p.read_text(encoding="utf-8", errors="ignore")
            return IngestResult(title=p.stem, text=text, source=str(p))

    if stdin_text:
        return IngestResult(title="Untitled", text=stdin_text, source="stdin")

    raise FileNotFoundError(f"Cannot load source: {source}")
