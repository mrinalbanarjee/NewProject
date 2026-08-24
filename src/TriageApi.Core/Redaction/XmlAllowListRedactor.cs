using System.Xml;
using System.Xml.Linq;

namespace TriageApi.Core.Redaction;

/// <summary>
/// Redacts XML by preserving element/attribute structure (names, nesting, counts) while
/// masking every leaf value by default. Only values on the RedactionOptions allow-list
/// pass through unmasked. Any parse failure blocks the whole payload rather than
/// returning anything - a malformed document must never leak through unredacted.
/// </summary>
public sealed class XmlAllowListRedactor(RedactionOptions? options = null) : IMessageRedactor
{
    private readonly RedactionOptions _options = options ?? new RedactionOptions();

    public RedactionResult Redact(string? rawXml)
    {
        if (string.IsNullOrWhiteSpace(rawXml))
        {
            return RedactionResult.Ok(string.Empty);
        }

        XDocument document;
        try
        {
            document = XDocument.Parse(rawXml, LoadOptions.None);
        }
        catch (Exception ex) when (ex is XmlException or ArgumentException)
        {
            return RedactionResult.Blocked($"Unparseable XML ({ex.GetType().Name}) - payload blocked, not passed through.");
        }

        if (document.Root is null)
        {
            return RedactionResult.Blocked("XML document has no root element.");
        }

        var redactedRoot = RedactElement(document.Root);
        return RedactionResult.Ok(redactedRoot.ToString(SaveOptions.DisableFormatting));
    }

    private XElement RedactElement(XElement element)
    {
        var redacted = new XElement(element.Name);

        foreach (var attribute in element.Attributes())
        {
            if (attribute.IsNamespaceDeclaration)
            {
                redacted.Add(attribute);
                continue;
            }

            var value = _options.AllowedAttributeNames.Contains(attribute.Name.LocalName)
                ? attribute.Value
                : RedactionOptions.RedactedValuePlaceholder;
            redacted.Add(new XAttribute(attribute.Name, value));
        }

        var childElements = element.Elements().ToList();
        if (childElements.Count > 0)
        {
            foreach (var child in childElements)
            {
                redacted.Add(RedactElement(child));
            }
            return redacted;
        }

        var text = element.Value;
        if (string.IsNullOrWhiteSpace(text))
        {
            return redacted;
        }

        redacted.Value = _options.AllowedLeafElementNames.Contains(element.Name.LocalName)
            ? text
            : RedactionOptions.RedactedValuePlaceholder;

        return redacted;
    }
}
