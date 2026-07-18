"""ReliefWeb adapter — UN OCHA humanitarian & disaster reports.

Article-shaped (goes through LLM classification): disasters, conflicts
and infrastructure incidents in producer/transit regions often precede
supply disruptions. Uses the v2 API.

NOTE: v2 requires an *approved* appname. Request one at
https://apidoc.reliefweb.int/ then set RELIEFWEB_APPNAME in .env. Until
an approved appname is set this source stays dormant (see registry).
"""

import httpx

from vorentice_agents.domain.models import RawArticle
from vorentice_agents.sources.base import NewsSource, SourceError, USER_AGENT

_RELIEFWEB_URL = "https://api.reliefweb.int/v2/reports"

# Reports mentioning energy-supply-relevant terms.
_QUERY = "oil OR petroleum OR refinery OR pipeline OR port OR tanker OR energy"


class ReliefWebSource(NewsSource):
    name = "reliefweb"

    def __init__(self, appname: str, max_entries: int = 20) -> None:
        self._appname = appname
        self._max_entries = max_entries

    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        try:
            response = await client.post(
                _RELIEFWEB_URL,
                params={"appname": self._appname},
                json={
                    "limit": self._max_entries,
                    "sort": ["date:desc"],
                    "query": {"value": _QUERY, "fields": ["title", "body"]},
                    "fields": {
                        "include": ["title", "url", "date.created", "source.shortname"]
                    },
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            data = response.json().get("data", [])
        except httpx.HTTPError as exc:
            raise SourceError(self.name, str(exc)) from exc
        except ValueError as exc:
            raise SourceError(self.name, f"bad JSON: {exc}") from exc

        articles: list[RawArticle] = []
        for entry in data:
            fields = entry.get("fields", {})
            url = (fields.get("url") or "").strip()
            title = (fields.get("title") or "").strip()
            if not url or not title:
                continue
            articles.append(
                RawArticle(
                    url=url,
                    title=title,
                    source_name=self.name,
                    published_at=_parse_created(fields),
                )
            )
        return articles


def _parse_created(fields: dict):
    from datetime import datetime

    raw = (fields.get("date") or {}).get("created")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
