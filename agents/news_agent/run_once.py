"""Run one ingestion cycle from the CLI and print the stats.

Usage:  python run_once.py
Honours .env — with no Azure keys (or NEWS_DRY_RUN=true) it uses the
heuristic classifier, so the full pipeline is testable without secrets.
"""

import asyncio
import json
import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

from vorentice_agents.agent.graph import build_news_agent  # noqa: E402
from vorentice_agents.persistence.database import create_db_and_tables  # noqa: E402


async def main() -> None:
    create_db_and_tables()
    agent = build_news_agent()
    stats = await agent.run()
    print("\n=== RUN COMPLETE ===")
    print(json.dumps(dict(stats), indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
