namespace TriageApi.Core.Triage;

/// <summary>
/// Notification type reference data and confirmed dependency rules, from PRD §2.1.1 / §2.1.2.
/// Kept as data (not scattered conditionals) so new types/rules are additive.
/// </summary>
public static class NotificationTypeCatalog
{
    public static readonly IReadOnlyDictionary<string, string> Descriptions = new Dictionary<string, string>
    {
        ["OXCU054"] = "Customer Phone update",
        ["OXCU016"] = "Customer Current Resident Address Update",
        ["OXCU036"] = "Customer Email address update",
        ["OXCU021"] = "Customer Solicitation update",
        ["OXCU001"] = "Customer Information Sharing Status Update",
        ["OXCU008"] = "Customer Combine update",
        ["OXCU066"] = "Customer Consent Update (Phone/Text/Email)",
        ["OXCU003"] = "Customer Name change update",
        ["OXCU004"] = "Customer Date Of Birth update",
        ["OXAC007"] = "Account Mailing address update",
        ["OXCU039"] = "Customer full update",
    };

    /// <summary>Type -> the types that presume it has already been applied.</summary>
    public static readonly IReadOnlyDictionary<string, IReadOnlyList<string>> StaticDependents =
        new Dictionary<string, IReadOnlyList<string>>
        {
            ["OXCU054"] = new[] { "OXCU066", "OXCU021" },
        };

    /// <summary>Combine (OXCU008): every other type for that ECN occurring after it is potentially affected.</summary>
    public const string CombineType = "OXCU008";

    public static bool IsUpstreamOfAllTypes(string notificationType) => notificationType == CombineType;
}
