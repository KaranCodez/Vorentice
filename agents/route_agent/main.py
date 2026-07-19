"""Entrypoint: uvicorn main:app  (or `python main.py` for dev). Port 8002."""

import logging
from pathlib import Path

# Load .env from the agents/ root (one level up), shared with the other agents.
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv

    load_dotenv(env_file)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

from route_agent.app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002)
