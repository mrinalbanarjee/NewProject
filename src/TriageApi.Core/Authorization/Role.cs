namespace TriageApi.Core.Authorization;

/// <summary>
/// Single Approver role covers all write operations for now (reprocess-marking for both
/// notifications and events, plus Alfa case-opening). Split into granular roles
/// (NotificationApprover, EventApprover, CaseOpener) once the project is further along.
/// </summary>
public static class Role
{
    public const string Viewer = "Viewer";
    public const string Approver = "Approver";
}
