"""Split labeled protocol sections into retrieval chunks.

Small sections become a single chunk. Longer sections are split into
overlapping ~500–800 token windows. Offsets refer to the original section text.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.parse import ProtocolSection

# ~4 characters per token is a stable stand-in without a tokenizer dependency.
CHARS_PER_TOKEN = 4
DEFAULT_MAX_TOKENS = 700
DEFAULT_OVERLAP_TOKENS = 80


@dataclass(frozen=True)
class Chunk:
    """A retrievable slice of a protocol section."""

    nct_id: str
    section: str
    text: str
    brief_title: str
    start_char: int
    end_char: int
    chunk_index: int
    id: int | None = None

    def labeled_text(self) -> str:
        """Section body prefixed with study identity for later indexing."""
        title = self.brief_title or self.nct_id
        header = f"[{self.nct_id}] {title} | {self.section}"
        return f"{header}\n{self.text}"


def approx_token_count(text: str) -> int:
    """Approximate token count from character length."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def chunk_section(
    section: ProtocolSection,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Turn one labeled section into one or more overlapping chunks."""
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be >= 0")
    if overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be smaller than max_tokens")

    text = section.text
    if not text.strip():
        return []

    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN
    spans = _window_spans(text, max_chars=max_chars, overlap_chars=overlap_chars)

    chunks: list[Chunk] = []
    for index, (start, end) in enumerate(spans):
        body = text[start:end]
        if not body.strip():
            continue
        chunks.append(
            Chunk(
                nct_id=section.nct_id,
                section=section.section,
                text=body,
                brief_title=section.brief_title,
                start_char=start,
                end_char=end,
                chunk_index=index,
            )
        )
    return chunks


def chunk_sections(
    sections: list[ProtocolSection],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Chunk every section, preserving study and section order."""
    chunks: list[Chunk] = []
    for section in sections:
        chunks.extend(
            chunk_section(
                section,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
    return chunks


def _window_spans(text: str, *, max_chars: int, overlap_chars: int) -> list[tuple[int, int]]:
    length = len(text)
    if length <= max_chars:
        return [(0, length)]

    spans: list[tuple[int, int]] = []
    start = 0
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            break_at = _last_break(text, start, end)
            if break_at > start:
                end = break_at
        start, end = _strip_span(text, start, end)
        if end <= start:
            break
        spans.append((start, end))
        if end >= length:
            break

        next_start = end - overlap_chars
        if next_start <= start:
            next_start = end
        while next_start < length and text[next_start].isspace():
            next_start += 1
        if next_start >= length:
            break
        start = next_start

    return spans


def _last_break(text: str, start: int, end: int) -> int:
    """Prefer paragraph, then line, then sentence, then word boundaries."""
    window = text[start:end]
    for separator in ("\n\n", "\n", ". ", " "):
        index = window.rfind(separator)
        # Avoid tiny tails that would create almost-empty next windows.
        if index > len(window) // 4:
            return start + index + len(separator)
    return end


def _strip_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
