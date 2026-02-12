import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = os.environ.get("DATABASE_PATH", str(DATA_DIR / "flickvault.db"))
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
