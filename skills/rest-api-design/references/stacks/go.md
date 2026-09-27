# Go — net/http, chi, Gin, Echo

Go 1.22+ (the standard `http.ServeMux` supports method + path patterns like `GET /v1/orders/{orderId}`).

## Choosing
- **net/http (stdlib)** or **chi** — default; idiomatic, minimal dependencies.
- **Gin / Echo** — when the user names them.
- **Contract-first**: `oapi-codegen` generates a `StrictServerInterface` and types from `openapi.yaml` for stdlib/chi/gin/echo. Strongly recommended — handlers become typed methods and drift becomes a compile error.

## Layout
```
cmd/api/main.go              # wiring: config, repo, service, router, server with timeouts
internal/
  api/                       # generated code (oapi-codegen) + handler impls
  <resource>/service.go      # business logic, returns domain errors
  <resource>/repository.go   # interface + memory impl
  platform/problem/          # Problem Details writer, error → status mapping
  platform/middleware/       # requestID, logging, auth, recover, rateLimit
api/openapi.yaml
```

## Libraries
| Need | Choice |
|---|---|
| Codegen | `github.com/oapi-codegen/oapi-codegen/v2` |
| Request validation | `oapi-codegen` `nethttp-middleware` (kin-openapi validator) |
| JWT | `github.com/lestrrat-go/jwx/v2` (JWKS) |
| Logging | `log/slog` (stdlib) |
| Rate limit | `golang.org/x/time/rate` or `httprate` (chi) |
| Tests | `net/http/httptest`, table-driven |

## Problem Details
```go
type Problem struct {
    Type     string       `json:"type"`
    Title    string       `json:"title"`
    Status   int          `json:"status"`
    Detail   string       `json:"detail,omitempty"`
    Instance string       `json:"instance,omitempty"`
    TraceID  string       `json:"traceId,omitempty"`
    Errors   []FieldError `json:"errors,omitempty"`
}

var ErrNotFound = errors.New("not found")  // domain sentinels; services wrap with %w

func Write(w http.ResponseWriter, r *http.Request, err error) {
    p := Problem{Type: "about:blank", Title: "Internal Server Error", Status: 500}
    var ve *ValidationError
    switch {
    case errors.Is(err, ErrNotFound):
        p = Problem{Type: base + "/not-found", Title: "Resource not found", Status: 404}
    case errors.As(err, &ve):
        p = Problem{Type: base + "/validation-error", Title: "Validation failed", Status: 422, Errors: ve.Fields}
    default:
        slog.ErrorContext(r.Context(), "unhandled", "err", err)
    }
    p.Instance, p.TraceID = r.URL.Path, middleware.RequestID(r.Context())
    w.Header().Set("Content-Type", "application/problem+json")
    w.WriteHeader(p.Status)
    json.NewEncoder(w).Encode(p)
}
```

## Patterns
- **Server timeouts** always: `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout`; graceful shutdown on SIGTERM.
- **Body limits**: `http.MaxBytesReader`; decoder with `DisallowUnknownFields()` for mass-assignment protection.
- **Recover middleware** converting panics to 500 Problem Details.
- **201**: set `Location`, then `WriteHeader(201)`, then encode body.
- **Context**: pass `r.Context()` through service and repo layers for cancellation.
- **JSON field names**: explicit `json:"camelCase"` tags on every field; `omitempty` per the null policy.
