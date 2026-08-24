using TriageApi.Core.Models;

namespace TriageApi.Core.Triage;

/// <summary>
/// Which Status values represent "still needs attention" for dependency resolution
/// purposes. A Success record must never be treated as a dependent needing reprocessing -
/// this classification exists specifically to keep that filtering in one place instead of
/// scattered inline checks.
/// </summary>
public static class NotificationFailureStatus
{
    private static readonly HashSet<string> FailureLike = new(StringComparer.OrdinalIgnoreCase)
    {
        NotificationStatus.Failed,
        NotificationStatus.Error,
        NotificationStatus.Retry,
        NotificationStatus.Reprocess,
    };

    public static bool IsFailureLike(string status) => FailureLike.Contains(status);
}
