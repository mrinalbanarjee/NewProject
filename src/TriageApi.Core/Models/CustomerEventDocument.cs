using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace TriageApi.Core.Models;

/// <summary>
/// Raw Mongo document shape for the CustomerEvent collection (PRD §2.2, AlfaToHogan flow).
/// HoganRequestResponses entries carry XML that may hold PII - never expose raw, always redact.
/// </summary>
public sealed class CustomerEventDocument
{
    [BsonId]
    public ObjectId Id { get; set; }

    [BsonElement("EventMessageGuid")]
    public string EventMessageGuid { get; set; } = string.Empty;

    [BsonElement("EventType")]
    public string? EventType { get; set; }

    [BsonElement("EventData")]
    public string? EventData { get; set; }

    [BsonElement("CreatedAt")]
    public DateTime CreatedAt { get; set; }

    [BsonElement("ECN")]
    public string Ecn { get; set; } = string.Empty;

    [BsonElement("ThirdPartyId")]
    public string? ThirdPartyId { get; set; }

    // Contract spells this "BillingAddressNmber" - mapped as-is to the stored field name;
    // verify against the real collection before renaming the Mongo-side field.
    [BsonElement("BillingAddressNmber")]
    public string? BillingAddressNumber { get; set; }

    [BsonElement("AccountNumber")]
    public string? AccountNumber { get; set; }

    [BsonElement("HoganRequestResponses")]
    public List<HoganRequestResponseEntry> HoganRequestResponses { get; set; } = new();

    [BsonElement("Status")]
    public string Status { get; set; } = string.Empty;

    [BsonElement("ResponseText")]
    public string? ResponseText { get; set; }

    [BsonElement("UpdatedAt")]
    public DateTime UpdatedAt { get; set; }
}
