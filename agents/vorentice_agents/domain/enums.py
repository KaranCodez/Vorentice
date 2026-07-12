"""Controlled vocabularies for intelligence classification.

These enums are the contract between the News Agent and every downstream
consumer (Risk Agent, dashboard, alerting). Extend deliberately — each
value added here must be handled by consumers.

Per the project charter, the News Agent monitors ALL domains that affect
supply security — wars, oil markets, weather, ports, sanctions, military
incidents — not any single route or scenario. `ImpactCategory` is the
fine-grained label the classifier assigns; `NewsSegment` is the coarser
operator-facing grouping the briefing and dashboard use.
"""

from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


#: Ranking helper — higher index = more severe.
SEVERITY_ORDER: dict[str, int] = {
    Severity.LOW.value: 0,
    Severity.MEDIUM.value: 1,
    Severity.HIGH.value: 2,
    Severity.CRITICAL.value: 3,
}


class ImpactCategory(StrEnum):
    # Energy & markets
    SUPPLY_DISRUPTION = "supply_disruption"
    PRICE_MOVEMENT = "price_movement"
    OPEC_DECISION = "opec_decision"
    # Trade restrictions
    SANCTIONS = "sanctions"
    # Logistics
    PORT_OPERATIONS = "port_operations"     # closures, congestion, strikes
    ROUTE_CLOSURE = "route_closure"         # chokepoint/canal blockage
    # Conflict & security
    GEOPOLITICAL = "geopolitical"           # political threats, tensions
    ARMED_CONFLICT = "armed_conflict"       # wars, declared hostilities
    MILITARY_SECURITY = "military_security" # missile/drone attacks, piracy
    # Environment & policy
    WEATHER = "weather"
    POLICY = "policy"
    OTHER = "other"


class NewsSegment(StrEnum):
    """Operator-facing grouping for the briefing view."""

    ENERGY_MARKETS = "energy_markets"
    WEATHER = "weather"
    SANCTIONS_TRADE = "sanctions_trade"
    PORTS_SHIPPING = "ports_shipping"
    ROUTES_CHOKEPOINTS = "routes_chokepoints"
    WAR_GEOPOLITICS = "war_geopolitics"
    MILITARY_SECURITY = "military_security"
    OTHER = "other"


#: Fine category -> operator segment. Every ImpactCategory MUST map.
CATEGORY_TO_SEGMENT: dict[str, NewsSegment] = {
    ImpactCategory.SUPPLY_DISRUPTION.value: NewsSegment.ENERGY_MARKETS,
    ImpactCategory.PRICE_MOVEMENT.value: NewsSegment.ENERGY_MARKETS,
    ImpactCategory.OPEC_DECISION.value: NewsSegment.ENERGY_MARKETS,
    ImpactCategory.SANCTIONS.value: NewsSegment.SANCTIONS_TRADE,
    ImpactCategory.PORT_OPERATIONS.value: NewsSegment.PORTS_SHIPPING,
    ImpactCategory.ROUTE_CLOSURE.value: NewsSegment.ROUTES_CHOKEPOINTS,
    ImpactCategory.GEOPOLITICAL.value: NewsSegment.WAR_GEOPOLITICS,
    ImpactCategory.ARMED_CONFLICT.value: NewsSegment.WAR_GEOPOLITICS,
    ImpactCategory.MILITARY_SECURITY.value: NewsSegment.MILITARY_SECURITY,
    ImpactCategory.WEATHER.value: NewsSegment.WEATHER,
    ImpactCategory.POLICY.value: NewsSegment.OTHER,
    ImpactCategory.OTHER.value: NewsSegment.OTHER,
}

SEGMENT_LABELS: dict[NewsSegment, str] = {
    NewsSegment.ENERGY_MARKETS: "Oil & Energy Markets",
    NewsSegment.WEATHER: "Weather Events",
    NewsSegment.SANCTIONS_TRADE: "Sanctions & Trade Restrictions",
    NewsSegment.PORTS_SHIPPING: "Ports & Shipping Operations",
    NewsSegment.ROUTES_CHOKEPOINTS: "Routes & Chokepoints",
    NewsSegment.WAR_GEOPOLITICS: "Wars & Geopolitical Conflicts",
    NewsSegment.MILITARY_SECURITY: "Military & Security Incidents",
    NewsSegment.OTHER: "Other Developments",
}


def segment_of(impact_category: str) -> NewsSegment:
    """Map a stored category string to its segment (OTHER on unknowns,
    so legacy rows and future categories never break the briefing)."""
    return CATEGORY_TO_SEGMENT.get(impact_category, NewsSegment.OTHER)


class Region(StrEnum):
    MIDDLE_EAST = "middle_east"
    RUSSIA_CIS = "russia_cis"
    WEST_AFRICA = "west_africa"
    NORTH_AMERICA = "north_america"
    SOUTH_AMERICA = "south_america"
    ASIA_PACIFIC = "asia_pacific"
    INDIA = "india"
    EUROPE = "europe"
    GLOBAL = "global"


# Named maritime chokepoints relevant to Indian crude imports.
# Used both by the pre-filter heuristics and the LLM output schema.
CHOKEPOINTS: tuple[str, ...] = (
    "Strait of Hormuz",
    "Strait of Malacca",
    "Suez Canal",
    "Bab el-Mandeb",
    "Bosporus",
    "Cape of Good Hope",
    "Danish Straits",
    "Panama Canal",
)
