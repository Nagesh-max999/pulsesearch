import pytest

from app.services.text_extraction import TextExtractionError, extract_text, normalize_text


def test_extract_plain_text():
    text = extract_text(b"Hello world\nThis is a test.", "text/plain")
    assert "Hello world" in text


def test_extract_plain_text_empty_content_raises():
    with pytest.raises(TextExtractionError):
        extract_text(b"", "text/plain")


def test_extract_corrupted_pdf_raises():
    with pytest.raises(TextExtractionError):
        extract_text(b"%PDF-1.4 not a real pdf structure", "application/pdf")


def test_extract_uses_filename_extension_when_mime_type_is_generic():
    with pytest.raises(TextExtractionError):
        # Detected as a PDF from the filename, then fails because it isn't one.
        extract_text(b"plain text content", "application/octet-stream", filename="doc.pdf")


def test_normalize_text_collapses_whitespace():
    raw = "Hello    world\n\n\n\nGoodbye"
    normalized = normalize_text(raw)
    assert "    " not in normalized
    assert "\n\n\n" not in normalized


def test_normalize_text_strips_null_bytes():
    raw = "Hello\x00World"
    assert "\x00" not in normalize_text(raw)
