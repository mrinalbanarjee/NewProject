using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace TriageApi.Core.Models;

/// <summary>
/// Dev-environment RBAC source: one document per user. Production swaps this for the
/// internal IAM via a different IAuthorizationProvider implementation - this collection
/// exists only so the same authorization contract can be exercised locally.
/// </summary>
public sealed class UserRoleDocument
{
    [BsonId]
    public ObjectId Id { get; set; }

    [BsonElement("UserId")]
    public string UserId { get; set; } = string.Empty;

    [BsonElement("Roles")]
    public List<string> Roles { get; set; } = new();

    [BsonElement("UpdatedAt")]
    public DateTime UpdatedAt { get; set; }
}
