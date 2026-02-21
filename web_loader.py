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

    # Inline link URLs so they survive get_text().
    # Turns <a href="https://x.com">click</a> → "click (https://x.com)"
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Make relative URLs absolute
        if href.startswith("/"):
            href = f"https://learn.microsoft.com{href}"
        link_text = a_tag.get_text(strip=True)
        if link_text and href.startswith("http"):
            a_tag.replace_with(f"{link_text} ({href})")

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
# Default URLs – full Agent Framework documentation
# ---------------------------------------------------------------------------
_BASE = "https://learn.microsoft.com/en-us/agent-framework"
_PIVOT = "?pivots=programming-language-python"

DEFAULT_URLS = [
    # Landing page (has GitHub repo link, samples, etc.)
    f"{_BASE}/",
    # Overview
    f"{_BASE}/overview/{_PIVOT}",
    # Get Started
    f"{_BASE}/get-started/{_PIVOT}",
    f"{_BASE}/get-started/your-first-agent{_PIVOT}",
    f"{_BASE}/get-started/add-tools{_PIVOT}",
    f"{_BASE}/get-started/multi-turn{_PIVOT}",
    f"{_BASE}/get-started/memory{_PIVOT}",
    f"{_BASE}/get-started/workflows{_PIVOT}",
    f"{_BASE}/get-started/hosting{_PIVOT}",
    # Agents
    f"{_BASE}/agents/{_PIVOT}",
    f"{_BASE}/agents/running-agents{_PIVOT}",
    f"{_BASE}/agents/multimodal{_PIVOT}",
    f"{_BASE}/agents/structured-output{_PIVOT}",
    f"{_BASE}/agents/background-responses{_PIVOT}",
    f"{_BASE}/agents/rag{_PIVOT}",
    f"{_BASE}/agents/declarative{_PIVOT}",
    f"{_BASE}/agents/observability{_PIVOT}",
    # Tools
    f"{_BASE}/agents/tools/{_PIVOT}",
    f"{_BASE}/agents/tools/function-tools{_PIVOT}",
    f"{_BASE}/agents/tools/tool-approval{_PIVOT}",
    f"{_BASE}/agents/tools/code-interpreter{_PIVOT}",
    f"{_BASE}/agents/tools/file-search{_PIVOT}",
    f"{_BASE}/agents/tools/web-search{_PIVOT}",
    f"{_BASE}/agents/tools/hosted-mcp-tools{_PIVOT}",
    f"{_BASE}/agents/tools/local-mcp-tools{_PIVOT}",
    # Conversations & Memory
    f"{_BASE}/agents/conversations/{_PIVOT}",
    f"{_BASE}/agents/conversations/session{_PIVOT}",
    f"{_BASE}/agents/conversations/context-providers{_PIVOT}",
    f"{_BASE}/agents/conversations/storage{_PIVOT}",
    # Middleware
    f"{_BASE}/agents/middleware/{_PIVOT}",
    f"{_BASE}/agents/middleware/defining-middleware{_PIVOT}",
    f"{_BASE}/agents/middleware/chat-middleware{_PIVOT}",
    f"{_BASE}/agents/middleware/agent-vs-run-scope{_PIVOT}",
    f"{_BASE}/agents/middleware/termination{_PIVOT}",
    f"{_BASE}/agents/middleware/result-overrides{_PIVOT}",
    f"{_BASE}/agents/middleware/exception-handling{_PIVOT}",
    f"{_BASE}/agents/middleware/shared-state{_PIVOT}",
    f"{_BASE}/agents/middleware/runtime-context{_PIVOT}",
    # Providers
    f"{_BASE}/agents/providers/{_PIVOT}",
    f"{_BASE}/agents/providers/azure-openai{_PIVOT}",
    f"{_BASE}/agents/providers/openai{_PIVOT}",
    f"{_BASE}/agents/providers/azure-ai-foundry{_PIVOT}",
    f"{_BASE}/agents/providers/anthropic{_PIVOT}",
    f"{_BASE}/agents/providers/ollama{_PIVOT}",
    f"{_BASE}/agents/providers/github-copilot{_PIVOT}",
    f"{_BASE}/agents/providers/copilot-studio{_PIVOT}",
    f"{_BASE}/agents/providers/custom{_PIVOT}",
    # Workflows
    f"{_BASE}/workflows/{_PIVOT}",
    f"{_BASE}/workflows/executors{_PIVOT}",
    f"{_BASE}/workflows/edges{_PIVOT}",
    f"{_BASE}/workflows/events{_PIVOT}",
    f"{_BASE}/workflows/workflows{_PIVOT}",
    f"{_BASE}/workflows/agents-in-workflows{_PIVOT}",
    f"{_BASE}/workflows/human-in-the-loop{_PIVOT}",
    f"{_BASE}/workflows/state{_PIVOT}",
    f"{_BASE}/workflows/checkpoints{_PIVOT}",
    f"{_BASE}/workflows/declarative{_PIVOT}",
    f"{_BASE}/workflows/observability{_PIVOT}",
    f"{_BASE}/workflows/as-agents{_PIVOT}",
    f"{_BASE}/workflows/visualization{_PIVOT}",
    # Orchestrations
    f"{_BASE}/workflows/orchestrations/{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/sequential{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/concurrent{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/handoff{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/group-chat{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/magentic{_PIVOT}",
    # Integrations
    f"{_BASE}/integrations/{_PIVOT}",
    f"{_BASE}/integrations/azure-functions{_PIVOT}",
    f"{_BASE}/integrations/openai-endpoints{_PIVOT}",
    f"{_BASE}/integrations/purview{_PIVOT}",
    f"{_BASE}/integrations/m365{_PIVOT}",
    f"{_BASE}/integrations/a2a{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/getting-started{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/backend-tool-rendering{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/frontend-tools{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/security-considerations{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/human-in-the-loop{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/state-management{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/testing-with-dojo{_PIVOT}",
    # DevUI
    f"{_BASE}/devui/{_PIVOT}",
    f"{_BASE}/devui/directory-discovery{_PIVOT}",
    f"{_BASE}/devui/api-reference{_PIVOT}",
    f"{_BASE}/devui/tracing{_PIVOT}",
    f"{_BASE}/devui/security{_PIVOT}",
    f"{_BASE}/devui/samples{_PIVOT}",
    # Migration Guide
    f"{_BASE}/migration-guide/{_PIVOT}",
    f"{_BASE}/migration-guide/from-autogen/{_PIVOT}",
    f"{_BASE}/migration-guide/from-semantic-kernel/{_PIVOT}",
    f"{_BASE}/migration-guide/from-semantic-kernel/samples{_PIVOT}",
    # Support
    f"{_BASE}/support/{_PIVOT}",
    f"{_BASE}/support/faq{_PIVOT}",
    f"{_BASE}/support/troubleshooting{_PIVOT}",
    f"{_BASE}/support/upgrade/{_PIVOT}",
    f"{_BASE}/support/upgrade/requests-and-responses-upgrade-guide-python{_PIVOT}",
    f"{_BASE}/support/upgrade/typed-options-guide-python{_PIVOT}",
    f"{_BASE}/support/upgrade/python-2026-significant-changes{_PIVOT}",
]


if __name__ == "__main__":
    chunks = load_and_chunk_urls(DEFAULT_URLS)
    print(f"\nTotal chunks: {len(chunks)}")
    for c in chunks[:3]:
        print(f"\n--- {c.title} (chunk {c.chunk_index}) ---")
        print(textwrap.shorten(c.text, width=200))
