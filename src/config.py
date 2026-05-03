import os
import yaml
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

_root = os.path.dirname(os.path.dirname(__file__))
_cfg_path = os.path.join(_root, "user_config.yaml")
with open(_cfg_path) as f:
    _cfg = yaml.safe_load(f)

OPENROUTER_MODEL    = _cfg.get("openrouter_model", "openrouter/free")
MIN_RELEVANCE_SCORE = _cfg.get("min_relevance_score", 4)
SEARCH_KEYWORDS     = _cfg.get("search_keywords", [])
PROFILE_SUMMARY     = _cfg.get("profile", "").strip()

DB_PATH = os.path.join(_root, "jobs.db")
