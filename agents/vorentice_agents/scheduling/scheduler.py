"""Recurring execution of the News Agent.

AsyncIOScheduler shares the API's event loop — one process serves HTTP
and runs the pipeline. In production this maps to one Azure Container
App; if scale demands it later, the scheduler moves to its own container
without code changes here.

`max_instances=1` + `coalesce=True` guarantee runs never overlap and
missed runs (e.g. during a deploy) collapse into one catch-up run.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from vorentice_agents.agent.graph import NewsAgent

logger = logging.getLogger(__name__)


class AgentScheduler:
    def __init__(self, agent: NewsAgent, interval_minutes: int) -> None:
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            agent.run,
            IntervalTrigger(minutes=interval_minutes),
            id="news_agent_run",
            max_instances=1,
            coalesce=True,
        )

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
