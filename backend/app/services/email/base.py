from abc import ABC, abstractmethod


class EmailError(Exception):
    """Raised when an email genuinely fails to send (SMTP error, etc.)."""


class EmailProvider(ABC):
    """Interface all email backends must implement — same pluggable pattern
    as embeddings/reranking/storage: the rest of the app depends only on
    this interface, so the concrete backend is swappable via configuration.
    """

    @abstractmethod
    async def send(self, to: str, subject: str, body_text: str) -> None: ...
