import os
import sys
import tempfile
from pathlib import Path

# izolowana baza i magazyn obiektów dla testów
_tmp = tempfile.mkdtemp(prefix="iw_test_")
os.environ["IW_DATA_DIR"] = _tmp
os.environ["IW_ENV_FILE"] = os.devnull
os.environ["IW_INTERNAL_TOKEN"] = "test-token"
os.environ["IW_REGISTRY_SOURCES"] = "demo"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
