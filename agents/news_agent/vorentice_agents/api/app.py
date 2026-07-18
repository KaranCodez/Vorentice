"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vorentice_agents import __version__
from vorentice_agents.agent.graph import build_news_agent
from vorentice_agents.api.routes import router
from vorentice_agents.persistence.database import create_db_and_tables
from vorentice_agents.persistence.repository import NewsRepository
from vorentice_agents.scheduling.scheduler import AgentScheduler
from vorentice_agents.settings import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        create_db_and_tables()
        repository = NewsRepository()
        agent = build_news_agent(settings, repository=repository)

        app.state.repository = repository
        app.state.news_agent = agent

        scheduler = AgentScheduler(
            agent, interval_minutes=settings.news.run_interval_minutes
        )
        scheduler.start()
        logger.info(
            "news agent scheduled every %d min", settings.news.run_interval_minutes
        )
        try:
            yield
        finally:
            scheduler.shutdown()

    app = FastAPI(
        title="Vorentice Agent Layer",
        version=__version__,
        lifespan=lifespan,
    )
    # Dashboard dev servers; tighten via env/config for production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3100"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app
