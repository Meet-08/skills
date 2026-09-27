#!/usr/bin/env python3
"""Lint an OpenAPI 3.x spec against the REST conventions in design-guidelines.md.

Usage: python lint_openapi.py openapi.yaml [--strict]
Exit code 1 if any ERROR is found (or any WARN with --strict).
Requires PyYAML (pip install pyyaml --break-system-packages).
"""
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML missing: pip install pyyaml --break-system-packages")

METHODS = {"get", "put", "post", "patch", "delete", "head", "options"}
VERBS = {"get", "create", "add", "update", "delete", "remove", "fetch", "list",
         "set", "make", "do", "save", "edit", "modify", "retrieve", "insert"}
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PARAM = re.compile(r"^\{([^}]+)\}$")
CAMEL = re.compile(r"^[a-z][a-zA-Z0-9]*$")
OPID = re.compile(r"^[a-z][a-zA-Z0-9]*$")
UNCOUNTABLE = {"me", "health", "status", "search", "auth", "profile", "settings",
               "metadata", "info", "login", "logout", "token", "config", "v1", "v2", "v3"}

findings = []


def add(level, where, msg):
    findings.append((level, where, msg))


def resolve(spec, node):
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 10:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return node
        cur = spec
        for part in ref[2:].split("/"):
            cur = cur.get(part, {}) if isinstance(cur, dict) else {}
        node, seen = cur, seen + 1
    return node


def check_paths(spec):
    paths = spec.get("paths") or {}
    if not paths:
        add("ERROR", "paths", "No paths defined")
    for path, item in paths.items():
        segs = [s for s in path.strip("/").split("/") if s]
        if path.endswith("/") and path != "/":
            add("WARN", path, "Trailing slash")
        static = []
        for i, seg in enumerate(segs):
            base = seg.split(":")[0]  # allow :action suffix
            m = PARAM.match(base)
            if m:
                if not CAMEL.match(m.group(1)):
                    add("WARN", path, f"Path param '{m.group(1)}' should be camelCase")
                continue
            if "." in base:
                add("WARN", path, f"Segment '{seg}' looks like a file extension")
            if not KEBAB.match(base):
                add("ERROR", path, f"Segment '{base}' is not lowercase kebab-case")
            first = re.split(r"[-_]|(?=[A-Z])", base)[0].lower()
            if first in VERBS:
                add("ERROR", path, f"Segment '{base}' starts with a verb; use nouns + HTTP methods")
            static.append((i, base))
        # collections followed by an {id} should be plural
        for i, base in static:
            nxt = segs[i + 1] if i + 1 < len(segs) else None
            if nxt and PARAM.match(nxt.split(":")[0]) and not base.endswith("s") \
                    and base not in UNCOUNTABLE:
                add("WARN", path, f"Collection '{base}' should probably be plural")
        depth = sum(1 for s in segs if PARAM.match(s.split(":")[0]))
        if depth > 2:
            add("WARN", path, f"Nested {depth} ids deep; keep nesting to one parent")

        for method, op in item.items():
            if method not in METHODS or not isinstance(op, dict):
                continue
            check_operation(spec, path, method, op)


def check_operation(spec, path, method, op):
    where = f"{method.upper()} {path}"
    opid = op.get("operationId")
    if not opid:
        add("ERROR", where, "Missing operationId")
    elif not OPID.match(opid):
        add("WARN", where, f"operationId '{opid}' should be camelCase")
    if not op.get("summary"):
        add("WARN", where, "Missing summary")
    if not op.get("tags"):
        add("WARN", where, "Missing tags")

    responses = {str(k): v for k, v in (op.get("responses") or {}).items()}
    codes = set(responses)
    if not codes:
        add("ERROR", where, "No responses")
        return
    success = {c for c in codes if c.startswith("2")}
    errors = {c for c in codes if c[0] in "45" or c == "default"}
    if not success:
        add("ERROR", where, "No 2xx response documented")
    if not errors:
        add("ERROR", where, "No error responses documented")

    if method == "get" and "requestBody" in op:
        add("ERROR", where, "GET must not have a request body")
    if method == "post" and "201" in codes:
        hdrs = resolve(spec, responses["201"]).get("headers", {}) or {}
        if "Location" not in hdrs:
            add("WARN", where, "201 response should declare a Location header")
    if method == "delete" and success and not ({"204", "202"} & success):
        add("WARN", where, "DELETE usually returns 204")
    if method in {"post", "put", "patch"} and "requestBody" in op and "422" not in codes \
            and "400" not in codes:
        add("WARN", where, "Body-accepting operation documents no 400/422")
    if "{" in path and method in {"get", "put", "patch", "delete"} and "404" not in codes:
        add("WARN", where, "Operation on an id documents no 404")

    for code, resp in responses.items():
        resp = resolve(spec, resp)
        content = resp.get("content") or {}
        if (code[0] in "45" or code == "default") and content \
                and "application/problem+json" not in content:
            add("WARN", where, f"{code} should use application/problem+json")
        for ctype, media in content.items():
            check_schema_props(spec, media.get("schema"), f"{where} {code}", set())

    body = resolve(spec, op.get("requestBody") or {})
    for ctype, media in (body.get("content") or {}).items():
        schema = resolve(spec, media.get("schema") or {})
        if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
            add("WARN", where, "Request schema should set additionalProperties: false")
        check_schema_props(spec, media.get("schema"), f"{where} body", set())


def check_schema_props(spec, schema, where, seen):
    if not isinstance(schema, dict):
        return
    ref = schema.get("$ref")
    if ref:
        if ref in seen:
            return
        seen = seen | {ref}
    schema = resolve(spec, schema)
    for name, prop in (schema.get("properties") or {}).items():
        if not CAMEL.match(name):
            add("WARN", where, f"Field '{name}' is not camelCase")
        p = resolve(spec, prop) if isinstance(prop, dict) else {}
        t = p.get("type")
        if t == "number" and re.search(r"(price|amount|cost|total|balance)", name, re.I):
            add("WARN", where, f"Money field '{name}' is a float; use integer minor units or string decimal")
        check_schema_props(spec, prop, where, seen)
    items = schema.get("items")
    if items:
        check_schema_props(spec, items, where, seen)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    if not args:
        sys.exit(__doc__)
    with open(args[0]) as f:
        spec = yaml.safe_load(f)
    if not str(spec.get("openapi", "")).startswith("3."):
        add("ERROR", "root", "Not an OpenAPI 3.x document")
    if not (spec.get("components") or {}).get("securitySchemes"):
        add("WARN", "components", "No securitySchemes defined")
    check_paths(spec)

    # de-duplicate while keeping order
    uniq = list(dict.fromkeys(findings))
    errs = [f for f in uniq if f[0] == "ERROR"]
    warns = [f for f in uniq if f[0] == "WARN"]
    for lvl, where, msg in errs + warns:
        print(f"[{lvl}] {where}: {msg}")
    print(f"\n{len(errs)} error(s), {len(warns)} warning(s)")
    sys.exit(1 if errs or (strict and warns) else 0)


if __name__ == "__main__":
    main()
