# Vorentice Agent Layer

Phase 2 of Vorentice — the autonomous agent backend. Currently ships the
**News Agent**: 24/7 global supply-chain and geopolitical news monitoring —
a complete newspaper replacement for its users.

## The product: a three-section intelligence report

`GET /api/news/report` is the agent's primary output, structured per the
charter:

1. **The Daily Brief** — a narrative roundup for EVERY one of the 8
   monitored categories (quiet categories included, stated explicitly),
   so the user never needs to consult another newspaper.
2. **Critical Events Tracker** — every significant disruptive event
   across all categories (never capped to one per category), each with
   its category, event summary, qualitative criticality level, and its
   logistics/trade impact right now.
3. **Emerging Threats (Watchlist)** — events that are NOT critical yet
   but could escalate, with why they are watched and the concrete
   triggers that would make them critical.

Charter rules enforced end-to-end: **no numeric risk scores anywhere**
(urgency is Critical / High / Moderate / Low / Emerging), and **no
anchoring** on any single route, region or scenario.

## Architecture

Deterministic LangGraph pipeline; the LLM is an enrichment stage, never the
controller:

```
fetch ──► dedup ──► prefilter ──┬─► classify ──► persist ──► digest ──► alerts
  articles + signals  (keyword,  └─────────────► persist    (Daily Brief
                       cost guard)   (Azure OpenAI, batched   composer)
                                      structured output)
```

**Coverage is multi-domain by charter** — the agent monitors the 8
categories worldwide: Oil Pricing & Energy Markets · Weather Events
Affecting Shipping & Trade · Sanctions & Trade Restrictions · Ports &
Shipping Operations · Route Blockages & Disruptions · Wars & Geopolitical
Conflicts · Missile Attacks, Military Activity & Security Incidents ·
Global Logistics & Supply Chain.

**Classification** (Azure OpenAI, structured output) now also produces,
per item: the current **logistics/trade impact**, and the **watchlist
call** — escalation potential, why it is watched, and the concrete
escalation triggers. The **digest stage** composes the Daily Brief (one
narrative per category from the window's stored items) after each cycle
that stores new items; a failure there never fails the run — the previous
edition stays current.

**Two source families, one feed:**
- **Article sources** → `RawArticle`, judged by the LLM: GDELT DOC (10
  standing queries, one per domain), OilPrice, Oil & Gas Journal, gCaptain,
  Maritime Executive, Al Jazeera, Google News sweeps (ports & conflict,
  true publisher attributed per entry), CSIS, ET EnergyWorld, EIA Today,
  PIB/MoPNG. A 7-day freshness gate drops stale search results (the 2021
  Suez story must never page as breaking news). (ReliefWeb ready but
  dormant until an approved appname is set.)
- **Signal sources** → `ClassifiedArticle`, judged by deterministic rules
  (no LLM, exact numbers): **EIA** crude stocks, **FRED** Brent/WTI prices,
  **Open-Meteo** sea state at the chokepoints, **OpenSanctions** newly
  listed oil entities/tankers. Each folds into the feed as a synthesized
  intel item (e.g. `EIA: U.S. crude stocks drew down 4.2M bbl`).

**Dedup is three-layered**: exact URL hash (in-batch + store), then
near-duplicate headline matching (token-set Jaccard). A near-dup from a
*different* outlet is folded into the stored item as **corroboration**.
Signals dedup on a canonical id (`eia://SERIES/PERIOD`) so a data point is
stored once.

**Alerting — two complementary gates, both run every cycle:**
1. *per-item* — critical fires when it's a trusted deterministic signal
   (EIA/FRED/Open-Meteo), an official government outlet (PIB), or already
   corroborated by ≥2 independent sources.
2. *event corroboration* — when ≥2 independent sources file **critical**
   reports about the **same event** (same chokepoint when tagged, else same
   segment + region), that is a real event and pages once, with provenance.
   Multiple simultaneous crises each raise their own alert — a war
   escalation, a canal blockage and a port shutdown happening at once
   produce three distinct pages, never a single headline event. Missing a
   real crisis is the worst failure mode for a supply-security system, so
   this path is deliberately sensitive while still requiring source
   independence.

A lone LLM-classified critical from a single outlet never pages on its own —
single-headline severity is the least trustworthy signal.

- **Sources** (all free, metadata-only): GDELT DOC 2.0, OilPrice, Oil & Gas
  Journal, EIA, PIB/MoPNG (Government of India). Each sits behind the
  `NewsSource` ABC — adding Refinitiv/Factiva later is one adapter class.
- **Storage**: SQLite in dev, Azure PostgreSQL in prod (swap `DATABASE_URL`).
- **Degradation path**: if Azure OpenAI is unconfigured or down, a heuristic
  classifier keeps ingestion alive (items marked `classified_by=heuristic`).

## Package layout

```
vorentice_agents/
├── settings.py       # pydantic-settings, env-driven (Azure + source keys)
├── domain/           # enums, models (frozen pydantic), graph state
├── sources/          # NewsSource ABC + GDELT/RSS/ReliefWeb adapters
│   └── signals/      # SignalSource ABC + EIA/FRED/Open-Meteo (deterministic)
├── pipeline/         # deduplicator, prefilter, classifier, digest, alerts
├── persistence/      # SQLModel tables, repository (only module with SQL)
├── agent/            # LangGraph nodes + graph assembly (composition root)
├── api/              # FastAPI routes: /news/latest, /news/stream (SSE), …
└── scheduling/       # APScheduler wrapper (30-min cycle, no overlap)
```

## Run

```powershell
cd agents
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env    # fill in Azure OpenAI keys

# one ingestion cycle, prints stats:
.venv\Scripts\python run_once.py

# API + scheduler (http://127.0.0.1:8000/docs):
.venv\Scripts\python main.py
```

No keys yet? Set `NEWS_DRY_RUN=true` (or just leave the Azure vars empty) —
the pipeline runs end-to-end with the heuristic classifier.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

## Endpoints

| Method | Path                | Purpose                              |
|--------|---------------------|--------------------------------------|
| GET    | `/api/health`       | Liveness probe                       |
| GET    | `/api/news/report`  | **The three-section intelligence report** — Daily Brief, Critical Events Tracker, Emerging Threats (`hours`) |
| GET    | `/api/news/briefing`| Situation briefing grouped by segment (`hours`, `min_severity`) |
| GET    | `/api/news/latest`  | Recent items (`limit`, `min_relevance`, `severity`) |
| GET    | `/api/news/stream`  | SSE push of newly stored items       |
| GET    | `/api/news/alerts`  | Raised alerts with their items       |
| GET    | `/api/news/sources` | Per-source ingestion health (ops)    |
| GET    | `/api/news/runs`    | Pipeline run history (ops)           |
| POST   | `/api/news/trigger` | Run the pipeline now                 |
