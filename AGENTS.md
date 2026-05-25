# AGENTS.md — Project Standards

## Language

**All code, comments, docstrings, variable names, file names, and commit messages must be in English.** Conversations may be in Portuguese, but every produced artifact is English-only.

---

## Code Style

### No `__all__` or re-exports

`__init__.py` files are **empty**. Never use `__all__` or re-import modules inside them. Import directly from the source file:

```python
# ✅ Correct
from voice.auth.token import verify_token
from voice.clients.llm_client import LLMClient

# ❌ Wrong
from voice.auth import verify_token          # __init__.py is empty
from voice.clients import LLMClient          # same
```

### No inline comments unless necessary

If the code is self-explanatory, **do not add comments**. Function names, variable names, and type hints should carry the meaning. Only comment when the "why" is not obvious from the code itself.

```python
# ❌ Unnecessary comment
def verify_token(authorization: str | None) -> None:
    """Verify the Bearer token from the Authorization header."""  # redundant
    if not settings.api_token:
        return

# ✅ Self-explanatory
def verify_token(authorization: str | None) -> None:
    if not settings.api_token:
        return
```

### Pydantic only — never `@dataclass`

**All models use `pydantic.BaseModel`.** Never use `@dataclass`, `NamedTuple`, `TypedDict`, or raw dicts for domain models, request models, response models, or DTOs.

```python
# ✅ Correct
from pydantic import BaseModel

class Turn(BaseModel):
    transcript: str
    assistant_text: str

# ❌ Wrong
from dataclasses import dataclass

@dataclass
class Turn:
    transcript: str
    assistant_text: str
```

---

## Tests

Tests live in `tests/` and mirror the source structure:

```
tests/
├── __init__.py
├── conftest.py
├── models/
│   ├── __init__.py
│   └── test_turn.py
├── services/
│   ├── __init__.py
│   └── test_llm_service.py
├── clients/
│   ├── __init__.py
│   └── test_llm_client.py
├── auth/
│   ├── __init__.py
│   └── test_token.py
└── routers/
    ├── __init__.py
    └── test_turns.py
```

**Naming conventions:**
- Files: `test_<module>.py`
- Classes: `Test<ClassName>`
- Methods: `test_<behavior>`
- Fixtures: snake_case, descriptive names

**Rules:**
- Use `pytest` + `pytest-asyncio` for async tests.
- Mock external clients, never call real APIs in unit tests.
- Each test covers one behavior. Name it after the expected outcome.
- `conftest.py` at `tests/` root for shared fixtures.
- Run with: `uv run pytest tests/ -v`

---

## Python Service Layout

Every Python service follows this structure:

```
src/<service>/
├── __init__.py          # empty
├── main.py              # FastAPI app, middleware, lifespan, DI wiring
├── config.py            # pydantic-settings Settings singleton
├── models/              # Domain models (business entities)
│   ├── __init__.py      # empty
│   └── turn.py
├── services/            # Business logic (orchestrates clients → models)
│   ├── __init__.py      # empty
│   └── llm_service.py
├── clients/             # External API clients (transport layer)
│   ├── __init__.py      # empty
│   └── llm_client.py
├── auth/                # Authentication helpers
│   ├── __init__.py      # empty
│   └── token.py
└── routers/             # HTTP endpoints
    ├── __init__.py      # empty
    ├── turns_requests.py
    ├── turns_responses.py
    └── turns_router.py
```

### Naming conventions by layer

| Layer | File pattern | Class naming |
|---|---|---|
| `models/` | `<entity>.py` | `Turn`, `Conversation` (no prefix/suffix) |
| `routers/` | `<feature>_requests.py` | `TextTurnRequest`, `AudioTurnRequest` |
| `routers/` | `<feature>_responses.py` | `TurnResponse`, `HealthResponse` |
| `routers/` | `<feature>_router.py` | `router = APIRouter(...)` |
| `clients/` | `<service>_client.py` | `LLMClient` + internal `*DTO` classes |
| `services/` | `<domain>_service.py` | `LLMService`, `AudioService` |

### `models/` — Domain Models

Single source of truth for business entities. Always `BaseModel`, never `@dataclass`.

```python
from pydantic import BaseModel

class Turn(BaseModel):
    transcript: str
    assistant_text: str
```

### `services/` — Business Logic

Services consume domain models only. They call clients, receive DTOs, and convert to domain data. Services **never import router models or client internals beyond the client public API**.

```python
from voice.clients.llm_client import LLMClient

class LLMService:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def generate_reply(self, transcript: str) -> str:
        dto = await self._client.chat(...)
        return dto.content
```

### `clients/` — External API Clients

Clients handle transport: HTTP calls, retries, timeouts, auth headers. Each client defines its own internal `*DTO` classes. These **never leak** into services or routers.

**LLM client pattern** (follow the dietgen / goshare reference):

```python
class LLMClient:
    # Low-level: accepts full payload dict, returns raw JSON
    async def chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    # High-level: builds standard payload, returns DTO
    async def chat(self, messages: list[dict[str, str]]) -> ChatCompletionDTO: ...
```

Key decisions:
- Uses `httpx.AsyncClient` directly (not the `openai` SDK).
- Auth: `Authorization: Bearer {password}` header.
- `chat()` always sends `chat_template_kwargs: {"enable_thinking": False}` to disable reasoning mode.
- `max_tokens: 2048` as default.
- Logging via `logging.getLogger(__name__)` with structured messages.

### `routers/` — HTTP Endpoints

Request and response schemas are **separate files** named after the feature:

```python
# turns_requests.py
from pydantic import BaseModel

class TextTurnRequest(BaseModel):
    message: str

# turns_responses.py
from pydantic import BaseModel

class TurnResponse(BaseModel):
    transcript: str
    assistant_text: str
```

Route handlers live in `<feature>_router.py` and use `Depends()` for service injection.

### Dependency Injection — no circular imports

Routers must not import `main.py` (circular). Use a **factory registration pattern**:

```python
# turns_router.py
_llm_factory: Callable[[], LLMService] | None = None

def register_llm(factory: Callable[[], LLMService]) -> None:
    global _llm_factory
    _llm_factory = factory

def get_llm_service() -> LLMService:
    if _llm_factory is None:
        raise RuntimeError("LLMService not registered.")
    return _llm_factory()

@router.post("/text", response_model=TurnResponse)
async def turn_text(
    request: TextTurnRequest,
    llm: LLMService = Depends(get_llm_service),
) -> TurnResponse: ...
```

```python
# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    client = LLMClient()
    app.state.llm_client = client
    register_llm(lambda: LLMService(client=client))
    yield
    await client.close()
```

---

## Layer Dependency Rules

```
routers  →  services  →  clients
    ↓           ↓            ↓
 requests    models      DTOs
 responses
```

| From → To | Allowed? |
|---|---|
| router → service | ✅ (converts router models to domain models) |
| service → client | ✅ (converts client DTOs to domain data) |
| service → models | ✅ (domain models are the contract) |
| client → models | ❌ (clients use their own DTOs) |
| service → router models | ❌ (services know nothing about HTTP) |
| router → models | ❌ (routers go through services) |
| main → router | ✅ (wires DI at startup) |
| router → main | ❌ (circular import) |

---

## Docker & Build

- **Backend**: `uv` manages dependencies. Dockerfile copies `src/` before `uv sync`.
- **Frontend**: Next.js with `output: "standalone"` for minimal Docker images.
- **`.dockerignore`** excludes `node_modules/`, `.next/`, `data/`, `.venv/`.
- **`docker-compose.yml`** orchestrates both services. `extra_hosts` for `host.docker.internal`.
- **`pyproject.toml`** uses `hatchling` with `[tool.hatch.build.targets.wheel] packages = ["src/<service>"]`.

---

## General Rules

- **One responsibility per file.** Split large files early.
- **No circular imports.** If you need them, the layering is wrong.
- **Settings live in `config.py`** using `pydantic-settings`.
- **`main.py` wires everything** (app, middleware, lifespan, DI registration).
- **Use `uv`** for dependency management and running commands.
- **Type hints everywhere.** No `Any` unless unavoidable.
- **Logging via `logging.getLogger(__name__)`**, not `print()`.
- **`__init__.py` files are empty.** No `__all__`, no re-exports.
- **Pydantic only for all models.** No `@dataclass`, `NamedTuple`, or `TypedDict`.
- **All code and comments in English.**
