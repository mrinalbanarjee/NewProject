using TriageApi.Core.Models;

namespace TriageApi.Core.Repositories;

public interface INotificationRepository
{
    /// <summary>Looks up a single failed notification in FailedHoganNotification by CorrelationId.</summary>
    Task<NotificationDocument?> FindFailedByCorrelationIdAsync(string correlationId, CancellationToken cancellationToken = default);

    /// <summary>
    /// All notifications (any status) for an ECN from NotificationAudit - the broader
    /// candidate set dependency resolution and staleness checking need, since Success
    /// records only live in the full audit trail, not the failed-only collection.
    /// </summary>
    Task<IReadOnlyList<NotificationDocument>> FindAllByEcnAsync(string ecn, CancellationToken cancellationToken = default);

    /// <summary>
    /// Marks the given correlationIds' Status as Reprocess, in order, in FailedHoganNotification.
    /// Callers must have already validated the plan (existence, current status, dependency
    /// ordering) before calling this - this method performs the write, not the validation.
    /// </summary>
    Task MarkReprocessAsync(IReadOnlyList<string> correlationIdsInOrder, CancellationToken cancellationToken = default);

    Task RecordReprocessAuditAsync(ReprocessAuditEntry entry, CancellationToken cancellationToken = default);
}
