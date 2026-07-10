"""Source registry — the one place that declares "what do we watch".

Two families:
- article sources  -> RawArticle, judged by the LLM (GDELT, RSS, ReliefWeb)
- signal sources   -> ClassifiedArticle, judged by deterministic rules
                      (EIA, FRED, Open-Meteo)

Every entry is free and license-safe. A source whose key/appname is not
configured is simply omitted here — the pipeline never sees it, so no
error noise while credentials are pending.
"""

import logging

from vorentice_agents.settings import ExternalSourcesSettings, NewsAgentSettings
from vorentice_agents.sources.base import NewsSource
from vorentice_agents.sources.gdelt import GdeltDocSource
from vorentice_agents.sources.reliefweb import ReliefWebSource
from vorentice_agents.sources.rss import RssSource
from vorentice_agents.sources.signals import (
    ChokepointWeatherSignal,
    EiaCrudeStocksSignal,
    FredOilPriceSignal,
    OpenSanctionsSignal,
)
from vorentice_agents.sources.signals.base import SignalSource

logger = logging.getLogger(__name__)

_DEFAULT_RELIEFWEB_APPNAME = "vorentice-news-agent"

# name -> feed URL. Names are stable identifiers used in stats & the DB.
RSS_FEEDS: dict[str, str] = {
    # Energy trade press
    "oilprice": "https://oilprice.com/rss/main",
    "ogj_general": (
        "https://www.ogj.com/__rss/website-scheduled-content.xml"
        "?input=%7B%22sectionAlias%22%3A%22general-interest%22%7D"
    ),
    "ogj_pipelines": (
        "https://www.ogj.com/__rss/website-scheduled-content.xml"
        "?input=%7B%22sectionAlias%22%3A%22pipelines-transportation%22%7D"
    ),
    # Think-tank analysis
    "csis": "https://www.csis.org/rss.xml",
    # India energy press — ET EnergyWorld oil & gas desk
    "et_energyworld": "https://energy.economictimes.indiatimes.com/rss/oil-and-gas",
    # Official / statistical
    "eia_today": "https://www.eia.gov/rss/todayinenergy.xml",
    # Government of India — Ministry of Petroleum & Natural Gas releases
    "pib_mopng": "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
}


def build_default_sources(settings: NewsAgentSettings) -> list[NewsSource]:
    """Assemble the article source set (RawArticle producers)."""
    sources: list[NewsSource] = [
        GdeltDocSource(timespan=settings.gdelt_timespan),
    ]
    sources.extend(
        RssSource(name=name, feed_url=url) for name, url in RSS_FEEDS.items()
    )
    return sources


def build_article_sources(
    news: NewsAgentSettings, external: ExternalSourcesSettings
) -> list[NewsSource]:
    """Article sources, including credential-gated ones when configured."""
    sources = build_default_sources(news)
    if external.reliefweb_appname != _DEFAULT_RELIEFWEB_APPNAME and (
        external.reliefweb_appname
    ):
        sources.append(ReliefWebSource(appname=external.reliefweb_appname))
    else:
        logger.info(
            "reliefweb dormant — set an approved RELIEFWEB_APPNAME to enable"
        )
    return sources


def build_signal_sources(
    external: ExternalSourcesSettings,
) -> list[SignalSource]:
    """Signal sources (deterministic ClassifiedArticle producers).

    Only enabled sources are returned; each self-reports readiness via
    is_enabled() (i.e. its key is present)."""
    candidates: list[SignalSource] = [
        EiaCrudeStocksSignal(api_key=external.eia_api_key),
        FredOilPriceSignal(api_key=external.fred_api_key),
        ChokepointWeatherSignal(),  # keyless, always enabled
        OpenSanctionsSignal(api_key=external.opensanctions_api_key),
    ]
    enabled = [s for s in candidates if s.is_enabled()]
    dormant = [s.name for s in candidates if not s.is_enabled()]
    if dormant:
        logger.info("signal sources dormant (no key): %s", ", ".join(dormant))
    return enabled
