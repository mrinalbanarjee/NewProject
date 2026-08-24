namespace TriageApi.Core.Models;

/// <summary>
/// Status values for the Notification collection. PRD §2.1 lists Pending|Success|Failed|Error|Retry;
/// "Reprocess" is added here per §2.1.3 / §1's description of FailedHoganNotification using
/// Error/Reprocess — confirm the literal string value against the real collection before go-live.
/// </summary>
public static class NotificationStatus
{
    public const string Pending = "Pending";
    public const string Success = "Success";
    public const string Failed = "Failed";
    public const string Error = "Error";
    public const string Retry = "Retry";
    public const string Reprocess = "Reprocess";
}
