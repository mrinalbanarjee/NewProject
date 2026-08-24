using MongoDB.Driver;
using TriageApi.Core.Models;
using TriageApi.Core.Repositories;

namespace TriageApi.Api.Infrastructure;

public sealed class MongoNotificationRepository(MongoContext context) : INotificationRepository
{
    public async Task<NotificationDocument?> FindFailedByCorrelationIdAsync(string correlationId, CancellationToken cancellationToken = default)
    {
        return await context.FailedHoganNotification
            .Find(n => n.CorrelationId == correlationId)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<NotificationDocument>> FindAllByEcnAsync(string ecn, CancellationToken cancellationToken = default)
    {
        var results = await context.NotificationAudit
            .Find(n => n.Ecn == ecn)
            .ToListAsync(cancellationToken);
        return results;
    }

    public async Task MarkReprocessAsync(IReadOnlyList<string> correlationIdsInOrder, CancellationToken cancellationToken = default)
    {
        // Sequential, not bulk: preserves a clear per-item audit trail and lets a failure
        // partway through stop cleanly rather than leaving an unclear partial bulk-write state.
        foreach (var correlationId in correlationIdsInOrder)
        {
            var update = Builders<NotificationDocument>.Update
                .Set(n => n.Status, NotificationStatus.Reprocess)
                .Set(n => n.UpdatedAt, DateTime.UtcNow);

            await context.FailedHoganNotification.UpdateOneAsync(
                n => n.CorrelationId == correlationId,
                update,
                cancellationToken: cancellationToken);
        }
    }

    public Task RecordReprocessAuditAsync(ReprocessAuditEntry entry, CancellationToken cancellationToken = default)
    {
        return context.ReprocessAudit.InsertOneAsync(entry, cancellationToken: cancellationToken);
    }
}
