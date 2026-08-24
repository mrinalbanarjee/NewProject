using TriageApi.Core.Models;

namespace TriageApi.Core.Triage;

/// <summary>
/// Compares the phone number two notifications refer to, without ever exposing the
/// number itself. A phone-consent update (OXCU066/OXCU021) should only be treated as
/// depending on a failed OXCU054 when both messages are about the *same* phone number -
/// two different phone changes for the same ECN aren't related just because they share a
/// customer and a type-dependency rule.
/// </summary>
public static class PhoneMatchChecker
{
    /// <param name="phoneFieldByType">
    /// Defaults to NotificationTypePhoneField.ElementNameByType (the production map, where
    /// only OXCU054 is confirmed). Overridable so tests can exercise the "configured and
    /// matching/mismatching" paths without waiting on real OXCU066/021 samples.
    /// </param>
    public static PhoneMatchResult Check(
        NotificationDocument a,
        NotificationDocument b,
        IReadOnlyDictionary<string, string>? phoneFieldByType = null)
    {
        var fieldMap = phoneFieldByType ?? NotificationTypePhoneField.ElementNameByType;

        if (!fieldMap.TryGetValue(a.NotificationType, out var fieldA))
        {
            return new PhoneMatchResult(false, false, $"Phone field not yet configured for type {a.NotificationType}.");
        }

        if (!fieldMap.TryGetValue(b.NotificationType, out var fieldB))
        {
            return new PhoneMatchResult(false, false, $"Phone field not yet configured for type {b.NotificationType}.");
        }

        if (!XmlLeafValueExtractor.TryExtractFirst(a.NotificationMessage, fieldA, out var phoneA))
        {
            return new PhoneMatchResult(false, false, $"Could not extract phone number from {a.CorrelationId}.");
        }

        if (!XmlLeafValueExtractor.TryExtractFirst(b.NotificationMessage, fieldB, out var phoneB))
        {
            return new PhoneMatchResult(false, false, $"Could not extract phone number from {b.CorrelationId}.");
        }

        var matches = Normalize(phoneA) == Normalize(phoneB);
        return new PhoneMatchResult(true, matches, null);
    }

    private static string Normalize(string rawPhoneNumber) =>
        new(rawPhoneNumber.Where(char.IsDigit).ToArray());
}
