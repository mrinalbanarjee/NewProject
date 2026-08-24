using TriageApi.Core.Models;

namespace TriageApi.Core.Triage;

/// <summary>
/// Pure staleness logic - takes an already-fetched candidate set (same NotificationType,
/// same ECN) rather than querying Mongo itself, so this stays unit-testable without a
/// live database. The caller (repository layer) is responsible for fetching candidates.
/// </summary>
public static class StalenessChecker
{
    public static StalenessResult Check(NotificationDocument failed, IReadOnlyList<NotificationDocument> sameTypeSameEcnCandidates)
    {
        if (!HoganTimestampParser.TryParse(failed.HoganTimeStamp, out var failedTimestamp))
        {
            return StalenessResult.Unknown(
                "Failed notification's HoganTimeStamp could not be parsed - staleness cannot be determined. " +
                "Treat as not-provably-stale and flag for manual review rather than assuming either outcome.");
        }

        NotificationDocument? newestSuperseding = null;
        var newestTimestamp = DateTimeOffset.MinValue;

        foreach (var candidate in sameTypeSameEcnCandidates)
        {
            if (candidate.CorrelationId == failed.CorrelationId) continue;
            if (candidate.NotificationType != failed.NotificationType) continue;
            if (candidate.Ecn != failed.Ecn) continue;
            if (candidate.Status != NotificationStatus.Success) continue;
            if (!HoganTimestampParser.TryParse(candidate.HoganTimeStamp, out var candidateTimestamp)) continue;
            if (candidateTimestamp <= failedTimestamp) continue;

            if (newestSuperseding is null || candidateTimestamp > newestTimestamp)
            {
                newestSuperseding = candidate;
                newestTimestamp = candidateTimestamp;
            }
        }

        return newestSuperseding is null
            ? StalenessResult.NotStale()
            : StalenessResult.Stale(newestSuperseding.CorrelationId, newestSuperseding.HoganTimeStamp);
    }
}
