"""Controlled vocabularies for intelligence classification.

These enums are the contract between the News Agent and every downstream
consumer (Risk Agent, dashboard, alerting). Extend deliberately — each
value added here must be handled by consumers.
"""

from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactCategory(StrEnum):
    SUPPLY_DISRUPTION = "supply_disruption"
    GEOPOLITICAL = "geopolitical"
    PRICE_MOVEMENT = "price_movement"
    ROUTE_CLOSURE = "route_closure"
    OPEC_DECISION = "opec_decision"
    SANCTIONS = "sanctions"
    WEATHER = "weather"
    POLICY = "policy"
    OTHER = "other"


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
