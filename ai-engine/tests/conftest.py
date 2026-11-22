import os
import sys
from pathlib import Path

# testy są deterministyczne i offline: embeddingi haszowane, bez LLM
os.environ["IW_EMBED_ENGINE"] = "hashing"
os.environ["IW_LLM_ENGINE"] = "none"
os.environ["IW_ENV_FILE"] = os.devnull
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from iw_ai.registry import registry  # noqa: E402

REGISTRY = {"version": "test", "entities": [
    {"id": 1, "name": "Vistula Dom Maklerski S.A.", "aliases": ["Vistula Trade"], "domains": ["vistula-dm.test"],
     "category": "dom_maklerski", "authorized": True},
    {"id": 2, "name": "Bank Nadwiślański S.A.", "aliases": ["Bank Nadwiślański"], "domains": ["bank-nadwislanski.test"],
     "category": "bank_maklerski", "authorized": True},
    {"id": 3, "name": "GoldStar Capital Partners", "aliases": [], "domains": ["goldstar-capital.test"],
     "category": "ostrzezenie_knf", "authorized": False},
    {"id": 4, "name": "Jan Kowalski", "aliases": [], "domains": ["agent-kowalski.test"],
     "category": "agent_firmy_inwestycyjnej", "authorized": True},
]}


@pytest.fixture(autouse=True)
def _registry():
    registry.load(REGISTRY)
    yield
