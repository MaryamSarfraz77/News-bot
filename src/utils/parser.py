"""
Shared parsing logic for the summarizer's news output.

Expected format:

Topic: <topic>
Headline: <headline>
Summary: <summary>
Source URL: <url>

The parser identifies each item by its Headline line instead of
depending on "---" separators, making it more robust to LLM formatting.
"""

import re
from typing import TypedDict


class NewsItem(TypedDict):
    topic: str
    headline: str
    summary: str
    url: str


def _clean_url(url: str) -> str:
    """Convert Markdown-style links into plain URLs."""

    url = url.strip()

    # Handles:
    # [https://example.com](https://example.com)
    match = re.match(r"\[([^\]]+)\]\((https?://[^)]+)\)", url)

    if match:
        return match.group(2).strip()

    return url.strip("[]()")


def parse_news_items(text: str) -> list[NewsItem]:
    """
    Extract all news items from the summarizer output.

    Each item is detected using its 'Headline:' line, so the parser
    works even when the LLM omits the expected '---' separator.
    """

    if not text:
        return []

    items: list[NewsItem] = []

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Find every Headline line.
    headline_matches = list(
        re.finditer(
            r"(?im)^\s*Headline:\s*(.+?)\s*$",
            text,
        )
    )

    for index, headline_match in enumerate(headline_matches):

        # Start at this headline
        start = headline_match.start()

        # End immediately before the next headline
        end = (
            headline_matches[index + 1].start()
            if index + 1 < len(headline_matches)
            else len(text)
        )

        block = text[start:end]

        headline = headline_match.group(1).strip()

        summary_match = re.search(
            r"(?im)^\s*Summary:\s*(.+?)\s*$",
            block,
        )

        url_match = re.search(
            r"(?im)^\s*Source URL:\s*(.+?)\s*$",
            block,
        )

        topic_match = re.search(
            r"(?im)^\s*Topic:\s*(.+?)\s*$",
            block,
        )

        # A valid news item needs at least headline + summary
        if not summary_match:
            continue

        summary = summary_match.group(1).strip()

        topic = (
            topic_match.group(1).strip()
            if topic_match
            else ""
        )

        url = (
            _clean_url(url_match.group(1))
            if url_match
            else ""
        )

        items.append(
            NewsItem(
                topic=topic,
                headline=headline,
                summary=summary,
                url=url,
            )
        )

    return items