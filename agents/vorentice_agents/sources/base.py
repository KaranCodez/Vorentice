"""Source adapter contract.

Every news provider — free RSS today, Refinitiv/Factiva tomorrow — is
hidden behind this interface. The pipeline only ever sees `RawArticle`
lists, so swapping or adding providers never touches pipeline code
(open/closed principle).
"""

from abc import ABC, abstractmethod

import httpx

from vorentice_agents.domain.models import RawArticle

# Identify ourselves politely; several feeds reject blank user agents.
USER_AGENT = "VorenticeNewsAgent/0.1 (+energy-supply-intelligence; contact ops)"


class SourceError(RuntimeError):
    """A source failed for this run. The pipeline logs it and continues —
    one dead feed must never kill the whole ingestion cycle."""

    def __init__(self, source_name: str, message: str) -> None:
        self.source_name = source_name
        super().__init__(f"[{source_name}] {message}")


class NewsSource(ABC):
    """Abstract news provider."""

    #: Human-readable, stable identifier — becomes RawArticle.source_name
    #: and the key in run stats / source-health monitoring.
    name: str

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        """Return newly published articles.

        Implementations must be idempotent per call and raise SourceError
        on failure rather than returning partial silently-wrong data.
        The shared AsyncClient is injected so all sources reuse one
        connection pool and one timeout policy.
        """
        raise NotImplementedError
