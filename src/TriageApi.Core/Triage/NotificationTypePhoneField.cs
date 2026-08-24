namespace TriageApi.Core.Triage;

/// <summary>
/// The leaf element name that carries "the phone number this message pertains to", per
/// NotificationType - needed so PhoneMatchChecker knows where to look in each type's XML.
///
/// Only OXCU054 is confirmed, from a real sample message (element `newPhoneNbr` /
/// `newRawPhoneNbr` under body). OXCU066 and OXCU021 are NOT yet configured - their real
/// XML shape hasn't been provided. Until they are, PhoneMatchChecker reports
/// "undeterminable" for those types rather than guessing a field name, which would risk
/// silently matching (or mismatching) on the wrong element.
/// </summary>
public static class NotificationTypePhoneField
{
    public static readonly IReadOnlyDictionary<string, string> ElementNameByType = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
    {
        ["OXCU054"] = "newPhoneNbr",
        // ["OXCU066"] = "TODO - confirm from a real OXCU066 sample message",
        // ["OXCU021"] = "TODO - confirm from a real OXCU021 sample message",
    };
}
