using TriageApi.Core.Models;

namespace TriageApi.Core.Triage;

/// <summary>
/// Combines dependency resolution and per-notification staleness checking into the plan a
/// human approver reviews. Staleness is checked independently for the root AND for every
/// dependent, because a dependent can be superseded on its own even when the root isn't
/// (see conversation decision: check staleness per notification, not just on the root).
/// </summary>
public static class ReprocessPlanBuilder
{
    /// <param name="phoneFieldByType">Forwarded to DependencyResolver/PhoneMatchChecker - see their doc comments.</param>
    public static ReprocessPlan Build(
        NotificationDocument failed,
        IReadOnlyList<NotificationDocument> sameEcnCandidates,
        IReadOnlyDictionary<string, string>? phoneFieldByType = null)
    {
        var rootStaleness = StalenessChecker.Check(
            failed,
            sameEcnCandidates.Where(c => c.NotificationType == failed.NotificationType).ToList());

        if (rootStaleness.IsStale)
        {
            return new ReprocessPlan(
                failed.CorrelationId,
                rootStaleness,
                Array.Empty<ReprocessPlanItem>(),
                Array.Empty<SupersededItem>(),
                new[]
                {
                    $"Root failure {failed.CorrelationId} is superseded by {rootStaleness.SupersededByCorrelationId} " +
                    "- no reprocessing action, no case opened. Reported as superseded only.",
                });
        }

        // Dependency resolution must only ever pull in candidates that still need attention -
        // a Success record of a dependent type is not a "dependent needing reprocessing".
        var failureLikeCandidates = sameEcnCandidates.Where(c => NotificationFailureStatus.IsFailureLike(c.Status)).ToList();
        var dependencies = DependencyResolver.Resolve(failed, failureLikeCandidates, phoneFieldByType);

        var recommended = new List<ReprocessPlanItem>
        {
            new(failed.CorrelationId, failed.NotificationType, failed.HoganTimeStamp, "Root failure."),
        };
        var superseded = new List<SupersededItem>();

        foreach (var dependent in dependencies.RelatedFailures)
        {
            // Guaranteed present: DependencyResolver only returns entries drawn from sameEcnCandidates.
            var dependentDoc = sameEcnCandidates.First(c => c.CorrelationId == dependent.CorrelationId);
            var dependentStaleness = StalenessChecker.Check(
                dependentDoc,
                sameEcnCandidates.Where(c => c.NotificationType == dependentDoc.NotificationType).ToList());

            if (dependentStaleness.IsStale)
            {
                superseded.Add(new SupersededItem(
                    dependent.CorrelationId,
                    dependent.NotificationType,
                    dependentStaleness.SupersededByCorrelationId!,
                    dependentStaleness.SupersededByHoganTimeStamp!));
            }
            else
            {
                recommended.Add(new ReprocessPlanItem(dependent.CorrelationId, dependent.NotificationType, dependent.HoganTimeStamp, dependent.Reason));
            }
        }

        return new ReprocessPlan(failed.CorrelationId, rootStaleness, recommended, superseded, dependencies.Notes);
    }
}
