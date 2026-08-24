using MongoDB.Bson.Serialization.Attributes;

namespace TriageApi.Core.Models;

/// <summary>
/// Element of CustomerEvent.HoganRequestResponses (PRD §2.2). RequestMessage/ResponseMessage
/// are XML and may carry PII - never expose raw, always redact first.
/// </summary>
public sealed class HoganRequestResponseEntry
{
    [BsonElement("CorrelationId")]
    public string CorrelationId { get; set; } = string.Empty;

    [BsonElement("RequestType")]
    public string RequestType { get; set; } = string.Empty;

    [BsonElement("RequestMessage")]
    public string RequestMessage { get; set; } = string.Empty;

    [BsonElement("ResponseType")]
    public string ResponseType { get; set; } = string.Empty;

    [BsonElement("ResponseMessage")]
    public string? ResponseMessage { get; set; }

    [BsonElement("ReturnCode")]
    public string? ReturnCode { get; set; }

    [BsonElement("ErrorText")]
    public string? ErrorText { get; set; }

    [BsonElement("IsMqSent")]
    public bool IsMqSent { get; set; }
}
