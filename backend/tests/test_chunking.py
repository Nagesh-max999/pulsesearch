import pytest

from app.services.chunking import chunk_text, estimate_token_count


def test_chunk_text_empty_returns_no_chunks():
    assert chunk_text("") == []


def test_chunk_text_short_text_single_chunk():
    text = " ".join(["word"] * 50)
    chunks = chunk_text(text, max_words=220, overlap_words=40)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_splits_long_text_with_overlap():
    words = [f"w{i}" for i in range(500)]
    text = " ".join(words)
    chunks = chunk_text(text, max_words=200, overlap_words=40)

    assert len(chunks) > 1
    first_words = chunks[0].split()
    second_words = chunks[1].split()
    assert first_words[-40:] == second_words[:40]


def test_chunk_text_covers_all_words():
    words = [f"w{i}" for i in range(300)]
    text = " ".join(words)
    chunks = chunk_text(text, max_words=150, overlap_words=30)

    all_chunk_words = set()
    for chunk in chunks:
        all_chunk_words.update(chunk.split())
    assert all_chunk_words == set(words)


def test_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text("some text here", max_words=10, overlap_words=10)


def test_estimate_token_count_scales_with_words():
    short = estimate_token_count("one two three")
    long = estimate_token_count(" ".join(["word"] * 30))
    assert long > short
    assert short >= 1


def test_chunk_text_prefers_sentence_boundaries():
    sentence = "The quick brown fox jumps over the lazy dog today."  # 10 words
    text = " ".join([sentence] * 6)  # 60 words, 6 sentences
    chunks = chunk_text(text, max_words=25, overlap_words=5)

    assert len(chunks) > 1
    for chunk in chunks:
        # A sentence-packed chunk should end at a sentence boundary, not mid-word.
        assert chunk.rstrip().endswith("today.")


def test_chunk_text_does_not_split_a_sentence_that_fits():
    text = "Short first sentence. Short second sentence."
    chunks = chunk_text(text, max_words=220, overlap_words=40)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_oversized_single_sentence_falls_back_to_word_window():
    # No punctuation at all: one giant "sentence" longer than max_words.
    words = [f"w{i}" for i in range(500)]
    text = " ".join(words)
    chunks = chunk_text(text, max_words=200, overlap_words=40)

    all_words = set()
    for chunk in chunks:
        all_words.update(chunk.split())
    assert all_words == set(words)
    assert len(chunks) > 1
