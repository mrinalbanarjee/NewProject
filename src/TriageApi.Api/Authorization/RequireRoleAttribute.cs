using Microsoft.AspNetCore.Mvc.Filters;

namespace TriageApi.Api.Authorization;

/// <summary>Gates an endpoint on the caller (resolved by CallerIdentityMiddleware) holding the given role.</summary>
public sealed class RequireRoleAttribute(string role) : Attribute, IAsyncActionFilter
{
    public async Task OnActionExecutionAsync(ActionExecutingContext context, ActionExecutionDelegate next)
    {
        var currentCaller = context.HttpContext.RequestServices.GetRequiredService<ICurrentCaller>();
        var caller = currentCaller.Context;

        if (caller is null || !caller.HasRole(role))
        {
            context.Result = new Microsoft.AspNetCore.Mvc.ObjectResult(new
            {
                error = $"Caller does not have the required role '{role}'.",
            })
            {
                StatusCode = StatusCodes.Status403Forbidden,
            };
            return;
        }

        await next();
    }
}
