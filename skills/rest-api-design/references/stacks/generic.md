# Any other stack (Rails, Laravel, Phoenix, Rust/Axum, Ktor, Hono, etc.)

No dedicated guide? Map the contract onto the framework with this procedure. The goal is the same everywhere: the framework is an implementation detail beneath an unchanged contract.

## 1. Find the framework's equivalents
Before writing code, identify (from the framework docs or your knowledge) how it does each of these, and note any default that conflicts with the contract:

| Contract concern | Look for |
|---|---|
| Routing by method + path | router / route macros / resource routes |
| Input validation | schema library, form requests, changesets, serde + validator |
| Central error handling | exception handler, rescue_from, error middleware, `IntoResponse` for errors |
| Serialization control | serializers, resources, explicit DTO structs (camelCase config) |
| Auth middleware | guards, plugs, filters, extractors |
| OpenAPI tooling | generators from spec (openapi-generator supports 50+ targets), request validators |
| Test client | in-process HTTP test client |

**Common conflicts to override:** default validation status (often 400 with a framework-specific body), snake_case JSON (Rails, Laravel, Phoenix), auto-generated resource routes you didn't design (e.g., Rails `resources` adds `edit`/`new` — use `only:`), HTML error pages in production, auto-incrementing integer IDs exposed in URLs.

## 2. Check openapi-generator first
`openapi-generator-cli list` — if a server generator exists for the stack, generate interfaces/models from `openapi.yaml` and implement them. This gives compile-time or boot-time contract alignment.

## 3. Build in the standard order
Layout (routes → services → repositories), schemas/DTOs, central Problem Details handler, middleware (request ID, logging, auth, rate limit, CORS, security headers), endpoints named after `operationId`, in-memory repository, tests, README. Same as SKILL.md Step 8.

## 4. Stack notes
- **Rails**: `rails new --api`; `rescue_from` in `ApplicationController` for Problem Details; `committee` gem validates requests/responses against the spec; configure camelCase via serializer (e.g., `alba` or `blueprinter` with key transform).
- **Laravel**: API resources for output shape, Form Requests for validation (override `failedValidation` to emit Problem Details at 422); exception rendering in `bootstrap/app.php`.
- **Phoenix**: JSON views/`Jason`, `FallbackController` for error mapping, `OpenApiSpex` for validation.
- **Rust (Axum)**: `serde(rename_all = "camelCase", deny_unknown_fields)`, a custom `AppError` implementing `IntoResponse` for Problem Details, `utoipa` or `progenitor`/`openapi-generator` for spec alignment, `tower-http` for CORS/tracing/limits.
- **Hono / Bun / Deno**: `@hono/zod-openapi`; `app.onError` for Problem Details.
