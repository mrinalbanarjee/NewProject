namespace TriageApi.Core.Triage;

/// <summary>
/// Never carries the phone number itself - only whether two messages refer to the same
/// one. Determinable is false when the field name isn't configured for one of the types,
/// or the value couldn't be extracted; callers must treat that as "needs manual review",
/// not as a match or a non-match.
/// </summary>
public sealed record PhoneMatchResult(bool Determinable, bool Matches, string? Reason);
