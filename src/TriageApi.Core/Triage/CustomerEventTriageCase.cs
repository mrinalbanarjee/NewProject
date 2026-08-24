namespace TriageApi.Core.Triage;

public sealed record RedactedHoganRequestResponse(
    string CorrelationId,
    string RequestType,
    string RedactedRequestMessage,
    string ResponseType,
    string RedactedResponseMessage,
    string? ReturnCode,
    string? ErrorText,
    bool IsMqSent);

/// <summary>
/// The redacted, structured view of a CustomerEvent handed to the agent/API caller.
/// DependencyAnalysisAvailable/StalenessAnalysisAvailable are deliberately false: those
/// rules for CustomerEvent haven't been provided yet (deferred, per PRD conversation).
/// Until they are, the agent must not propose a reprocessing plan for event failures -
/// diagnose and route to alert_user instead, since recommending reprocessing without a
/// staleness check risks pushing stale data back into Hogan (the exact failure mode the
/// staleness rule exists to prevent for notifications).
/// </summary>
public sealed record CustomerEventTriageCase(
    string EventMessageGuid,
    string Ecn,
    string? EventType,
    string Status,
    string? ResponseText,
    IReadOnlyList<RedactedHoganRequestResponse> HoganRequestResponses,
    bool DependencyAnalysisAvailable,
    bool StalenessAnalysisAvailable,
    bool ReprocessingRecommendationAvailable,
    string Note);
