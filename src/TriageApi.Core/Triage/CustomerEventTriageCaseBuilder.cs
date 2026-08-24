using TriageApi.Core.Models;
using TriageApi.Core.Redaction;

namespace TriageApi.Core.Triage;

public static class CustomerEventTriageCaseBuilder
{
    public const string ConservativeNote =
        "Dependency and staleness rules for CustomerEvent are not yet defined (to be provided later). " +
        "Do not autonomously recommend reprocessing for this event - route to alert_user instead.";

    public static CustomerEventTriageCase Build(CustomerEventDocument evt, IMessageRedactor redactor)
    {
        var entries = evt.HoganRequestResponses
            .Select(entry => RedactEntry(entry, redactor))
            .ToList();

        return new CustomerEventTriageCase(
            evt.EventMessageGuid,
            evt.Ecn,
            evt.EventType,
            evt.Status,
            evt.ResponseText,
            entries,
            DependencyAnalysisAvailable: false,
            StalenessAnalysisAvailable: false,
            ReprocessingRecommendationAvailable: false,
            ConservativeNote);
    }

    private static RedactedHoganRequestResponse RedactEntry(HoganRequestResponseEntry entry, IMessageRedactor redactor)
    {
        var request = redactor.Redact(entry.RequestMessage);
        var response = redactor.Redact(entry.ResponseMessage);

        return new RedactedHoganRequestResponse(
            entry.CorrelationId,
            entry.RequestType,
            request.Success ? request.RedactedXml! : $"[BLOCKED - {request.BlockReason}]",
            entry.ResponseType,
            response.Success ? response.RedactedXml! : $"[BLOCKED - {response.BlockReason}]",
            entry.ReturnCode,
            entry.ErrorText,
            entry.IsMqSent);
    }
}
