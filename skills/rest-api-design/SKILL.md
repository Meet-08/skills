---
name: rest-api-design
description: Contract-first REST API design and implementation. First produces a backend-independent API design (resource model, endpoints, status codes, error format, pagination, auth, versioning) as an OpenAPI 3.1 spec, reviews it against best practices, gets user approval, and only then implements it in the user's chosen stack (Express, NestJS, FastAPI, Django, Spring Boot, Go, .NET, or any other). Use this skill whenever the user wants to build, design, plan, scaffold, review, or refactor a REST API, HTTP API, web service, backend endpoints, CRUD API, or OpenAPI/Swagger spec — even if they only say "make me a backend for X" or "add endpoints for Y" and don't mention design or best practices.
---

# REST API Design → Implementation

This skill runs in two phases with a hard checkpoint between them:

1. **Design** — produce a stack-agnostic contract (OpenAPI 3.1) that any backend could implement.
2. **Implement** — translate that approved contract into the user's stack, faithfully.

The reason for the split: API contracts outlive implementations. Clients, docs, SDKs and tests all depend on the contract, so mistakes there are expensive to undo. Designing without a framework in mind also stops framework defaults (auto-generated routes, ORM-shaped payloads) from leaking into the public interface.

---

## Phase 1 — Design (backend-independent)

During this phase, do not write framework code, mention ORMs, or shape payloads around database tables. Think in terms of what API consumers need.

### Step 1: Understand the domain

Extract from the request (ask only for what's genuinely missing and blocks design — otherwise state assumptions and proceed):

- **Consumers**: who calls this API (web SPA, mobile, third-party partners, internal services)? This drives auth, versioning strictness and pagination style.
- **Resources**: the nouns of the domain and how they relate (owns, belongs to, many-to-many).
- **Operations**: what consumers must do with each resource, including non-CRUD actions (approve, cancel, refund).
- **Constraints**: expected scale, public vs internal, compliance or multi-tenancy needs.

### Step 2: Model resources and endpoints

Read `references/design-guidelines.md` now — it holds the detailed rules. The essentials:

- Plural nouns, kebab-case paths, no verbs: `/orders`, `/orders/{orderId}/line-items`.
- Nest at most one level deep when the child cannot exist without the parent; otherwise use a top-level collection with a filter (`/comments?postId=…`).
- Map operations to methods by semantics: GET (safe), PUT (full replace, idempotent), PATCH (partial), POST (create or non-idempotent action), DELETE (idempotent).
- Model state-changing actions that aren't CRUD as sub-resources or action endpoints: `POST /orders/{id}/cancellation` (preferred) or `POST /orders/{id}:cancel`. Pick one style and use it everywhere.
- Use camelCase JSON fields, ISO 8601 UTC timestamps, string IDs (opaque to clients), and explicit enums.
- Separate request and response schemas (e.g., `OrderCreate`, `OrderUpdate`, `Order`) so server-owned fields (`id`, `createdAt`) never appear as client inputs.

### Step 3: Define cross-cutting concerns

Decide each of these once for the whole API — consistency matters more than any single choice:

| Concern | Default (override with reason) |
|---|---|
| Errors | RFC 9457 Problem Details (`application/problem+json`) with an `errors[]` array for field validation |
| Pagination | Cursor-based (`limit`, `cursor`, response `nextCursor`) for feeds/large sets; offset allowed for small admin lists |
| Filtering/sorting | `?status=active&sort=-createdAt,name` |
| Versioning | URI major version `/v1`; additive changes don't bump it |
| Auth | OAuth2/OIDC bearer JWT for users; API keys only for server-to-server |
| Idempotency | `Idempotency-Key` header on POSTs that create or charge |
| Concurrency | `ETag` + `If-Match` on PUT/PATCH/DELETE where lost updates matter |
| Rate limiting | `429` + `Retry-After`, `RateLimit-*` headers |
| Caching | `Cache-Control` and `ETag` on cacheable GETs |

### Step 4: Write the OpenAPI 3.1 contract

Start from `assets/openapi-template.yaml`, which already contains reusable Problem Details schemas, pagination parameters, security schemes and standard error responses. Every operation needs: `operationId` (camelCase verbNoun, e.g., `listOrders`), a summary, tags, all success and error responses, and request/response examples.

Save it as `openapi.yaml` in the output directory.

### Step 5: Lint and self-review

Run the linter bundled with this skill:

```bash
python <skill-path>/scripts/lint_openapi.py openapi.yaml
```

It catches mechanical issues (verbs in paths, singular collections, missing error responses, missing operationIds, inconsistent casing). Fix every error; justify or fix warnings.

Then walk through the checklist at the bottom of `references/design-guidelines.md` for the judgment calls a linter can't make.

### Step 6: Present the design and STOP for approval

Show the user a compact summary — not the full YAML dumped into chat:

```markdown
## API design: <name>

**Resources:** <one-line each, with relationships>

**Endpoints**
| Method | Path | Purpose | Success | Notable errors |
|---|---|---|---|---|

**Conventions:** errors, pagination, auth, versioning, idempotency choices (one line each)

**Assumptions & open questions:** <anything you guessed>
```

Then provide the `openapi.yaml` file and ask the user to approve or request changes. **Do not start Phase 2 until they approve.** If the user explicitly says to skip the review ("just build it"), note your key assumptions in one short paragraph and continue.

---

## Phase 2 — Implement in the given stack

### Step 7: Confirm the stack

Use the stack the user named. If none was named, ask once, offering the common options. Then read the matching guide:

| Stack | Reference |
|---|---|
| Node.js — Express, Fastify, NestJS | `references/stacks/node.md` |
| Python — FastAPI, Django REST Framework, Flask | `references/stacks/python.md` |
| Java/Kotlin — Spring Boot | `references/stacks/java-spring.md` |
| Go — net/http, chi, Gin, Echo | `references/stacks/go.md` |
| C# — ASP.NET Core | `references/stacks/dotnet.md` |
| Anything else | `references/stacks/generic.md` (mapping procedure for any framework) |

### Step 8: Implement against the contract

The contract is the source of truth. The implementation must match it exactly — paths, field names, status codes, headers, error shape. When the framework's defaults disagree with the contract (e.g., a framework returning `422` with its own error format), override the framework.

Build in this order, because each layer depends on the one before:

1. **Project layout** — layered: routes/controllers (HTTP only) → services (business logic) → repositories (persistence). Controllers never talk to the database directly; this is what keeps the implementation swappable underneath the contract.
2. **Schemas/DTOs** — generated from or hand-mirrored to the OpenAPI schemas, with validation.
3. **Error handling** — one central handler that converts every exception into Problem Details. No route builds error responses by hand.
4. **Cross-cutting middleware** — auth, request ID/correlation, logging, rate limiting, CORS, security headers.
5. **Endpoints** — one per operation in the spec, named after `operationId`.
6. **Persistence** — in-memory repository by default unless the user named a database; keep it behind the repository interface.
7. **Tests** — at least one happy path and one error path per endpoint, plus contract validation (responses validated against `openapi.yaml`) where the stack has tooling for it.
8. **Docs & run instructions** — serve the spec (Swagger UI / Redoc) and include a README with setup, env vars and example `curl` calls.

### Step 9: Verify conformance

Before handing off, cross-check the implementation against the spec: every `operationId` has a handler, every documented status code is reachable, and no undocumented endpoints exist. If you can run the code, start it and exercise a few endpoints with `curl`. Report any intentional deviations.

---

## Output

Deliver:

- `openapi.yaml` — the approved contract (Phase 1)
- The project source tree for the chosen stack (Phase 2)
- `README.md` — how to run, test and call the API

Keep the chat summary short: what was built, how to run it, and any deviations or follow-ups.
