using System.Xml;
using System.Xml.Linq;

namespace TriageApi.Core.Triage;

/// <summary>
/// Reads a single leaf element's raw (unredacted) value out of a NotificationMessage XML
/// payload, for internal server-side comparisons only (e.g. PhoneMatchChecker).
///
/// This intentionally handles PII in memory - that is allowed, the hard constraint is that
/// raw values must never reach an API response, log, exception message, or the LLM.
/// Callers must only use the extracted value to compute a boolean/derived result and must
/// never place the raw return value into anything serialized or logged.
/// </summary>
public static class XmlLeafValueExtractor
{
    public static bool TryExtractFirst(string? rawXml, string elementLocalName, out string value)
    {
        value = string.Empty;
        if (string.IsNullOrWhiteSpace(rawXml))
        {
            return false;
        }

        XDocument document;
        try
        {
            document = XDocument.Parse(rawXml);
        }
        catch (Exception ex) when (ex is XmlException or ArgumentException)
        {
            return false;
        }

        var element = document.Descendants()
            .FirstOrDefault(e => !e.HasElements && e.Name.LocalName.Equals(elementLocalName, StringComparison.OrdinalIgnoreCase));

        if (element is null || string.IsNullOrWhiteSpace(element.Value))
        {
            return false;
        }

        value = element.Value;
        return true;
    }
}
