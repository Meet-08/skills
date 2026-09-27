# Node.js (TypeScript) — Express, Fastify, NestJS

Use TypeScript unless the user asks for plain JS. Node 20+.

## Choosing
- **Fastify** — default for new services: fast, schema-first (JSON Schema validation and serialization built in), which suits a contract-first workflow.
- **Express** — when the user names it or the team already uses it.
- **NestJS** — larger teams wanting opinionated modules, DI and decorators.

## Layout (Express/Fastify)
```
src/
  app.ts               # build app, register plugins/middleware, routes, error handler
  server.ts            # listen()
  config.ts            # env parsing (zod) — fail fast on bad config
  routes/<resource>.routes.ts      # HTTP only: parse, call service, map to response
  services/<resource>.service.ts   # business rules; throws domain errors
  repositories/<resource>.repo.ts  # interface + in-memory impl
  schemas/<resource>.schema.ts     # zod or TypeBox schemas mirroring OpenAPI
  errors/problem.ts                # AppError classes + Problem Details mapper
  middleware/                      # auth, requestId, rateLimit
openapi.yaml
test/
```
NestJS: one module per resource (`orders.module.ts`, `.controller.ts`, `.service.ts`, `dto/`), global `ExceptionFilter` for Problem Details, `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })`.

## Libraries
| Need | Choice |
|---|---|
| Validation | zod (Express), TypeBox/JSON Schema (Fastify), class-validator (Nest) |
| Contract enforcement | `express-openapi-validator` (Express) validates requests/responses against `openapi.yaml`; Fastify: load schemas from spec |
| Types from spec | `openapi-typescript` generates TS types from `openapi.yaml` |
| Security headers | `helmet` / `@fastify/helmet` |
| CORS | `cors` / `@fastify/cors` with explicit origin allow-list |
| Rate limit | `express-rate-limit` / `@fastify/rate-limit` |
| Auth (JWT) | `jose` for verification against the IdP's JWKS |
| Logging | `pino` (+ `pino-http`) with request ID |
| Docs | `swagger-ui-express` / `@fastify/swagger-ui` serving `openapi.yaml` |
| Tests | `vitest` or `jest` + `supertest` (Express) / `app.inject()` (Fastify) |

## Problem Details handler (Express)
```ts
export class AppError extends Error {
  constructor(public status: number, public type: string, public title: string,
              public detail?: string, public errors?: FieldError[]) { super(title); }
}
export const NotFound = (what: string) =>
  new AppError(404, 'https://api.example.com/problems/not-found', 'Resource not found', `${what} not found`);

export function problemHandler(err, req, res, _next) {
  const isApp = err instanceof AppError;
  const status = isApp ? err.status : (err.status ?? 500);
  if (status >= 500) req.log?.error(err);
  res.status(status).type('application/problem+json').json({
    type: isApp ? err.type : 'about:blank',
    title: isApp ? err.title : status >= 500 ? 'Internal Server Error' : err.message,
    status,
    detail: isApp ? err.detail : undefined,
    instance: req.originalUrl,
    traceId: req.id,
    errors: isApp ? err.errors : err.errors?.map(e => ({ field: e.path, code: e.errorCode, message: e.message })),
  });
}
```
Register it last. Convert zod errors to `422` with `errors[]`; JSON parse errors to `400`.

## Patterns
- **201 + Location**: `res.status(201).location(`/v1/orders/${o.id}`).json(o)`.
- **Cursor pagination**: encode `{ createdAt, id }` of the last item as base64url JSON; decode and query `WHERE (createdAt, id) < (?, ?)`. Fetch `limit + 1` to compute `hasMore`.
- **ETag**: hash of `updatedAt`/version; compare `If-Match`, throw `412` on mismatch.
- **Idempotency**: middleware keyed on `Idempotency-Key` + user; store `{ bodyHash, status, body }` for 24h (Map in dev, Redis in prod).
- **Async handlers**: Express 5 forwards rejected promises automatically; on Express 4 wrap handlers.
- Always `app.disable('x-powered-by')` and set `express.json({ limit: '100kb' })`.

## Tests
One happy and one error test per operation. With `express-openapi-validator` set `validateResponses: true` in test env so any drift from the contract fails the test.
