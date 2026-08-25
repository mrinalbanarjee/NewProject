namespace TriageApi.Api.Configuration;

/// <summary>
/// Bound from the "AccountSync" configuration section.
/// </summary>
public sealed class AccountSummaryConfiguration
{
    public const string SectionName = "AccountSync";

    public int TTLInMinutes { get; set; }
    public DateOnly AlfaSystemDate { get; set; }
}
