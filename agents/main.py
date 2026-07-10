"""Entrypoint: uvicorn main:app  (or `python main.py` for dev)."""

import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
# httpx logs every request at INFO; keep the signal-to-noise ratio sane.
logging.getLogger("httpx").setLevel(logging.WARNING)

from vorentice_agents.api.app import create_app  # noqa: E402

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
