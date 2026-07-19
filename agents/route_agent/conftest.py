"""Pytest bootstrap — put the route_agent package dir on sys.path so tests
import it the same way `main.py` does (run from agents/route_agent/)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
