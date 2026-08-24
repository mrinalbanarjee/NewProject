namespace TriageApi.Core.Authorization;

/// <summary>
/// Resolves a user id to their roles. Dev implementation reads the UserRoles Mongo
/// collection; production implementation should call the internal IAM instead - callers
/// of this interface must not care which.
/// </summary>
public interface IAuthorizationProvider
{
    Task<CallerContext> ResolveAsync(string userId, CancellationToken cancellationToken = default);
}
