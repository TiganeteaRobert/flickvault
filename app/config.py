import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "flickvault.db"))
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.2")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "https://flickvault.fly.dev")
OPENROUTER_APP_TITLE = os.environ.get("OPENROUTER_APP_TITLE", "Flickvault")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production-please!!")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "720"))  # 30 days
SECURE_COOKIES = os.environ.get("SECURE_COOKIES", "true").lower() == "true"
