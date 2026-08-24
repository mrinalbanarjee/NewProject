namespace TriageApi.Core.Redaction;

/// <summary>
/// Outcome of redacting a raw XML payload. When Success is false, RedactedXml is always
/// null - callers must not fall back to the raw input on failure (fail closed).
/// </summary>
public sealed record RedactionResult(bool Success, string? RedactedXml, string? BlockReason)
{
    public static RedactionResult Ok(string redactedXml) => new(true, redactedXml, null);

    public static RedactionResult Blocked(string reason) => new(false, null, reason);
}
