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

    if endpoint and api_key:
        app.state.chat_engine = RiskChatEngine(
            endpoint=endpoint,
            api_key=api_key,
            deployment=deployment,
            api_version=api_version,
        )
        logger.info("Risk Agent: Azure OpenAI configured (deployment=%s)", deployment)
    else:
        logger.warning(
            "Risk Agent: Azure OpenAI not configured — set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY"
        )
        app.state.chat_engine = None

    app.include_router(router, prefix="/api")
    return app
