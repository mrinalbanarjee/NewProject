namespace TriageApi.Api.Controllers;

public sealed record ConfirmReprocessRequest(string RootCorrelationId, IReadOnlyList<string> OrderedCorrelationIds);
