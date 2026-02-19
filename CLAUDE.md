# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Name

The project is named **Flickvault** (pyproject.toml, entry points `flickvault-web` and `flickvault-mcp`). The database is `data/flickvault.db`.

## Commands

```bash
# Install dependencies
uv sync

# Run web server (hot reload, port 8000)
uv run python -m app.main
# or
uv run flickvault-web

# Run MCP server (stdio transport)
uv run python -m mcp_server.server
# or
uv run flickvault-mcp

# Docker
docker-compose up --build

# CLI import
uv run python scripts/import_json.py "Collection Name" ~/path/to/movies.json
```

There are no tests in this repo.

## Architecture

**Two-headed architecture**: a single shared data layer (`app/` package) serves two independent entry points:

1. **FastAPI Web App** (`app/main.py`) — HTML UI + REST API on port 8000
2. **MCP Server** (`mcp_server/server.py`) — stdio transport for AI assistant integration

Both share the same SQLite database (`data/flickvault.db`), so writes from either entry point are immediately visible to the other.

```
SQLite DB (data/flickvault.db)
        |
   app/ package (models, crud, schemas, database)
        |               |
  FastAPI Web        MCP Server
  (port 8000)         (stdio)
```

## Key Architectural Details

### Authentication (Web UI only)
- JWT tokens stored in cookies (or `Authorization: Bearer` header)
- `app/auth.py` — password hashing (bcrypt) and JWT encode/decode
- `app/dependencies.py` — `get_current_user` (raises 401) and `get_optional_user` (returns None, used for redirect-to-login pages)
- The MCP server does NOT use JWT auth — it accepts `user_id: int` directly as a parameter on every tool

### Data Models (`app/models.py`)
- **User**: `id`, `username` (unique), `password_hash`
- **Collection**: `id`, `name`, `description`, `media_type` ("movie"|"show"), `parent_id` (self-referential FK for "More like this" lineage), `min_rating`, `user_id`. Unique constraint: `(user_id, name)`.
- **Movie**: `id`, `title`, `year`, `trakt_id` (unique), `imdb_id` (unique), `tmdb_id`, `overview`, `poster_url`, `rating`, `media_type`
- **CollectionMovie**: junction table with `sort_order`. Unique constraint: `(collection_id, movie_id)`. Cascade delete from Collection.

No migration system — uses `Base.metadata.create_all()`. Schema changes require recreating the database or manual SQL migration.

### CRUD Layer (`app/crud.py`)
All functions accept `user_id: int` to scope data to the authenticated user. All collection queries filter by `user_id`.

Key behaviors:
- `find_or_create_movie()` deduplicates by `trakt_id` first, then `imdb_id`, and updates existing fields when re-imported
- `add_movie_to_collection()` enforces `media_type` matching between movie and collection
- `get_ancestor_movie_titles()` walks the `parent_id` chain for "More like this" exclusion logic
- `get_collections()` fetches up to 4 poster URLs per collection in a single extra query for the grid UI

### AI Generation (`app/ai_generate.py`)
- Uses `anthropic` SDK (model: `claude-sonnet-4-5-20250929`) to generate movie/show lists from a natural language prompt
- Calls TMDB API (`app/tmdb.py`) to enrich each result with `tmdb_id`, `imdb_id`, `poster_url`, `overview`, `rating`
- `generate_collection_iter()` is a generator yielding `{"type": "progress"}` and `{"type": "result"}` events
- When `min_rating` is set, runs up to 5 rounds to gather enough titles that pass the rating filter
- When `source_collection_id` is set, excludes all titles from that collection and its ancestors (lineage chain via `parent_id`)

### Generate Router (`app/routers/generate.py`)
- `POST /api/collections/generate` — returns a `StreamingResponse` with SSE events: `progress`, `complete`, `error`
- Router is registered before the collections router in `app/main.py` to avoid `/generate` matching `/{collection_id}`

### MCP Server (`mcp_server/server.py`)
- 10 tools registered with `@mcp.tool()` via `FastMCP`
- All tools return JSON strings; errors are `{"error": "..."}` not exceptions
- DB sessions managed manually with `_get_db()` + `try/finally db.close()`
- Tool 10 (`generate_collection`) calls `ai_generate_collection()` synchronously (non-streaming)

### Configuration (`app/config.py`)
| Env Var | Default | Purpose |
|---|---|---|
| `DATABASE_PATH` | `data/flickvault.db` | SQLite file path |
| `ANTHROPIC_API_KEY` | `""` | Required for AI generation |
| `TMDB_API_KEY` | `""` | Required for movie enrichment |
| `JWT_SECRET` | `"change-me-in-production-please!!"` | JWT signing key |
| `JWT_EXPIRATION_HOURS` | `720` (30 days) | Token lifetime |
| `SECURE_COOKIES` | `"true"` | Set `False` for local HTTP dev |

### Web UI
- Jinja2 server-rendered templates with Pico.css v2 (CDN, classless)
- All forms submit via JavaScript `fetch()` to the REST API — no traditional form POSTs
- Generate page uses `EventSource` to consume SSE from `/api/collections/generate`

### JSON Import Format
The `_extract_movies()` / `_normalize()` helpers (duplicated in `mcp_server/server.py`, `app/routers/movies.py`, and `scripts/import_json.py`) support:
- Plain JSON arrays of movie objects
- Trakt watchlist format with `already_added` and/or `remaining` keys
