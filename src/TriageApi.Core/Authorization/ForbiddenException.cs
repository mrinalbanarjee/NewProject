namespace TriageApi.Core.Authorization;

/// <summary>Thrown when a caller lacks the role required for the requested operation.</summary>
public sealed class ForbiddenException(string userId, string requiredRole)
    : Exception($"User '{userId}' does not have the required role '{requiredRole}'.")
{
    public string UserId { get; } = userId;
    public string RequiredRole { get; } = requiredRole;
}
