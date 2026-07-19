"""FastAPI application factory for the Route Agent."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from route_agent import __version__
from route_agent.routes import router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Vorentice Route Agent", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        # Any localhost/127.0.0.1 port — the frontend dev server and the QA
        # preview are assigned ports dynamically, so match the whole range.
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.state.fred_api_key = os.getenv("FRED_API_KEY", "")
    if app.state.fred_api_key:
        logger.info("Route Agent: FRED key present — live Brent cost framing enabled")
    else:
        logger.warning("Route Agent: FRED_API_KEY not set — using default basket price")

    app.include_router(router, prefix="/api")
    return app
