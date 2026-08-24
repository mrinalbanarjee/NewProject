using TriageApi.Core.Models;
using TriageApi.Core.Triage;
using Xunit;

namespace TriageApi.Core.Tests.Triage;

public class PhoneMatchCheckerTests
{
    private static NotificationDocument Notification(string correlationId, string type, string? phoneNumber) =>
        new()
        {
            CorrelationId = correlationId,
            NotificationType = type,
            NotificationMessage = phoneNumber is null ? string.Empty : $"<Root><newPhoneNbr>{phoneNumber}</newPhoneNbr></Root>",
        };

    [Fact]
    public void Check_SamePhoneNumber_Matches()
    {
        var a = Notification("a", "OXCU054", "5551234567");
        var b = Notification("b", "OXCU054", "5551234567");

        var result = PhoneMatchChecker.Check(a, b);

        Assert.True(result.Determinable);
        Assert.True(result.Matches);
    }

    [Fact]
    public void Check_DifferentPhoneNumber_DoesNotMatch()
    {
        var a = Notification("a", "OXCU054", "5551234567");
        var b = Notification("b", "OXCU054", "9998887777");

        var result = PhoneMatchChecker.Check(a, b);

        Assert.True(result.Determinable);
        Assert.False(result.Matches);
    }

    [Fact]
    public void Check_SamePhoneNumberDifferentFormatting_StillMatches()
    {
        var a = Notification("a", "OXCU054", "(555) 123-4567");
        var b = Notification("b", "OXCU054", "5551234567");

        var result = PhoneMatchChecker.Check(a, b);

        Assert.True(result.Determinable);
        Assert.True(result.Matches);
    }

    [Fact]
    public void Check_TypeNotConfiguredInFieldMap_IsUndeterminable()
    {
        // Production default map: OXCU066 is intentionally unconfigured pending a real sample.
        var a = Notification("a", "OXCU054", "5551234567");
        var b = Notification("b", "OXCU066", "5551234567");

        var result = PhoneMatchChecker.Check(a, b);

        Assert.False(result.Determinable);
        Assert.False(result.Matches);
        Assert.Contains("not yet configured", result.Reason);
    }

    [Fact]
    public void Check_PhoneFieldMissingFromMessage_IsUndeterminable()
    {
        var a = Notification("a", "OXCU054", phoneNumber: null);
        var b = Notification("b", "OXCU054", "5551234567");

        var result = PhoneMatchChecker.Check(a, b);

        Assert.False(result.Determinable);
    }

    [Fact]
    public void Check_CustomFieldMap_UsesProvidedMapInsteadOfDefault()
    {
        var a = Notification("a", "OXCU066", "5551234567");
        var b = Notification("b", "OXCU021", "5551234567");
        var customMap = new Dictionary<string, string> { ["OXCU066"] = "newPhoneNbr", ["OXCU021"] = "newPhoneNbr" };

        var result = PhoneMatchChecker.Check(a, b, customMap);

        Assert.True(result.Determinable);
        Assert.True(result.Matches);
    }
}
