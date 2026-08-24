using TriageApi.Core.Models;
using TriageApi.Core.Triage;
using Xunit;

namespace TriageApi.Core.Tests.Triage;

public class StalenessCheckerTests
{
    private static NotificationDocument Notification(
        string correlationId, string ecn, string type, string hoganTimeStamp, string status) =>
        new()
        {
            CorrelationId = correlationId,
            Ecn = ecn,
            NotificationType = type,
            HoganTimeStamp = hoganTimeStamp,
            Status = status,
        };

    [Fact]
    public void Check_LaterSuccessSameTypeSameEcn_IsStale()
    {
        var failed = Notification("failed1", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed);
        var later = Notification("success1", "ECN1", "OXCU054", "2026-01-01T11:00:00Z", NotificationStatus.Success);

        var result = StalenessChecker.Check(failed, new[] { failed, later });

        Assert.True(result.IsStale);
        Assert.Equal("success1", result.SupersededByCorrelationId);
    }

    [Fact]
    public void Check_NoLaterSuccess_IsNotStale()
    {
        var failed = Notification("failed1", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed);
        var earlierSuccess = Notification("success0", "ECN1", "OXCU054", "2026-01-01T09:00:00Z", NotificationStatus.Success);

        var result = StalenessChecker.Check(failed, new[] { failed, earlierSuccess });

        Assert.False(result.IsStale);
        Assert.True(result.Determinable);
    }

    [Fact]
    public void Check_LaterSuccessDifferentType_DoesNotCountAsStale()
    {
        var failed = Notification("failed1", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed);
        var laterDifferentType = Notification("success1", "ECN1", "OXCU066", "2026-01-01T11:00:00Z", NotificationStatus.Success);

        var result = StalenessChecker.Check(failed, new[] { failed, laterDifferentType });

        Assert.False(result.IsStale);
    }

    [Fact]
    public void Check_LaterSuccessDifferentEcn_DoesNotCountAsStale()
    {
        var failed = Notification("failed1", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed);
        var laterDifferentEcn = Notification("success1", "ECN2", "OXCU054", "2026-01-01T11:00:00Z", NotificationStatus.Success);

        var result = StalenessChecker.Check(failed, new[] { failed, laterDifferentEcn });

        Assert.False(result.IsStale);
    }

    [Fact]
    public void Check_MultipleLaterSuccesses_PicksNewest()
    {
        var failed = Notification("failed1", "ECN1", "OXCU054", "2026-01-01T10:00:00Z", NotificationStatus.Failed);
        var success1 = Notification("success1", "ECN1", "OXCU054", "2026-01-01T11:00:00Z", NotificationStatus.Success);
        var success2 = Notification("success2", "ECN1", "OXCU054", "2026-01-01T12:00:00Z", NotificationStatus.Success);

        var result = StalenessChecker.Check(failed, new[] { failed, success1, success2 });

        Assert.True(result.IsStale);
        Assert.Equal("success2", result.SupersededByCorrelationId);
    }

    [Fact]
    public void Check_UnparseableFailedTimestamp_IsUndeterminableNotStale()
    {
        var failed = Notification("failed1", "ECN1", "OXCU054", "not-a-timestamp", NotificationStatus.Failed);
        var later = Notification("success1", "ECN1", "OXCU054", "2026-01-01T11:00:00Z", NotificationStatus.Success);

        var result = StalenessChecker.Check(failed, new[] { failed, later });

        Assert.False(result.Determinable);
        Assert.False(result.IsStale);
        Assert.NotNull(result.Note);
    }
}
