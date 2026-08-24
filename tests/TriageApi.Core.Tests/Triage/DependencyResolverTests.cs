using TriageApi.Core.Models;
using TriageApi.Core.Triage;
using Xunit;

namespace TriageApi.Core.Tests.Triage;

public class DependencyResolverTests
{
    // Test-only phone field map: extends the production map (which only confirms OXCU054)
    // with OXCU066/OXCU021 so the "configured and matching/mismatching" paths can be
    // exercised without waiting on real sample messages for those types.
    private static readonly IReadOnlyDictionary<string, string> TestPhoneFieldByType = new Dictionary<string, string>
    {
        ["OXCU054"] = "newPhoneNbr",
        ["OXCU066"] = "newPhoneNbr",
        ["OXCU021"] = "newPhoneNbr",
    };

    private static NotificationDocument Notification(
        string correlationId, string ecn, string type, string hoganTimeStamp, string status = NotificationStatus.Failed, string? phoneNumber = null) =>
        new()
        {
            CorrelationId = correlationId,
            Ecn = ecn,
            NotificationType = type,
            HoganTimeStamp = hoganTimeStamp,
            Status = status,
            NotificationMessage = phoneNumber is null ? string.Empty : $"<Root><newPhoneNbr>{phoneNumber}</newPhoneNbr></Root>",
        };

    [Fact]
    public void Resolve_Oxcu054Failure_PullsInOxcu066AndOxcu021ForSameEcnAndSamePhone()
    {
        var failed = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", phoneNumber: "5551234567");
        var candidates = new[]
        {
            failed,
            Notification("dep1", "ECN1", "OXCU066", "2026-01-01T10:05:00Z", phoneNumber: "5551234567"),
            Notification("dep2", "ECN1", "OXCU021", "2026-01-01T10:02:00Z", phoneNumber: "5551234567"),
            Notification("unrelated", "ECN1", "OXCU016", "2026-01-01T10:03:00Z"),
        };

        var result = DependencyResolver.Resolve(failed, candidates, TestPhoneFieldByType);

        Assert.Equal(2, result.RelatedFailures.Count);
        Assert.Contains(result.RelatedFailures, r => r.CorrelationId == "dep1");
        Assert.Contains(result.RelatedFailures, r => r.CorrelationId == "dep2");
        Assert.DoesNotContain(result.RelatedFailures, r => r.CorrelationId == "unrelated");
    }

    [Fact]
    public void Resolve_Oxcu054Failure_DifferentPhoneNumber_ExcludedFromDependents()
    {
        var failed = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", phoneNumber: "5551234567");
        var candidates = new[]
        {
            failed,
            Notification("dep1", "ECN1", "OXCU066", "2026-01-01T10:05:00Z", phoneNumber: "9998887777"),
        };

        var result = DependencyResolver.Resolve(failed, candidates, TestPhoneFieldByType);

        Assert.Empty(result.RelatedFailures);
        Assert.Contains(result.Notes, n => n.Contains("different phone number"));
    }

    [Fact]
    public void Resolve_Oxcu054Failure_PhoneFieldNotConfiguredForType_ExcludedAndFlaggedForReview()
    {
        // Uses the production default map, where OXCU066/OXCU021 are intentionally unconfigured.
        var failed = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", phoneNumber: "5551234567");
        var candidates = new[]
        {
            failed,
            Notification("dep1", "ECN1", "OXCU066", "2026-01-01T10:05:00Z", phoneNumber: "5551234567"),
        };

        var result = DependencyResolver.Resolve(failed, candidates);

        Assert.Empty(result.RelatedFailures);
        Assert.Contains(result.Notes, n => n.Contains("could not be verified") && n.Contains("manual review"));
    }

    [Fact]
    public void Resolve_Oxcu054Failure_OrdersDependentsByHoganTimeStampAscending()
    {
        var failed = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", phoneNumber: "5551234567");
        var candidates = new[]
        {
            failed,
            Notification("later", "ECN1", "OXCU066", "2026-01-01T12:00:00Z", phoneNumber: "5551234567"),
            Notification("earlier", "ECN1", "OXCU021", "2026-01-01T11:00:00Z", phoneNumber: "5551234567"),
        };

        var result = DependencyResolver.Resolve(failed, candidates, TestPhoneFieldByType);

        Assert.Equal(new[] { "earlier", "later" }, result.RelatedFailures.Select(r => r.CorrelationId));
    }

    [Fact]
    public void Resolve_Oxcu008Failure_PullsInLaterNotificationsOfAnyTypeForSameEcn()
    {
        var failed = Notification("root", "ECN1", "OXCU008", "2026-01-01T10:00:00Z");
        var candidates = new[]
        {
            failed,
            Notification("after", "ECN1", "OXCU003", "2026-01-01T11:00:00Z"),
            Notification("before", "ECN1", "OXCU004", "2026-01-01T09:00:00Z"),
        };

        var result = DependencyResolver.Resolve(failed, candidates);

        Assert.Single(result.RelatedFailures);
        Assert.Equal("after", result.RelatedFailures[0].CorrelationId);
    }

    [Fact]
    public void Resolve_DifferentEcn_NeverPulledIn()
    {
        var failed = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", phoneNumber: "5551234567");
        var candidates = new[]
        {
            failed,
            Notification("otherEcn", "ECN2", "OXCU066", "2026-01-01T10:05:00Z", phoneNumber: "5551234567"),
        };

        var result = DependencyResolver.Resolve(failed, candidates, TestPhoneFieldByType);

        Assert.Empty(result.RelatedFailures);
    }

    [Fact]
    public void Resolve_TypeWithNoDependencyRule_ReturnsEmpty()
    {
        var failed = Notification("root", "ECN1", "OXCU016", "2026-01-01T10:00:00Z");
        var candidates = new[]
        {
            failed,
            Notification("other", "ECN1", "OXCU036", "2026-01-01T10:05:00Z"),
        };

        var result = DependencyResolver.Resolve(failed, candidates);

        Assert.Empty(result.RelatedFailures);
    }
}
