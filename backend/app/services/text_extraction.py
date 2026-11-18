import re
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class TextExtractionError(Exception):
    pass


def extract_text(content: bytes, mime_type: str, filename: str = "") -> str:
    """Extracts text from file content already read into memory.

    Taking bytes rather than a filesystem path means extraction doesn't care
    whether the content came from local disk or was fetched from object
    storage (S3/MinIO) — the storage backend is fully decoupled from the
    processing pipeline.
    """
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        return _extract_pdf(content)
    return _extract_plain_text(content)


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise TextExtractionError("PDF is password-protected")
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise TextExtractionError(f"Corrupted or unreadable PDF: {exc}") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise TextExtractionError("No extractable text found in PDF")
    return text


def _extract_plain_text(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        raise TextExtractionError("File is empty")
    return text


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
