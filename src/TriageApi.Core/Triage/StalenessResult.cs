namespace TriageApi.Core.Triage;

/// <summary>
/// Result of the staleness check (PRD, notification staleness rule as confirmed by the user):
/// a failure is superseded when a later notification of the same type, same ECN, reached
/// Success after the failed one's HoganTimeStamp. When superseded, no reprocessing action
/// should be taken and no case should be opened - just report it, citing SupersededByCorrelationId.
/// </summary>
public sealed record StalenessResult(
    bool IsStale,
    bool Determinable,
    string? SupersededByCorrelationId,
    string? SupersededByHoganTimeStamp,
    string? Note)
{
    public static StalenessResult NotStale() => new(false, true, null, null, null);

    public static StalenessResult Stale(string correlationId, string hoganTimeStamp) =>
        new(true, true, correlationId, hoganTimeStamp, null);

    public static StalenessResult Unknown(string note) => new(false, false, null, null, note);
}
