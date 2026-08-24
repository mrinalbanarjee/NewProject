using TriageApi.Core.Models;

namespace TriageApi.Core.Triage;

/// <summary>
/// Applies the two confirmed dependency rules (PRD §2.1.2):
/// - OXCU066 &amp; OXCU021 depend on OXCU054 (a static type-to-type rule) - AND must be
///   about the same phone number as the failed OXCU054, checked via PhoneMatchChecker.
///   A consent update for a different phone number is not actually related, even though
///   it matches on ECN + type.
/// - OXCU008 (Combine) is upstream of every other type for that ECN occurring after it
///   (a temporal rule, not a fixed type list).
/// Pure function over an already-fetched candidate set (same ECN) - no Mongo access here,
/// so it stays unit-testable. Only candidates currently in a failure-ish state should
/// generally be passed in by the caller; this function does not filter by Status itself
/// because "which statuses count" is a query-shaping decision for the repository layer.
/// </summary>
public static class DependencyResolver
{
    /// <param name="phoneFieldByType">Forwarded to PhoneMatchChecker - see its doc comment.</param>
    public static DependencyResolutionResult Resolve(
        NotificationDocument failed,
        IReadOnlyList<NotificationDocument> sameEcnCandidates,
        IReadOnlyDictionary<string, string>? phoneFieldByType = null)
    {
        var related = new List<DependentNotification>();
        var notes = new List<string>();

        if (NotificationTypeCatalog.StaticDependents.TryGetValue(failed.NotificationType, out var dependentTypes))
        {
            var description = NotificationTypeCatalog.Descriptions.GetValueOrDefault(failed.NotificationType, failed.NotificationType);
            foreach (var candidate in sameEcnCandidates.Where(c => c.Ecn == failed.Ecn && dependentTypes.Contains(c.NotificationType)))
            {
                var phoneMatch = PhoneMatchChecker.Check(failed, candidate, phoneFieldByType);

                if (!phoneMatch.Determinable)
                {
                    notes.Add(
                        $"{candidate.CorrelationId} ({candidate.NotificationType}) type-depends on {failed.NotificationType}, " +
                        $"but whether it's the same phone number could not be verified ({phoneMatch.Reason}) - " +
                        "excluded from the recommended plan pending manual review.");
                    continue;
                }

                if (!phoneMatch.Matches)
                {
                    notes.Add(
                        $"{candidate.CorrelationId} ({candidate.NotificationType}) type-depends on {failed.NotificationType} " +
                        "but refers to a different phone number - not included as a dependent.");
                    continue;
                }

                related.Add(new DependentNotification(
                    candidate.CorrelationId,
                    candidate.NotificationType,
                    candidate.HoganTimeStamp,
                    $"Depends on {failed.NotificationType} ({description}) having already been applied to the same phone number."));
            }
        }

        if (NotificationTypeCatalog.IsUpstreamOfAllTypes(failed.NotificationType))
        {
            if (HoganTimestampParser.TryParse(failed.HoganTimeStamp, out var failedTimestamp))
            {
                foreach (var candidate in sameEcnCandidates)
                {
                    if (candidate.Ecn != failed.Ecn) continue;
                    if (candidate.NotificationType == failed.NotificationType) continue;
                    if (related.Any(r => r.CorrelationId == candidate.CorrelationId)) continue;
                    if (!HoganTimestampParser.TryParse(candidate.HoganTimeStamp, out var candidateTimestamp)) continue;
                    if (candidateTimestamp <= failedTimestamp) continue;

                    related.Add(new DependentNotification(
                        candidate.CorrelationId,
                        candidate.NotificationType,
                        candidate.HoganTimeStamp,
                        $"Occurred after the failed Combine ({NotificationTypeCatalog.CombineType}) for the same ECN - potentially affected, re-evaluate."));
                }
            }
            else
            {
                notes.Add("Combine failure's HoganTimeStamp could not be parsed, so time-based dependents could not be computed - review manually.");
            }
        }

        var ordered = related
            .OrderBy(r => HoganTimestampParser.TryParse(r.HoganTimeStamp, out var ts) ? ts : DateTimeOffset.MaxValue)
            .ToList();

        return new DependencyResolutionResult(failed.CorrelationId, ordered, notes);
    }
}
