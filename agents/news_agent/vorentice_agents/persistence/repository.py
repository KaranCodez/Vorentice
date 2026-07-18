"""Repository — the only module that speaks SQL.

Pipeline stages and API routes depend on this interface, never on
SQLModel sessions directly, so the storage engine can evolve (Postgres,
pgvector, partitioning) behind a stable seam.
"""

import json
from datetime import datetime, timedelta, timezone

from sqlmodel import col, select

from vorentice_agents.domain.models import ClassifiedArticle
from vorentice_agents.domain.state import RunStats
from vorentice_agents.persistence.database import open_session
from vorentice_agents.persistence.tables import (
    AgentRunRow,
    AlertRow,
    NewsItemRow,
    SegmentDigestRow,
)


class NewsRepository:
    """Persistence operations for the News Agent."""

    def existing_dedup_keys(self, keys: list[str]) -> set[str]:
        """Return the subset of `keys` already stored."""
        if not keys:
            return set()
        with open_session() as session:
            rows = session.exec(
                select(NewsItemRow.dedup_key).where(
                    col(NewsItemRow.dedup_key).in_(keys)
                )
            ).all()
        return set(rows)

    def recent_titles(self, hours: int = 72) -> list[tuple[int, str]]:
        """(id, title) of items fetched in the window — near-dup candidates."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with open_session() as session:
            rows = session.exec(
                select(NewsItemRow.id, NewsItemRow.title).where(
                    NewsItemRow.fetched_at >= cutoff
                )
            ).all()
        return [(row_id, title) for row_id, title in rows if row_id is not None]

    def add_corroboration(self, item_id: int, source_name: str) -> None:
        """Record an independent sighting of an already-stored story."""
        with open_session() as session:
            row = session.get(NewsItemRow, item_id)
            if row is None:
                return
            sources = set(filter(None, row.corroborating_sources.split(",")))
            if source_name in sources or source_name == row.source_name:
                return  # same outlet repeating itself is not corroboration
            sources.add(source_name)
            row.corroborating_sources = ",".join(sorted(sources))
            row.corroboration_count = 1 + len(sources)
            session.add(row)
            session.commit()

    def store_classified(self, items: list[ClassifiedArticle]) -> int:
        """Insert classified articles; returns number actually written."""
        if not items:
            return 0
        written = 0
        with open_session() as session:
            known = self.existing_dedup_keys(
                [item.article.dedup_key for item in items]
            )
            for item in items:
                if item.article.dedup_key in known:
                    continue
                session.add(_to_row(item))
                written += 1
            session.commit()
        return written

    def latest_items(
        self,
        limit: int = 50,
        min_relevance: float = 0.0,
        severity: str | None = None,
    ) -> list[NewsItemRow]:
        with open_session() as session:
            query = (
                select(NewsItemRow)
                .where(NewsItemRow.relevance_score >= min_relevance)
                .order_by(col(NewsItemRow.fetched_at).desc())
                .limit(limit)
            )
            if severity:
                query = query.where(NewsItemRow.severity == severity)
            rows = list(session.exec(query).all())
        # Within one ingestion cycle fetched_at differs only by µs, which
        # makes raw time-order arbitrary. Bucket to the minute so the
        # newest batch still leads, but best intel leads *within* it.
        rows.sort(
            key=lambda r: (
                r.fetched_at.replace(second=0, microsecond=0),
                r.relevance_score,
            ),
            reverse=True,
        )
        return rows

    def briefing_items(self, hours: int = 24) -> list[NewsItemRow]:
        """Everything fetched in the briefing window; grouping by segment
        happens at the API layer (segments are presentation, not storage)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with open_session() as session:
            return list(
                session.exec(
                    select(NewsItemRow)
                    .where(NewsItemRow.fetched_at >= cutoff)
                    .order_by(col(NewsItemRow.fetched_at).desc())
                ).all()
            )

    def watchlist_items(self, hours: int = 48) -> list[NewsItemRow]:
        """Emerging Threats (Section 3): items flagged with escalation
        potential that are NOT already critical/high — those belong in
        the Critical Events Tracker, not the watchlist."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with open_session() as session:
            rows = session.exec(
                select(NewsItemRow)
                .where(
                    NewsItemRow.escalation_potential == True,  # noqa: E712
                    col(NewsItemRow.severity).in_(["low", "medium"]),
                    NewsItemRow.fetched_at >= cutoff,
                )
                .order_by(col(NewsItemRow.fetched_at).desc())
            ).all()
        return list(rows)

    def save_digests(self, digests: list[SegmentDigestRow]) -> None:
        """Store one generation of Daily Brief digests (append-only —
        history is cheap and lets operators diff briefs over time)."""
        if not digests:
            return
        with open_session() as session:
            for digest in digests:
                session.add(digest)
            session.commit()

    def latest_digests(self) -> dict[str, SegmentDigestRow]:
        """Most recent digest per segment (across generations)."""
        with open_session() as session:
            rows = session.exec(
                select(SegmentDigestRow).order_by(
                    col(SegmentDigestRow.generated_at).asc()
                )
            ).all()
        # Later generations overwrite earlier ones per segment.
        return {row.segment: row for row in rows}

    def items_since(self, item_id: int) -> list[NewsItemRow]:
        """Items newer than a known id — powers SSE incremental pushes."""
        with open_session() as session:
            return list(
                session.exec(
                    select(NewsItemRow)
                    .where(NewsItemRow.id > item_id)
                    .order_by(col(NewsItemRow.id).asc())
                ).all()
            )

    def unalerted_critical_items(self, hours: int = 48) -> list[NewsItemRow]:
        """Critical items no alert has been raised for yet, within a recent
        window. Scanned every run — so an item that *becomes* eligible
        later (corroboration arrives after storage) is picked up, while
        stale criticals age out of consideration."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with open_session() as session:
            return list(
                session.exec(
                    select(NewsItemRow).where(
                        NewsItemRow.severity == "critical",
                        NewsItemRow.alert_sent == False,  # noqa: E712
                        NewsItemRow.fetched_at >= cutoff,
                    )
                ).all()
            )

    def raise_event_alert(
        self, representative_id: int, item_ids: list[int], reason: str
    ) -> None:
        """Raise one alert for a corroborated event and mark every
        constituent item as alerted so they don't re-fire individually."""
        with open_session() as session:
            representative = session.get(NewsItemRow, representative_id)
            if representative is None or representative.alert_sent:
                # Representative already alerted — still flag the rest.
                pass
            else:
                session.add(AlertRow(news_item_id=representative_id, reason=reason))
            for item_id in item_ids:
                row = session.get(NewsItemRow, item_id)
                if row is not None:
                    row.alert_sent = True
                    session.add(row)
            session.commit()

    def raise_alert(self, item_id: int, reason: str) -> None:
        with open_session() as session:
            item = session.get(NewsItemRow, item_id)
            if item is None or item.alert_sent:
                return
            item.alert_sent = True
            session.add(item)
            session.add(AlertRow(news_item_id=item_id, reason=reason))
            session.commit()

    def recent_alerts(self, limit: int = 50) -> list[tuple[AlertRow, NewsItemRow]]:
        with open_session() as session:
            rows = session.exec(
                select(AlertRow, NewsItemRow)
                .where(AlertRow.news_item_id == NewsItemRow.id)
                .order_by(col(AlertRow.created_at).desc())
                .limit(limit)
            ).all()
            return list(rows)

    def source_health(self) -> list[dict]:
        """Per-source ops view: stored volume and the latest run's errors.
        A source with zero recent items and no error is the silent-death
        case operators must notice."""
        from sqlmodel import func

        with open_session() as session:
            counts = session.exec(
                select(
                    NewsItemRow.source_name,
                    func.count(),
                    func.max(NewsItemRow.fetched_at),
                ).group_by(NewsItemRow.source_name)
            ).all()
            last_run = session.exec(
                select(AgentRunRow).order_by(col(AgentRunRow.started_at).desc())
            ).first()

        errors: dict[str, str] = (
            json.loads(last_run.source_errors) if last_run and last_run.source_errors else {}
        )
        health = [
            {
                "source": name,
                "items_stored": count,
                "last_item_at": last_at.isoformat() if last_at else None,
                "last_error": errors.get(name.split(":")[0]),
            }
            for name, count, last_at in counts
        ]
        # Sources that errored and have stored nothing yet still appear.
        seen = {h["source"].split(":")[0] for h in health}
        for source, error in errors.items():
            if source not in seen:
                health.append(
                    {"source": source, "items_stored": 0,
                     "last_item_at": None, "last_error": error}
                )
        return sorted(health, key=lambda h: h["source"])

    def record_run(self, stats: RunStats, ok: bool) -> None:
        with open_session() as session:
            session.add(
                AgentRunRow(
                    started_at=datetime.fromisoformat(
                        stats.get("started_at", datetime.now(timezone.utc).isoformat())
                    ),
                    finished_at=datetime.now(timezone.utc),
                    ok=ok,
                    fetched=stats.get("fetched", 0),
                    after_dedup=stats.get("after_dedup", 0),
                    after_prefilter=stats.get("after_prefilter", 0),
                    classified=stats.get("classified", 0),
                    stored=stats.get("stored", 0),
                    llm_calls=stats.get("llm_calls", 0),
                    source_errors=json.dumps(stats.get("source_errors", {})),
                )
            )
            session.commit()

    def recent_runs(self, limit: int = 20) -> list[AgentRunRow]:
        with open_session() as session:
            return list(
                session.exec(
                    select(AgentRunRow)
                    .order_by(col(AgentRunRow.started_at).desc())
                    .limit(limit)
                ).all()
            )


def _to_row(item: ClassifiedArticle) -> NewsItemRow:
    article = item.article
    return NewsItemRow(
        dedup_key=article.dedup_key,
        url=article.url,
        title=article.title,
        source_name=article.source_name,
        snippet=article.snippet,
        language=article.language,
        published_at=article.published_at,
        relevance_score=item.relevance_score,
        severity=item.severity.value,
        impact_category=item.impact_category.value,
        region=item.region.value,
        chokepoints=",".join(item.chokepoints),
        summary=item.summary,
        trade_impact=item.trade_impact,
        escalation_potential=item.escalation_potential,
        watchlist_reason=item.watchlist_reason,
        escalation_triggers=item.escalation_triggers,
        classified_by=item.classified_by,
        classified_at=item.classified_at,
    )
