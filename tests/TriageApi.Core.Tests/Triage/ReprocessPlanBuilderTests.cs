using TriageApi.Core.Models;
using TriageApi.Core.Triage;
using Xunit;

namespace TriageApi.Core.Tests.Triage;

public class ReprocessPlanBuilderTests
{
    // See DependencyResolverTests for why this test-only map extends the production one.
    private static readonly IReadOnlyDictionary<string, string> TestPhoneFieldByType = new Dictionary<string, string>
    {
        ["OXCU054"] = "newPhoneNbr",
        ["OXCU066"] = "newPhoneNbr",
        ["OXCU021"] = "newPhoneNbr",
    };

    private static NotificationDocument Notification(
        string correlationId, string ecn, string type, string hoganTimeStamp, string status, string? phoneNumber = null) =>
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
    public void Build_StaleRoot_NoRecommendationNoSuperseded_JustReportsSupersession()
    {
        var root = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed);
        var laterSuccess = Notification("success1", "ECN1", "OXCU054", "2026-01-01T11:00:00Z", NotificationStatus.Success);

        var plan = ReprocessPlanBuilder.Build(root, new[] { root, laterSuccess });

        Assert.True(plan.RootStaleness.IsStale);
        Assert.Empty(plan.RecommendedOrder);
        Assert.Empty(plan.Superseded);
        Assert.Contains(plan.Notes, n => n.Contains("success1"));
    }

    [Fact]
    public void Build_NonStaleRootNoDependents_RecommendsRootOnly()
    {
        var root = Notification("root", "ECN1", "OXCU016", "2026-01-01T10:00:00Z", NotificationStatus.Failed);

        var plan = ReprocessPlanBuilder.Build(root, new[] { root });

        Assert.False(plan.RootStaleness.IsStale);
        Assert.Single(plan.RecommendedOrder);
        Assert.Equal("root", plan.RecommendedOrder[0].CorrelationId);
    }

    [Fact]
    public void Build_DependentIndependentlyStale_GoesToSupersededNotRecommended()
    {
        var root = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed, phoneNumber: "5551234567");
        var dependent = Notification("dep1", "ECN1", "OXCU066", "2026-01-01T10:05:00Z", NotificationStatus.Failed, phoneNumber: "5551234567");
        var dependentLaterSuccess = Notification("dep1success", "ECN1", "OXCU066", "2026-01-01T10:10:00Z", NotificationStatus.Success, phoneNumber: "5551234567");

        var plan = ReprocessPlanBuilder.Build(root, new[] { root, dependent, dependentLaterSuccess }, TestPhoneFieldByType);

        Assert.False(plan.RootStaleness.IsStale);
        Assert.Single(plan.RecommendedOrder);
        Assert.Equal("root", plan.RecommendedOrder[0].CorrelationId);
        Assert.Single(plan.Superseded);
        Assert.Equal("dep1", plan.Superseded[0].CorrelationId);
        Assert.Equal("dep1success", plan.Superseded[0].SupersededByCorrelationId);
    }

    [Fact]
    public void Build_RootAndNonStaleDependent_BothRecommendedRootFirst()
    {
        var root = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed, phoneNumber: "5551234567");
        var dependent = Notification("dep1", "ECN1", "OXCU066", "2026-01-01T10:05:00Z", NotificationStatus.Failed, phoneNumber: "5551234567");

        var plan = ReprocessPlanBuilder.Build(root, new[] { root, dependent }, TestPhoneFieldByType);

        Assert.Equal(2, plan.RecommendedOrder.Count);
        Assert.Equal("root", plan.RecommendedOrder[0].CorrelationId);
        Assert.Equal("dep1", plan.RecommendedOrder[1].CorrelationId);
        Assert.Empty(plan.Superseded);
    }

    [Fact]
    public void Build_RootAndDependentWithDifferentPhoneNumber_DependentNotRecommended()
    {
        var root = Notification("root", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed, phoneNumber: "5551234567");
        var unrelatedConsentUpdate = Notification("dep1", "ECN1", "OXCU066", "2026-01-01T10:05:00Z", NotificationStatus.Failed, phoneNumber: "9998887777");

        var plan = ReprocessPlanBuilder.Build(root, new[] { root, unrelatedConsentUpdate }, TestPhoneFieldByType);

        Assert.Single(plan.RecommendedOrder);
        Assert.Equal("root", plan.RecommendedOrder[0].CorrelationId);
        Assert.Empty(plan.Superseded);
        Assert.Contains(plan.Notes, n => n.Contains("different phone number"));
    }
}
