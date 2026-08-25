namespace TriageApi.Api.Configuration;

/// <summary>
/// Bound from the "CustomerSync" configuration section - retention windows, mocking
/// toggles, and retry tuning for the customer-sync flow. Property names/casing match
/// the section verbatim (including "GenerateCustomeEvent") since config binding is
/// exact - don't "fix" spellings here without also updating appsettings.json.
/// </summary>
public sealed class CustomerAppConfiguration
{
    public const string SectionName = "CustomerSync";

    public int CustomerEventsRetentionInDays { get; set; }
    public bool DarkModeEnabled { get; set; }
    public int FailedHoganNotificationsRetentionInDays { get; set; }
    public bool GenerateCustomeEvent { get; set; }
    public string MockGUID { get; set; } = string.Empty;
    public bool MockMQCalls { get; set; }
    public bool MockMongoDB { get; set; }
    public int NotificationAuditRetentionInDays { get; set; }
    public int CustomerEventsRetryAfterInMinutes { get; set; }
    public int MaxRetryCount { get; set; }
}
