namespace TriageApi.Core.Models;

/// <summary>Status values for the CustomerEvent collection, per PRD §2.2.</summary>
public static class CustomerEventStatus
{
    public const string Completed = "Completed";
    public const string Error = "Error";
    public const string MqSending = "MQSending";
    public const string Sent = "Sent";
    public const string Reprocess = "Reprocess";
    public const string Cancelled = "Cancelled";
}
