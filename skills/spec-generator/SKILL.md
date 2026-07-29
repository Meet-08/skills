---
name: spec-generator
description: Generate source-grounded Markdown API specifications for a named project feature. Use when the user invokes this skill with a feature name or asks to document a feature's endpoints, request schemas, response schemas, validation, errors, or WebSocket contracts; write the result to specs/{feature}.md.
---

# Generalize Spec Generator

Generate one complete, source-grounded endpoint specification for the requested feature.

## Invocation

Interpret the first argument or named feature as `<feature>` and create or update `specs/<feature>.md` at the project root. Preserve useful existing documentation only when it remains accurate; regenerate stale sections from current source.

Do not modify application source, tests, migrations, configuration, or generated build output. The only intended write is the Markdown specification.

## Source discovery

1. Locate the feature's bounded-context/module directory. Prefer an exact directory such as `**/features/<feature>/`, then inspect project conventions if that path does not exist.
2. Find every HTTP route declaration belonging to the feature: Spring `@RestController`/`@RequestMapping`, JAX-RS resources, Express/Fastify routers, Django/FastAPI routes, or the equivalent framework mechanism.
3. Read the complete path composition from class-level and method-level mappings. Record HTTP method, full path, content type, authentication requirements, and access rules only when supported by source.
4. Trace every endpoint's request and response types through DTOs/records/interfaces, wrapper types, serializers, mapper methods, and service return values. Scan nested DTOs recursively.
5. Scan validation annotations or schemas, enum values, custom validators, exception types, global error handlers, and documented status mappings.
6. Scan feature-local WebSocket/STOMP/message handlers when present (`@MessageMapping`, socket routers, event listeners, message payload DTOs). Document them under a separate realtime section rather than silently omitting them.
7. Check existing project docs and neighboring specs for naming and response-envelope conventions, but treat source code as authoritative.

Use fast text search first (`rg`); exclude build, dependency, IDE, and generated directories. Resolve ambiguous routes by reading the declaring class and imports rather than guessing.

## Required output

Write `specs/<feature>.md` with this structure:

```markdown
# <Feature> API Specification

## Overview
<feature responsibility and source package/module>

## Authentication and common conventions
<only source-supported details: auth, common headers, response envelope, pagination, IDs, dates>

## HTTP endpoints
### <METHOD> <full path>
- Purpose: ...
- Authentication/authorization: ...
- Request headers/path/query parameters: a table with name, type, required, constraints, and description
- Request body: schema and JSON example when the concrete shape is known
- Responses: one subsection/table per status with status, body schema, and example
- Errors: endpoint-specific validation/domain errors and status codes

## WebSocket/message contracts
<only if the feature defines message handlers or listeners; include destination/event, direction, payload schema, and acknowledgement/broadcast behavior>

## Shared schemas
<deduplicated request, response, envelope, error, enum, and nested object definitions>

## Source references
<repository-relative file paths and relevant class/method names>
```

For each schema, show field name, type, required/optional status, nullability where known, validation constraints, enum values, and a concise meaning. Distinguish absent, nullable, and server-generated fields. Use JSON examples only when they can be derived from the DTO shape and conventions.

Document all discovered endpoints, including aliases and multiple methods on one path. Do not collapse distinct status responses into a generic success response. Include empty or `void` bodies explicitly.

When a detail cannot be established from source, write `Not specified in source` or `Inferred from <file>` and keep the inference visibly labeled. Never invent authentication rules, default values, status codes, fields, or examples.

## Verification

Read the generated file back and check that every discovered route appears, each route has request and response shapes (including empty-body cases), validation and errors are source-grounded, realtime contracts are included when present, and source references point to real files.

Run the repository's lightweight Markdown or formatting check if one exists. Otherwise use `git diff --check` when available, with a repository-safe-directory option if Git ownership protection requires it. Report tooling failures separately from the generated documentation.
