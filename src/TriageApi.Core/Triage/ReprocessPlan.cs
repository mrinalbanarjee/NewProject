namespace TriageApi.Core.Triage;

public sealed record ReprocessPlanItem(string CorrelationId, string NotificationType, string HoganTimeStamp, string Reason);

public sealed record SupersededItem(
    string CorrelationId,
    string NotificationType,
    string SupersededByCorrelationId,
    string SupersededByHoganTimeStamp);

/// <summary>
/// The proposal shown to a human approver before anything is written. RecommendedOrder is
/// the root failure followed by its dependents in chronological order - a starting
/// proposal, not a final decision; the approver may reorder before confirming (PRD §2.1.3).
/// Superseded items are reported for audit only - no action is taken on them.
/// </summary>
public sealed record ReprocessPlan(
    string RootCorrelationId,
    StalenessResult RootStaleness,
    IReadOnlyList<ReprocessPlanItem> RecommendedOrder,
    IReadOnlyList<SupersededItem> Superseded,
    IReadOnlyList<string> Notes);
