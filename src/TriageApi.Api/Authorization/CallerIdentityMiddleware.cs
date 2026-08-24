using TriageApi.Core.Authorization;

namespace TriageApi.Api.Authorization;

/// <summary>
/// DEV-ONLY identity resolution: trusts an X-User-Id header at face value and looks up
/// that user's roles via IAuthorizationProvider (MongoAuthorizationProvider in dev).
/// THIS IS NOT AUTHENTICATION - anyone can claim to be any user by setting the header.
/// Production must replace this middleware with real token validation (internal IAM /
/// JWT bearer) before this header-trusting behavior ever runs against real data.
/// </summary>
public sealed class CallerIdentityMiddleware(RequestDelegate next)
{
    public const string UserIdHeader = "X-User-Id";

    public async Task InvokeAsync(HttpContext httpContext, IAuthorizationProvider authorizationProvider, ICurrentCaller currentCaller)
    {
        if (!httpContext.Request.Headers.TryGetValue(UserIdHeader, out var userIdValues) ||
            string.IsNullOrWhiteSpace(userIdValues.FirstOrDefault()))
        {
            httpContext.Response.StatusCode = StatusCodes.Status401Unauthorized;
            await httpContext.Response.WriteAsJsonAsync(new
            {
                error = $"Missing {UserIdHeader} header. Dev-mode placeholder for real authentication - " +
                         "see README before treating this as sufficient for production.",
            });
            return;
        }

        var userId = userIdValues.First()!;
        currentCaller.Context = await authorizationProvider.ResolveAsync(userId, httpContext.RequestAborted);

        await next(httpContext);
    }
}
