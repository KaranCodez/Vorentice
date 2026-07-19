"""FastAPI application factory for the Risk Agent."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from risk_agent import __version__
from risk_agent.chat_engine import RiskChatEngine
from risk_agent.routes import router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    fred_api_key = os.getenv("FRED_API_KEY", "")
    eia_api_key = os.getenv("EIA_API_KEY", "")
    serper_api_key = os.getenv("SERPER_API_KEY", "")

    app = FastAPI(
        title="Vorentice Risk Agent",
        version=__version__,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3100"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.state.fred_api_key = fred_api_key
    app.state.eia_api_key = eia_api_key

    if fred_api_key:
        logger.info("Risk Agent: FRED API key present — live market data enabled")
    else:
        logger.warning("Risk Agent: FRED_API_KEY not set — live market data will be partial")

    if eia_api_key:
        logger.info("Risk Agent: EIA API key present — crude inventory signal enabled")
    else:
        logger.warning("Risk Agent: EIA_API_KEY not set — crude inventory signal disabled")

    if serper_api_key:
        logger.info("Risk Agent: Serper API key present — web search tool enabled")
    else:
        logger.warning("Risk Agent: SERPER_API_KEY not set — web search tool disabled")

    if endpoint and api_key:
        app.state.chat_engine = RiskChatEngine(
            endpoint=endpoint,
            api_key=api_key,
            deployment=deployment,
            api_version=api_version,
            serper_api_key=serper_api_key,
        )
        logger.info("Risk Agent: Azure OpenAI configured (deployment=%s)", deployment)
    else:
        logger.warning(
            "Risk Agent: Azure OpenAI not configured — set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY"
        )
        app.state.chat_engine = None

    app.include_router(router, prefix="/api")
    return app
