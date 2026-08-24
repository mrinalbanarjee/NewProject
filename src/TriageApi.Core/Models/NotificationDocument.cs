using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace TriageApi.Core.Models;

/// <summary>
/// Raw Mongo document shape for the Notification collection (PRD §2.1), used for
/// NotificationAudit (all notifications) and FailedHoganNotification (failed subset).
/// This type must never be serialized directly into an API response or handed to the LLM —
/// NotificationMessage carries PII XML. Always go through the redaction layer first.
/// </summary>
public sealed class NotificationDocument
{
    [BsonId]
    public ObjectId Id { get; set; }

    [BsonElement("CorrelationId")]
    public string CorrelationId { get; set; } = string.Empty;

    [BsonElement("CreatedAt")]
    public DateTime CreatedAt { get; set; }

    [BsonElement("ECN")]
    public string Ecn { get; set; } = string.Empty;

    // Contract types this as string, not date - parse defensively when ordering by it.
    [BsonElement("HoganTimeStamp")]
    public string HoganTimeStamp { get; set; } = string.Empty;

    [BsonElement("LoanAccountNumber")]
    public string LoanAccountNumber { get; set; } = string.Empty;

    /// <summary>XML payload containing PII. Never expose raw - route through redaction.</summary>
    [BsonElement("NotificationMessage")]
    public string NotificationMessage { get; set; } = string.Empty;

    [BsonElement("NotificationType")]
    public string NotificationType { get; set; } = string.Empty;

    [BsonElement("ProcessorText")]
    public string ProcessorText { get; set; } = string.Empty;

    [BsonElement("RetryCounter")]
    public int RetryCounter { get; set; }

    [BsonElement("Status")]
    public string Status { get; set; } = string.Empty;

    [BsonElement("UpdatedAt")]
    public DateTime UpdatedAt { get; set; }
}
