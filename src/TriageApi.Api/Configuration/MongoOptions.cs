namespace TriageApi.Api.Configuration;

/// <summary>
/// Bound from the "Mongo" configuration section. ConnectionString must come from
/// environment variables / user-secrets, never committed to appsettings.json.
/// </summary>
public sealed class MongoOptions
{
    public const string SectionName = "Mongo";

    public string ConnectionString { get; set; } = string.Empty;
    public string DatabaseName { get; set; } = string.Empty;

    // Collection names are configurable in case the dev/shared Mongo instance uses
    // different casing/names than the PRD's collection names.
    public string NotificationAuditCollectionName { get; set; } = "NotificationAudit";
    public string FailedHoganNotificationCollectionName { get; set; } = "FailedHoganNotification";
    public string CustomerEventCollectionName { get; set; } = "CustomerEvent";
    public string UserRolesCollectionName { get; set; } = "UserRoles";
    public string ReprocessAuditCollectionName { get; set; } = "ReprocessAudit";
}
