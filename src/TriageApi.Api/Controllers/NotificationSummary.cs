namespace TriageApi.Api.Controllers;

/// <summary>Listing-view DTO - deliberately omits NotificationMessage entirely (no redaction needed if it's never included).</summary>
public sealed record NotificationSummary(
    string CorrelationId,
    string NotificationType,
    string Status,
    string HoganTimeStamp,
    int RetryCounter,
    string ProcessorText);
