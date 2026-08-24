using Microsoft.AspNetCore.Mvc;
using TriageApi.Core.Redaction;
using TriageApi.Core.Repositories;
using TriageApi.Core.Triage;

namespace TriageApi.Api.Controllers;

/// <summary>
/// No write/confirm endpoint yet: dependency and staleness rules for CustomerEvent have
/// not been provided, so this API only supports diagnosis - never an automated
/// reprocessing recommendation - for events. Add a confirm endpoint mirroring
/// NotificationsController once those rules land.
/// </summary>
[ApiController]
[Route("api/customer-events")]
public sealed class CustomerEventsController(
    ICustomerEventRepository repository,
    IMessageRedactor redactor) : ControllerBase
{
    [HttpGet("{eventMessageGuid}/triage")]
    public async Task<ActionResult<CustomerEventTriageCase>> GetTriage(string eventMessageGuid, CancellationToken cancellationToken)
    {
        var evt = await repository.FindByGuidAsync(eventMessageGuid, cancellationToken);
        if (evt is null)
        {
            return NotFound(new { error = $"No CustomerEvent found for EventMessageGuid '{eventMessageGuid}'." });
        }

        var triageCase = CustomerEventTriageCaseBuilder.Build(evt, redactor);
        return Ok(triageCase);
    }
}
