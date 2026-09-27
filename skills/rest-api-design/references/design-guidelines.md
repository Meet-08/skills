# REST API Design Guidelines

Stack-agnostic rules for the design phase. Each section explains the reasoning so you can make good calls in cases the rules don't cover.

## Contents
1. Resource naming and URLs
2. HTTP methods and semantics
3. Status codes
4. Request and response bodies
5. Errors (RFC 9457)
6. Pagination, filtering, sorting, field selection
7. Versioning and evolution
8. Authentication and authorization
9. Idempotency and concurrency
10. Caching, rate limiting, and operational headers
11. Security
12. Long-running and bulk operations
13. Design review checklist

---

## 1. Resource naming and URLs

- **Nouns, not verbs.** The method is the verb. `POST /users`, not `POST /createUser`.
- **Plural collections.** `/users` and `/users/{userId}`. Consistent pluralization means clients never guess.
- **kebab-case path segments**, camelCase path parameters: `/purchase-orders/{purchaseOrderId}`.
- **Shallow nesting.** Nest only for true containment (`/orders/{orderId}/line-items`). Stop at one level: `/orders/{id}/line-items/{lineItemId}` is fine; `/customers/{c}/orders/{o}/line-items/{l}` is not — the line item has a stable ID of its own.
- **No file extensions or trailing slashes.** Use `Accept` for formats.
- **Singleton sub-resources** are singular: `/users/{id}/profile`, `/me`.
- **Non-CRUD actions**: prefer modelling the action's result as a resource (`POST /payments/{id}/refunds` creates a refund). When no natural noun exists, use a colon action (`POST /documents/{id}:publish`). Never `GET` for actions.

## 2. HTTP methods and semantics

| Method | Use | Safe | Idempotent | Typical success |
|---|---|---|---|---|
| GET | Read resource or collection | ✔ | ✔ | 200 |
| POST | Create in collection; non-idempotent action | ✘ | ✘ | 201 + `Location` / 200 / 202 |
| PUT | Full replace (client sends whole representation) | ✘ | ✔ | 200 or 204 |
| PATCH | Partial update (JSON Merge Patch by default) | ✘ | ✘* | 200 |
| DELETE | Remove | ✘ | ✔ | 204 |

*PATCH with merge-patch is idempotent in practice; document it.

- Use `PUT` for create only when the client chooses the ID.
- `DELETE` on an already-deleted resource: return `404` (or `204` if you want strict idempotent-looking behavior — pick one and document it).
- Support `HEAD` and `OPTIONS` implicitly where the framework allows.

## 3. Status codes

Use the most specific correct code; clients branch on them.

- **200** OK with body · **201** Created (+ `Location` header, return the resource) · **202** Accepted (async; return a status resource) · **204** No Content
- **400** malformed request (bad JSON, wrong types) · **401** missing/invalid credentials · **403** authenticated but not allowed · **404** not found (also use for resources the caller can't see, to avoid leaking existence) · **405** method not allowed · **409** conflict (duplicate, invalid state transition) · **412** precondition failed (ETag mismatch) · **415** unsupported media type · **422** well-formed but semantically invalid (validation failures) · **428** precondition required · **429** too many requests
- **500** unexpected server error (never leak stack traces) · **503** temporarily unavailable (+ `Retry-After`)

Convention: `400` for syntactic problems, `422` for validation. If the team prefers `400` for both, that's acceptable — be consistent.

## 4. Request and response bodies

- **JSON, camelCase**, UTF-8. `Content-Type: application/json`.
- **Return the resource** after create/update so clients don't need a second call.
- **No envelopes for single resources.** Return the object directly. Collections use `{ "data": [...], "page": {...} }` so pagination metadata has a home.
- **Timestamps**: ISO 8601 in UTC (`2026-09-27T10:15:00Z`), named `createdAt`, `updatedAt`.
- **IDs**: strings (UUIDv7, ULID, or prefixed like `ord_123`). Opaque; never expose auto-increment integers publicly (enumeration risk, sharding pain).
- **Money**: integer minor units plus currency (`{"amount": 1999, "currency": "INR"}`) or decimal string. Never floats.
- **Enums**: UPPER_SNAKE or lowercase strings — pick one. Document that new values may be added.
- **Nulls**: omit vs `null` — pick one policy. For PATCH (merge-patch), `null` means "clear this field".
- **Booleans** named as predicates: `isActive`, `hasChildren`.
- **Separate schemas** for create/update/read. Mark server fields `readOnly: true`, secrets `writeOnly: true`.

## 5. Errors (RFC 9457 Problem Details)

Every error uses `Content-Type: application/problem+json`:

```json
{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Validation failed",
  "status": 422,
  "detail": "2 fields are invalid.",
  "instance": "/v1/orders",
  "traceId": "4bf92f3577b34da6",
  "errors": [
    { "field": "email", "code": "invalid_format", "message": "Must be a valid email address." },
    { "field": "items[0].quantity", "code": "min", "message": "Must be at least 1." }
  ]
}
```

- `type` is a stable URI identifying the problem class — clients key off it, not `title`.
- Include a `traceId` that matches server logs.
- Never include stack traces, SQL, or internal hostnames.

## 6. Pagination, filtering, sorting, field selection

**Cursor pagination (default):**
Request `GET /orders?limit=20&cursor=eyJpZCI6...`. Response:
```json
{ "data": [...], "page": { "nextCursor": "eyJpZCI6...", "hasMore": true } }
```
Stable under inserts, efficient on large tables. Cursors are opaque (base64-encoded keyset).

**Offset pagination** (`?page=2&pageSize=20`, with `totalItems`) is acceptable for small admin lists where jumping to a page matters.

- Always cap `limit` (e.g., default 20, max 100) and document it.
- **Filtering**: plain query params per field (`?status=shipped&customerId=cus_1`); ranges with suffixes (`createdAfter`, `createdBefore`) or `created[gte]=` — pick one.
- **Sorting**: `?sort=-createdAt,name` (minus = descending). Whitelist sortable fields.
- **Search**: `?q=` for free text.
- **Field selection** (optional): `?fields=id,name`. **Expansion** (optional): `?expand=customer`.

## 7. Versioning and evolution

- Major version in the URI: `/v1/...`. Simple, visible, cache-friendly.
- **Non-breaking** (no version bump): adding endpoints, optional request fields, response fields, enum values (if documented as extensible).
- **Breaking** (new major): removing/renaming fields, changing types, tightening validation, changing status codes or auth.
- Deprecate with `Deprecation` and `Sunset` headers plus a `Link` to migration docs; keep the old version running through the sunset date.
- Clients must ignore unknown fields — say so in the docs.

## 8. Authentication and authorization

- **User-facing**: OAuth 2.0 / OIDC, `Authorization: Bearer <JWT>`. Short-lived access tokens, refresh via the auth server.
- **Server-to-server**: OAuth client credentials, or API keys in a header (`X-API-Key` or `Authorization`), never in query strings (they end up in logs).
- Define scopes per operation in OpenAPI (`security: [{ bearerAuth: [orders:write] }]`).
- Enforce object-level authorization on every request that takes an ID (BOLA is the #1 API vulnerability). Return `404` for objects the caller can't access.
- HTTPS only. Reject plain HTTP rather than redirecting API calls.

## 9. Idempotency and concurrency

- **Idempotency-Key** header on POSTs that create resources or move money. Server stores key + request hash + response for ~24h; a replay with the same key returns the stored response; same key with a different body returns `422`.
- **Optimistic concurrency**: return `ETag` on GET; require `If-Match` on PUT/PATCH/DELETE for contended resources. Mismatch → `412`; missing when required → `428`.

## 10. Caching, rate limiting, and operational headers

- `Cache-Control: no-store` on sensitive responses; `private, max-age=…` or `ETag` + `If-None-Match` → `304` for cacheable reads.
- Rate limits: `429` with `Retry-After`; expose `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`.
- Accept/propagate `X-Request-Id` (or W3C `traceparent`) and echo it back.
- `Location` on 201 and 202.

## 11. Security

Design-time items (mapped to OWASP API Security Top 10):
- Object-level and function-level authorization on every operation.
- Explicit request schemas with `additionalProperties: false` to block mass assignment.
- Bounds on every string (`maxLength`), array (`maxItems`), and number; cap page sizes and request body size.
- Never return secrets or internal fields; use distinct response schemas.
- Validate `Content-Type`; reject unexpected media types with `415`.
- Security headers: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, restrictive CORS allow-list.

## 12. Long-running and bulk operations

- **Async**: `POST /reports` → `202 Accepted`, `Location: /v1/operations/{opId}`. The operation resource exposes `status` (`pending|running|succeeded|failed`), and a link to the result when done. Optionally support webhooks.
- **Bulk**: `POST /orders:batchCreate` with a capped array; respond `200` with per-item results (`207 Multi-Status` is an option but less client-friendly). Document atomicity (all-or-nothing vs partial).

---

## 13. Design review checklist

Walk this before presenting the design. Each "no" needs a fix or a stated reason.

**Resources & URLs**
- [ ] Every path is plural-noun, kebab-case, verb-free (except documented `:action` endpoints)
- [ ] Nesting ≤ 1 level; nested children genuinely can't exist alone
- [ ] Non-CRUD actions follow one consistent style

**Semantics**
- [ ] Methods match semantics (no state change on GET; PUT is full replace)
- [ ] 201 responses include `Location`; DELETE returns 204
- [ ] Every operation documents 4xx/5xx responses, not just success

**Schemas**
- [ ] Separate create/update/read schemas; server-owned fields are `readOnly`
- [ ] Strings, arrays, numbers have bounds; `additionalProperties: false` on inputs
- [ ] Timestamps ISO 8601 UTC; IDs are strings; money isn't a float
- [ ] Field naming is consistently camelCase

**Cross-cutting**
- [ ] All errors use the shared Problem Details schema
- [ ] All collections paginate with a capped `limit`
- [ ] Auth scheme and per-operation scopes are declared
- [ ] Money-moving/creation POSTs accept `Idempotency-Key`
- [ ] Contended updates use `ETag`/`If-Match`
- [ ] Versioning strategy stated; nothing in the design depends on a specific framework or database

**Consumer view**
- [ ] A client can complete each core user journey without N+1 calls or guessing
- [ ] Every operation has an `operationId`, summary, and example
