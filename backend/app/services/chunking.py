import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Splits text into sentences on '.', '!', '?' followed by whitespace.

    Falls back to treating the whole text as one "sentence" when no boundary is
    found (e.g. text with no punctuation), so callers degrade to word-window
    chunking below rather than losing content.
    """
    stripped = text.strip()
    if not stripped:
        return []
    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(stripped) if s.strip()]
    return sentences or [stripped]


def _word_window_chunks(words: list[str], max_words: int, overlap_words: int) -> list[str]:
    """Fixed-size overlapping word windows.

    Used directly for text with no sentence boundaries, and as a fallback for any
    single sentence longer than max_words on its own.
    """
    if not words:
        return []
    chunks = []
    start = 0
    step = max_words - overlap_words
    while start < len(words):
        chunk_words = words[start : start + max_words]
        chunks.append(" ".join(chunk_words))
        if start + max_words >= len(words):
            break
        start += step
    return chunks


def chunk_text(text: str, max_words: int = 220, overlap_words: int = 40) -> list[str]:
    """Split normalized text into overlapping, sentence-aware chunks.

    Chunks are packed to whole sentence boundaries where possible, so a chunk reads
    as coherent prose instead of being cut mid-sentence — this makes both the
    keyword snippet and the semantic embedding for a chunk more representative of
    its actual content. Overlap between consecutive chunks is carried forward by
    word count (not full sentences) so downstream search still sees shared context
    across a chunk boundary.

    A sentence longer than max_words on its own (or text with no sentence
    punctuation at all, e.g. code or a word list) falls back to a fixed word
    window, so no content is ever dropped.
    """
    if max_words <= overlap_words:
        raise ValueError("max_words must be greater than overlap_words")

    if not text.split():
        return []

    chunks: list[str] = []
    current_words: list[str] = []

    for sentence in _split_sentences(text):
        sentence_words = sentence.split()

        if len(sentence_words) > max_words:
            if current_words:
                chunks.append(" ".join(current_words))
                current_words = []
            chunks.extend(_word_window_chunks(sentence_words, max_words, overlap_words))
            continue

        if current_words and len(current_words) + len(sentence_words) > max_words:
            chunks.append(" ".join(current_words))
            current_words = current_words[-overlap_words:] if overlap_words else []

        current_words.extend(sentence_words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def estimate_token_count(text: str) -> int:
    return max(1, round(len(text.split()) / 0.75))
