namespace TriageApi.Core.Redaction;

/// <summary>
/// Allow-list of leaf element / attribute local names whose *values* may pass through
/// unredacted, because they're diagnostic/structural rather than PII. Everything not
/// explicitly listed here is masked - this must stay an allow-list, never a PII deny-list,
/// so an unanticipated field fails closed instead of leaking.
///
/// The list below is confirmed against a real OXCU054 sample message (header/actyCtxt
/// block plus the non-PII body fields). It is applied globally across all notification
/// types for now, which is a simplification worth revisiting: an element name that's safe
/// in OXCU054 isn't guaranteed to mean the same (safe) thing in every other type's schema.
/// Only OXCU054 has been confirmed as of this writing - re-verify per type as real samples
/// for OXCU066, OXCU021, OXCU008, and the CustomerEvent HoganRequestResponses XML arrive,
/// and prefer narrowing this rather than assuming a name is safe everywhere it appears.
///
/// Deliberately NOT allow-listed (confirmed PII from the OXCU054 sample): tin (SSN),
/// fullNme (customer name), custId (observed to embed a name fragment), newPhoneNbr,
/// newRawPhoneNbr (the phone number itself - see PhoneMatchChecker for how dependency
/// resolution compares these without exposing them to the API/LLM).
/// </summary>
public sealed class RedactionOptions
{
    public HashSet<string> AllowedLeafElementNames { get; init; } = new(StringComparer.OrdinalIgnoreCase)
    {
        // header / actyCtxt - processing metadata, not customer PII.
        "crtId", "crtTmstp", "vrsn", "excpIndc", "procsTypCde", "procsNme", "applCde",
        "orgTypCde", "orgId", "inactId", "correlId", "athzCustNbr",

        // body - structural/diagnostic codes and dates, not the PII values themselves.
        "msgMode", "custCoId", "chgTypCde", "tinTypCde", "tinVldCde", "prflTypCd",
        "nonIndvIndc", "newPhoneNbrCoId", "newPurpsCde", "newTempPhoneInd", "newSeqNbr",
        "newEffectDte", "newExprDte", "newLstMntncDte", "pdLst", "svcLst",
    };

    public HashSet<string> AllowedAttributeNames { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    public const string RedactedValuePlaceholder = "[REDACTED]";
}
