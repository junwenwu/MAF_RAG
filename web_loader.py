# Copyright (c) Microsoft. All rights reserved.

"""Fetch web pages, extract text, and chunk them for ingestion into a vector store.

Usage:
    from web_loader import load_and_chunk_urls

    chunks = load_and_chunk_urls([
        "https://learn.microsoft.com/en-us/agent-framework/overview/",
    ])
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup


@dataclass
class TextChunk:
    """A chunk of text extracted from a web page."""

    text: str
    source_url: str
    title: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Stable identifier for this chunk."""
        return f"{self.source_url}#chunk-{self.chunk_index}"


def fetch_page_text(url: str) -> tuple[str, str]:
    """Fetch a web page and return (title, cleaned_text)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Remove script, style, nav, footer, header elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Try to grab the main content area
    main = soup.find("main") or soup.find("article") or soup.find("body")

    title = soup.title.string.strip() if soup.title and soup.title.string else url
    text = main.get_text(separator="\n", strip=True) if main else ""

    # Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return title, text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """Split text into overlapping chunks by character count.

    Tries to split on paragraph boundaries first, then falls back to
    sentence boundaries.
    """
    if not text:
        return []

    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current.strip())
            # If a single paragraph exceeds chunk_size, split it further
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sub = ""
                for sent in sentences:
                    if len(sub) + len(sent) + 1 <= chunk_size:
                        sub = f"{sub} {sent}" if sub else sent
                    else:
                        if sub:
                            chunks.append(sub.strip())
                        sub = sent
                current = sub
            else:
                current = para

    if current:
        chunks.append(current.strip())

    # Apply overlap by prepending the tail of the previous chunk
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-chunk_overlap:]
            overlapped.append(f"{prev_tail} ... {chunks[i]}")
        chunks = overlapped

    return chunks


def load_and_chunk_urls(
    urls: list[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    """Fetch, extract, and chunk multiple web pages.

    Returns a flat list of TextChunk objects ready for vector store ingestion.
    """
    all_chunks: list[TextChunk] = []

    for url in urls:
        print(f"  Fetching: {url} ... ", end="", flush=True)
        try:
            title, text = fetch_page_text(url)
            raw_chunks = chunk_text(text, chunk_size, chunk_overlap)
            for idx, chunk_text_str in enumerate(raw_chunks):
                all_chunks.append(
                    TextChunk(
                        text=chunk_text_str,
                        source_url=url,
                        title=title,
                        chunk_index=idx,
                    )
                )
            print(f"{len(raw_chunks)} chunks")
        except Exception as exc:
            print(f"FAILED ({exc})")

    return all_chunks


# ---------------------------------------------------------------------------
# Default URLs for the prototype
# ---------------------------------------------------------------------------
DEFAULT_URLS = [
    "https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python",
    "https://learn.microsoft.com/en-us/agent-framework/agents/tools/?pivots=programming-language-python",
    "https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools?pivots=programming-language-python",
    "https://learn.microsoft.com/en-us/agent-framework/get-started/your-first-agent?pivots=programming-language-python",
    "https://learn.microsoft.com/en-us/agent-framework/get-started/add-tools?pivots=programming-language-python",
]


if __name__ == "__main__":
    chunks = load_and_chunk_urls(DEFAULT_URLS)
    print(f"\nTotal chunks: {len(chunks)}")
    for c in chunks[:3]:
        print(f"\n--- {c.title} (chunk {c.chunk_index}) ---")
        print(textwrap.shorten(c.text, width=200))
