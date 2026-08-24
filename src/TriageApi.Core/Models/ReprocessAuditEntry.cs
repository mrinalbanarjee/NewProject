using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace TriageApi.Core.Models;

/// <summary>
/// One human-approved reprocessing action, recorded independently of the mutation itself
/// so the approved plan (who, when, what order) is reconstructable even if the write to
/// FailedHoganNotification is later investigated separately.
/// </summary>
public sealed class ReprocessAuditEntry
{
    [BsonId]
    public ObjectId Id { get; set; }

    [BsonElement("RootCorrelationId")]
    public string RootCorrelationId { get; set; } = string.Empty;

    [BsonElement("ApprovedByUserId")]
    public string ApprovedByUserId { get; set; } = string.Empty;

    [BsonElement("ApprovedAt")]
    public DateTime ApprovedAt { get; set; }

    [BsonElement("OrderedCorrelationIds")]
    public List<string> OrderedCorrelationIds { get; set; } = new();
}
