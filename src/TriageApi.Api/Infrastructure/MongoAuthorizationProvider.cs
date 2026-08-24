using MongoDB.Driver;
using TriageApi.Core.Authorization;

namespace TriageApi.Api.Infrastructure;

/// <summary>
/// Dev-environment role source, reading the UserRoles collection. Production replaces
/// this entire class with one that calls the internal IAM - nothing else in the app
/// should need to change, since callers only depend on IAuthorizationProvider.
/// </summary>
public sealed class MongoAuthorizationProvider(MongoContext context) : IAuthorizationProvider
{
    public async Task<CallerContext> ResolveAsync(string userId, CancellationToken cancellationToken = default)
    {
        var doc = await context.UserRoles
            .Find(u => u.UserId == userId)
            .FirstOrDefaultAsync(cancellationToken);

        var roles = doc is { Roles.Count: > 0 }
            ? new HashSet<string>(doc.Roles, StringComparer.OrdinalIgnoreCase)
            : new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        return new CallerContext(userId, roles);
    }
}
