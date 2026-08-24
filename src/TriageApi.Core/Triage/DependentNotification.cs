namespace TriageApi.Core.Triage;

/// <summary>One related notification pulled in by dependency resolution, with why it's included.</summary>
public sealed record DependentNotification(
    string CorrelationId,
    string NotificationType,
    string HoganTimeStamp,
    string Reason);

/// <summary>
/// Dependency resolution output for a failed notification: the root failure plus every
/// related notification that should be considered for reprocessing alongside it, already
/// ordered (root's dependents in chronological HoganTimeStamp order). This ordering is a
/// starting proposal for the human approver, who may reorder before confirming.
/// </summary>
public sealed record DependencyResolutionResult(
    string RootCorrelationId,
    IReadOnlyList<DependentNotification> RelatedFailures,
    IReadOnlyList<string> Notes);
