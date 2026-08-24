using System.Globalization;

namespace TriageApi.Core.Triage;

/// <summary>
/// HoganTimeStamp is contractually a string, not a date (PRD §2.1). Parsing is required
/// for staleness/ordering comparisons - this must fail closed (return false) rather than
/// guess when the format is unexpected. Confirm the actual format against real data;
/// this currently accepts anything .NET's invariant-culture parser recognizes.
/// </summary>
public static class HoganTimestampParser
{
    public static bool TryParse(string? value, out DateTimeOffset result)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            result = default;
            return false;
        }

        return DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.None, out result);
    }
}
