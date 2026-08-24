using TriageApi.Core.Models;
using TriageApi.Core.Redaction;

namespace TriageApi.Core.Triage;

public static class NotificationTriageCaseBuilder
{
    public static NotificationTriageCase Build(
        NotificationDocument failed,
        IReadOnlyList<NotificationDocument> sameEcnCandidates,
        IMessageRedactor redactor,
        IReadOnlyDictionary<string, string>? phoneFieldByType = null)
    {
        var redaction = redactor.Redact(failed.NotificationMessage);
        var redactedMessage = redaction.Success
            ? redaction.RedactedXml!
            : $"[BLOCKED - {redaction.BlockReason}]";

        var staleness = StalenessChecker.Check(
            failed,
            sameEcnCandidates.Where(c => c.NotificationType == failed.NotificationType).ToList());

        // Dependency resolution must only ever pull in candidates that still need attention -
        // a Success record of a dependent type is not a "dependent needing reprocessing".
        var failureLikeCandidates = sameEcnCandidates.Where(c => NotificationFailureStatus.IsFailureLike(c.Status)).ToList();
        var dependencies = DependencyResolver.Resolve(failed, failureLikeCandidates, phoneFieldByType);

        return new NotificationTriageCase(
            failed.CorrelationId,
            failed.Ecn,
            failed.NotificationType,
            NotificationTypeCatalog.Descriptions.GetValueOrDefault(failed.NotificationType, "Unknown type"),
            failed.Status,
            failed.RetryCounter,
            failed.ProcessorText,
            failed.HoganTimeStamp,
            redactedMessage,
            staleness,
            dependencies);
    }
}
