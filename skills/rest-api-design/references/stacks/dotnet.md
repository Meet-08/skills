# C# — ASP.NET Core

.NET 8+. Minimal APIs with route groups for small/medium services; controllers when the team prefers them. Both are fine — the contract is what matters.

## Contract-first option
NSwag (`nswag openapi2cscontroller`) generates controller base classes and DTOs from `openapi.yaml`. For minimal APIs, hand-write records mirroring the schemas.

## Layout
```
src/Api/
  Program.cs                  # services, middleware pipeline, endpoint groups
  Endpoints/OrdersEndpoints.cs    # MapGroup("/v1/orders") — HTTP only
  Features/Orders/OrderService.cs # business logic
  Features/Orders/IOrderRepository.cs + InMemoryOrderRepository.cs
  Contracts/Orders/OrderCreate.cs, OrderUpdate.cs, OrderResponse.cs (records)
  Infrastructure/Errors/          # exception types + IExceptionHandler
wwwroot/openapi.yaml
tests/Api.Tests/
```

## Libraries
| Need | Choice |
|---|---|
| Problem Details | Built-in: `builder.Services.AddProblemDetails()` + `IExceptionHandler` |
| Validation | FluentValidation, invoked via an endpoint filter |
| Auth | `Microsoft.AspNetCore.Authentication.JwtBearer`; policies per scope |
| Rate limit | Built-in `Microsoft.AspNetCore.RateLimiting` (`RejectionStatusCode = 429`) |
| Docs | Swagger UI / Scalar pointed at the static `openapi.yaml` |
| Tests | xUnit + `WebApplicationFactory<Program>` |

## Problem Details
```csharp
builder.Services.AddProblemDetails(o => o.CustomizeProblemDetails = ctx => {
    ctx.ProblemDetails.Instance = ctx.HttpContext.Request.Path;
    ctx.ProblemDetails.Extensions["traceId"] = Activity.Current?.Id ?? ctx.HttpContext.TraceIdentifier;
});
builder.Services.AddExceptionHandler<AppExceptionHandler>();
app.UseExceptionHandler(); app.UseStatusCodePages();

sealed class AppExceptionHandler(IProblemDetailsService pds) : IExceptionHandler {
    public async ValueTask<bool> TryHandleAsync(HttpContext ctx, Exception ex, CancellationToken ct) {
        var (status, type, title) = ex switch {
            NotFoundException => (404, $"{Base}/not-found", "Resource not found"),
            ConflictException => (409, $"{Base}/conflict", "Conflict"),
            _ => (500, "about:blank", "Internal Server Error")
        };
        ctx.Response.StatusCode = status;
        return await pds.TryWriteAsync(new() { HttpContext = ctx, Exception = ex,
            ProblemDetails = { Status = status, Type = type, Title = title,
                               Detail = status < 500 ? ex.Message : null } });
    }
}
```
Validation: return `TypedResults.ValidationProblem(...)` but remap to 422 with the contract's `errors[]` shape (the default uses 400 and a dictionary).

## Patterns
- **201**: `TypedResults.Created($"/v1/orders/{o.Id}", o)`; **204**: `TypedResults.NoContent()`.
- **JSON**: `System.Text.Json` defaults to camelCase; add `JsonStringEnumConverter`; set `UnmappedMemberHandling = Disallow` on input types.
- **ETag**: return `ETag` header from a row version; compare `If-Match` → `412`.
- **Security**: `app.UseHsts()`, `UseHttpsRedirection` only for browsers — APIs should reject HTTP; CORS with explicit origins.
