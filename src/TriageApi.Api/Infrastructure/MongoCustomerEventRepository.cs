using MongoDB.Driver;
using TriageApi.Core.Models;
using TriageApi.Core.Repositories;

namespace TriageApi.Api.Infrastructure;

public sealed class MongoCustomerEventRepository(MongoContext context) : ICustomerEventRepository
{
    public async Task<CustomerEventDocument?> FindByGuidAsync(string eventMessageGuid, CancellationToken cancellationToken = default)
    {
        return await context.CustomerEvents
            .Find(e => e.EventMessageGuid == eventMessageGuid)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<CustomerEventDocument>> FindAllByEcnAsync(string ecn, CancellationToken cancellationToken = default)
    {
        var results = await context.CustomerEvents
            .Find(e => e.Ecn == ecn)
            .ToListAsync(cancellationToken);
        return results;
    }
}
