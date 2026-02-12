"""FastAPI dependencies for per-user API key extraction."""

from dataclasses import dataclass

from fastapi import Request

from app.config import ANTHROPIC_API_KEY, TMDB_API_KEY


@dataclass
class APIKeys:
    anthropic_key: str
    tmdb_key: str


def get_api_keys(request: Request) -> APIKeys:
    """Extract API keys from request headers, falling back to server env vars."""
    return APIKeys(
        anthropic_key=request.headers.get("X-Anthropic-Key", "") or ANTHROPIC_API_KEY,
        tmdb_key=request.headers.get("X-TMDB-Key", "") or TMDB_API_KEY,
    )
