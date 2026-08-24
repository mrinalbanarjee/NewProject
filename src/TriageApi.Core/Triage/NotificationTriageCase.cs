namespace TriageApi.Core.Triage;

/// <summary>
/// The redacted, structured view of a failed notification handed to the agent/API caller.
/// ECN/CorrelationId/LoanAccountNumber are passed through as-is: the PRD's PII constraint
/// names NotificationMessage (and HoganRequestResponses' Request/ResponseMessage)
/// specifically as the XML fields containing PII - these identifiers are the mechanism
/// triage runs on (ECN drives dependency/staleness lookups) and aren't XML PII payloads.
/// Revisit this reading if ECN turns out to be treated as PII elsewhere in the org.
/// </summary>
public sealed record NotificationTriageCase(
    string CorrelationId,
    string Ecn,
    string NotificationType,
    string NotificationTypeDescription,
    string Status,
    int RetryCounter,
    string ProcessorText,
    string HoganTimeStamp,
    string RedactedNotificationMessage,
    StalenessResult Staleness,
    DependencyResolutionResult Dependencies);
