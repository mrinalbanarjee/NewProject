namespace TriageApi.Core.Authorization;

/// <summary>The authenticated caller's identity and roles, resolved once per request.</summary>
public sealed record CallerContext(string UserId, IReadOnlySet<string> Roles)
{
    public bool HasRole(string role) => Roles.Contains(role);
}
