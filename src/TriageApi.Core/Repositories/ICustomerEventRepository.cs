using TriageApi.Core.Models;

namespace TriageApi.Core.Repositories;

public interface ICustomerEventRepository
{
    Task<CustomerEventDocument?> FindByGuidAsync(string eventMessageGuid, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<CustomerEventDocument>> FindAllByEcnAsync(string ecn, CancellationToken cancellationToken = default);
}
