namespace TriageApi.Core.Redaction;

/// <summary>
/// Deterministic redaction boundary. Every path from Mongo to the LLM must call this -
/// no code may hand an LLM (or any API response consumed by the agent) a raw
/// NotificationMessage or HoganRequestResponses Request/ResponseMessage value.
/// </summary>
public interface IMessageRedactor
{
    RedactionResult Redact(string? rawXml);
}
