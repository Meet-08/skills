# Java / Kotlin — Spring Boot

Spring Boot 3.x, Java 21 (records for DTOs). Kotlin works identically with data classes.

## Contract-first option
`openapi-generator-maven-plugin` (generator `spring`, `interfaceOnly=true`, `useSpringBoot3=true`) generates API interfaces and DTOs from `openapi.yaml`; controllers implement the interfaces, so the compiler catches contract drift. Prefer this for larger APIs. For small ones, hand-write DTOs mirroring the spec.

## Layout
```
src/main/java/com/example/api/
  config/            # SecurityConfig, WebConfig (CORS), Jackson config
  common/error/      # AppException hierarchy, GlobalExceptionHandler
  common/paging/     # CursorPage<T>, cursor codec
  <resource>/
    OrderController.java      # @RestController, HTTP only
    OrderService.java         # @Service, @Transactional, business rules
    OrderRepository.java      # interface (+ in-memory or Spring Data JPA)
    dto/OrderCreate.java, OrderUpdate.java, OrderResponse.java
    Order.java                # domain/entity — never returned directly
src/main/resources/static/openapi.yaml
```

## Libraries
| Need | Choice |
|---|---|
| Validation | `spring-boot-starter-validation` (`@Valid`, Jakarta constraints) |
| Errors | Built-in `ProblemDetail` + `@RestControllerAdvice` extending `ResponseEntityExceptionHandler`; set `spring.mvc.problemdetails.enabled=true` |
| Security | `spring-boot-starter-oauth2-resource-server` (JWT via `issuer-uri`); `@PreAuthorize("hasAuthority('SCOPE_orders:write')")` |
| Docs | `springdoc-openapi-starter-webmvc-ui`, pointed at the static `openapi.yaml` (`springdoc.swagger-ui.url=/openapi.yaml`) |
| Rate limit | Bucket4j |
| Tests | `@WebMvcTest` + MockMvc; `@SpringBootTest` + Testcontainers for integration; `swagger-request-validator-mockmvc` for contract checks |

## Problem Details
```java
@RestControllerAdvice
class GlobalExceptionHandler extends ResponseEntityExceptionHandler {
  @ExceptionHandler(NotFoundException.class)
  ProblemDetail notFound(NotFoundException ex, HttpServletRequest req) {
    var pd = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    pd.setType(URI.create(BASE + "/not-found")); pd.setTitle("Resource not found");
    pd.setProperty("traceId", MDC.get("traceId"));
    return pd;
  }
  @Override
  protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException ex,
      HttpHeaders h, HttpStatusCode s, WebRequest r) {
    var pd = ProblemDetail.forStatus(HttpStatus.UNPROCESSABLE_ENTITY);
    pd.setType(URI.create(BASE + "/validation-error")); pd.setTitle("Validation failed");
    pd.setProperty("errors", ex.getFieldErrors().stream()
        .map(f -> Map.of("field", f.getField(), "code", f.getCode(), "message", f.getDefaultMessage())).toList());
    return ResponseEntity.unprocessableEntity().contentType(MediaType.APPLICATION_PROBLEM_JSON).body(pd);
  }
  @ExceptionHandler(Exception.class)
  ProblemDetail unhandled(Exception ex) { log.error("unhandled", ex);
    return ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "Unexpected error"); }
}
```
Note: Spring defaults validation failures to 400 — override to 422 if the contract says so.

## Patterns
- **201**: `ResponseEntity.created(uriBuilder.path("/v1/orders/{id}").build(o.id())).body(o)`.
- **204**: `ResponseEntity.noContent().build()`.
- **ETag/If-Match**: entity `@Version` field → `ResponseEntity.ok().eTag(...)`; compare header, throw `PreconditionFailedException` (412).
- **Jackson**: `FAIL_ON_UNKNOWN_PROPERTIES=true` for inputs (mass-assignment protection), ISO dates (`WRITE_DATES_AS_TIMESTAMPS=false`), `NON_NULL` inclusion if the contract omits nulls.
- **PATCH (merge-patch)**: accept `JsonNode` or `Map`, or use `JsonMergePatch` (`jakarta.json`).
- Never return JPA entities — map to response records (MapStruct or manual).
