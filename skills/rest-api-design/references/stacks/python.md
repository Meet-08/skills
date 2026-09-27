# Python — FastAPI, Django REST Framework, Flask

Python 3.11+, type hints throughout.

## Choosing
- **FastAPI** — default: Pydantic validation, async, generates OpenAPI (compare it against the approved `openapi.yaml`; the approved contract wins).
- **Django REST Framework** — when there's an existing Django project or the user wants admin/ORM batteries.
- **Flask** (+ `flask-smorest` or `apiflask`) — small services or existing Flask code.

## Layout (FastAPI)
```
app/
  main.py                  # create_app(): routers, middleware, exception handlers
  config.py                # pydantic-settings
  api/v1/<resource>.py     # APIRouter; HTTP concerns only
  schemas/<resource>.py    # Pydantic: OrderCreate, OrderUpdate, Order
  services/<resource>.py   # business logic, raises domain errors
  repositories/<resource>.py  # Protocol + in-memory impl
  core/errors.py           # AppError + Problem Details handlers
  core/security.py         # JWT verification dependency
tests/
openapi.yaml
```
DRF: app per resource with `serializers.py`, `views.py` (ViewSets or APIViews), `urls.py`; custom `EXCEPTION_HANDLER` for Problem Details; custom pagination class for cursor pages (DRF's `CursorPagination` is a good base — rename fields to match the contract).

## Libraries
| Need | Choice |
|---|---|
| Validation | Pydantic v2 (`model_config = ConfigDict(extra='forbid')` on inputs) |
| Settings | pydantic-settings |
| Auth | `PyJWT` or `python-jose` with JWKS; FastAPI `Security` dependencies with scopes |
| Rate limit | `slowapi` |
| Logging | `structlog` + request-ID middleware |
| Tests | `pytest` + `httpx.AsyncClient` / `TestClient` |
| Contract tests | `schemathesis` (property-based tests generated from `openapi.yaml`) |

## Problem Details (FastAPI)
```python
class AppError(Exception):
    def __init__(self, status: int, type_: str, title: str, detail: str | None = None, errors=None):
        self.status, self.type, self.title, self.detail, self.errors = status, type_, title, detail, errors

def problem(request: Request, status: int, type_: str, title: str, detail=None, errors=None):
    body = {"type": type_, "title": title, "status": status, "instance": request.url.path,
            "traceId": request.state.request_id}
    if detail: body["detail"] = detail
    if errors: body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type="application/problem+json")

@app.exception_handler(AppError)
async def app_error(req, exc): return problem(req, exc.status, exc.type, exc.title, exc.detail, exc.errors)

@app.exception_handler(RequestValidationError)
async def validation(req, exc):
    errs = [{"field": ".".join(map(str, e["loc"][1:])), "code": e["type"], "message": e["msg"]} for e in exc.errors()]
    return problem(req, 422, f"{BASE}/validation-error", "Validation failed", errors=errs)

@app.exception_handler(StarletteHTTPException)   # 404/405 from routing
async def http_error(req, exc): return problem(req, exc.status_code, "about:blank", exc.detail)

@app.exception_handler(Exception)
async def unhandled(req, exc):
    log.exception("unhandled"); return problem(req, 500, "about:blank", "Internal Server Error")
```

## Patterns
- **Status codes**: set explicitly (`status_code=201`, `204` with `Response(status_code=204)`); FastAPI's default 200 is often wrong.
- **Location**: `response.headers["Location"] = f"/v1/orders/{order.id}"`.
- **camelCase JSON** with snake_case Python: `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)` and `response_model_by_alias=True`.
- **PATCH**: `payload.model_dump(exclude_unset=True)` to apply only sent fields.
- **Cursor pagination**: base64url JSON of `(created_at, id)`; fetch `limit + 1`.
- Don't use FastAPI's auto-generated spec as the contract; serve the approved `openapi.yaml` (set `app.openapi = lambda: yaml.safe_load(...)`) or diff the two in CI.

## Tests
pytest per endpoint (happy + error) and `schemathesis run openapi.yaml --base-url=...` to catch contract drift.
